//
//  HealthDashboardViewModel.swift
//  MemoTime
//
//  健康数据面板视图模型
//  管理健康数据的加载、处理和展示状态
//

import Foundation
import Combine
import SwiftUI

class HealthDashboardViewModel: ObservableObject {
    
    // MARK: - Published Properties
    
    /// 健康数据摘要
    @Published private(set) var healthSummary: HealthDataSummary?
    
    /// 趋势数据（步数、心率、睡眠）
    @Published private(set) var stepTrend: HealthTrendData?
    @Published private(set) var heartRateTrend: HealthTrendData?
    @Published private(set) var sleepTrend: HealthTrendData?
    
    /// 加载状态
    @Published private(set) var isLoading = false
    
    /// 错误信息
    @Published private(set) var error: Error?
    
    /// 权限状态
    @Published private(set) var authorizationStatus: HKAuthorizationStatus = .notDetermined
    
    /// 同步状态
    @Published private(set) var syncStatus: CloudSyncStatus = .disabled
    
    /// 存储统计
    @Published private(set) var storageStats: HealthDataEncryptionManager.StorageStatistics?
    
    /// 健康建议列表
    @Published private(set) var recommendations: [HealthRecommendation] = []
    
    // MARK: - Dependencies
    
    private let healthKitManager: HealthKitManager
    private let encryptionManager: HealthDataEncryptionManager
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Configuration
    
    /// 同步配置
    private var syncConfiguration = HealthSyncConfiguration()
    
    /// 监控的数据类型
    private let monitoredDataTypes: [HealthDataType] = [
        .stepCount,
        .heartRate,
        .sleepAnalysis,
        .bodyMass,
        .activeEnergyBurned
    ]
    
    // MARK: - Initialization
    
    init(healthKitManager: HealthKitManager = HealthKitManager(),
         encryptionManager: HealthDataEncryptionManager = HealthDataEncryptionManager()) {
        self.healthKitManager = healthKitManager
        self.encryptionManager = encryptionManager
        
        setupBindings()
    }
    
    // MARK: - Setup
    
    private func setupBindings() {
        // 监听 HealthKit 权限状态
        healthKitManager.$authorizationStatus
            .receive(on: DispatchQueue.main)
            .assign(to: \.authorizationStatus, on: self)
            .store(in: &cancellables)
        
        // 监听加密管理器状态
        encryptionManager.$syncStatus
            .receive(on: DispatchQueue.main)
            .assign(to: \.syncStatus, on: self)
            .store(in: &cancellables)
        
        encryptionManager.$storageStats
            .receive(on: DispatchQueue.main)
            .assign(to: \.storageStats, on: self)
            .store(in: &cancellables)
    }
    
    // MARK: - 数据加载
    
    /// 加载所有健康数据
    @MainActor
    func loadHealthData() async {
        guard !isLoading else { return }
        
        isLoading = true
        error = nil
        
        do {
            // 1. 检查并请求权限
            let permissionResult = try await requestPermissionsIfNeeded()
            
            guard permissionResult.isFullyGranted || permissionResult.isPartiallyGranted else {
                throw NSError(domain: "HealthDashboard", code: -1,
                            userInfo: [NSLocalizedDescriptionKey: "健康数据访问权限不足"])
            }
            
            // 2. 查询今日摘要数据
            let todaySummary = try await loadTodaySummary()
            healthSummary = todaySummary
            
            // 3. 加载趋势数据
            async let steps = loadTrendData(for: .stepCount)
            async let heartRate = loadTrendData(for: .heartRate)
            async let sleep = loadTrendData(for: .sleepAnalysis)
            
            (stepTrend, heartRateTrend, sleepTrend) = try await (steps, heartRate, sleep)
            
            // 4. 生成健康建议
            recommendations = generateRecommendations()
            
            // 5. 启动实时监控
            startRealTimeMonitoring()
            
        } catch {
            self.error = error
            print("Failed to load health data: \(error)")
        }
        
        isLoading = false
    }
    
    /// 请求权限（如果需要）
    private func requestPermissionsIfNeeded() async throws -> HealthPermissionResult {
        let status = healthKitManager.authorizationStatus(for: monitoredDataTypes.first ?? .stepCount)
        
        if status == .notDetermined {
            return await healthKitManager.requestAuthorization(for: monitoredDataTypes)
        }
        
        // 检查已授予的权限
        var grantedTypes: [HealthDataType] = []
        var deniedTypes: [HealthDataType] = []
        
        for dataType in monitoredDataTypes {
            let authStatus = healthKitManager.authorizationStatus(for: dataType)
            if authStatus == .sharingAuthorized {
                grantedTypes.append(dataType)
            } else {
                deniedTypes.append(dataType)
            }
        }
        
        return HealthPermissionResult(
            requestedTypes: monitoredDataTypes,
            grantedTypes: grantedTypes,
            deniedTypes: deniedTypes,
            requestDate: Date()
        )
    }
    
    /// 加载今日摘要数据
    private func loadTodaySummary() async throws -> HealthDataSummary {
        var summary = HealthDataSummary(date: Date())
        
        for dataType in monitoredDataTypes {
            guard healthKitManager.authorizationStatus(for: dataType) == .sharingAuthorized else {
                continue
            }
            
            if dataType == .sleepAnalysis {
                // 睡眠数据需要特殊处理（查询最近一次睡眠）
                let samples = try await healthKitManager.queryHealthData(
                    for: dataType,
                    from: Calendar.current.date(byAdding: .day, value: -1, to: Date()) ?? Date(),
                    to: Date()
                )
                
                if let latestSleep = samples.first {
                    summary.metrics[dataType] = latestSleep.value
                }
            } else {
                // 其他数据查询今日汇总
                let value = try await healthKitManager.queryTodaySummary(for: dataType)
                summary.metrics[dataType] = value
            }
        }
        
        return summary
    }
    
    /// 加载趋势数据
    private func loadTrendData(for dataType: HealthDataType) async throws -> HealthTrendData? {
        guard healthKitManager.authorizationStatus(for: dataType) == .sharingAuthorized else {
            return nil
        }
        
        let dailyValues = try await healthKitManager.queryWeeklyTrend(for: dataType)
        
        guard !dailyValues.isEmpty else {
            return nil
        }
        
        let values = Array(dailyValues.values)
        let average = values.reduce(0, +) / Double(values.count)
        let max = values.max() ?? 0
        let min = values.min() ?? 0
        
        // 简单趋势判断（基于最后两天的变化）
        let sortedDates = dailyValues.keys.sorted()
        guard sortedDates.count >= 2 else {
            return HealthTrendData(
                period: DateInterval(start: sortedDates.first ?? Date(), end: Date()),
                dataType: dataType,
                dailyValues: dailyValues,
                average: average,
                max: max,
                min: min,
                trendDirection: .stable
            )
        }
        
        let recentDates = sortedDates.suffix(2)
        let recentValues = recentDates.compactMap { dailyValues[$0] }
        
        guard recentValues.count == 2 else {
            return HealthTrendData(
                period: DateInterval(start: sortedDates.first ?? Date(), end: Date()),
                dataType: dataType,
                dailyValues: dailyValues,
                average: average,
                max: max,
                min: min,
                trendDirection: .stable
            )
        }
        
        let trendDirection: TrendDirection
        let change = recentValues[0] - recentValues[1]
        
        if abs(change) < (average * 0.05) { // 变化小于5%认为是稳定
            trendDirection = .stable
        } else if change > 0 {
            trendDirection = .increasing
        } else {
            trendDirection = .decreasing
        }
        
        return HealthTrendData(
            period: DateInterval(start: sortedDates.first ?? Date(), end: Date()),
            dataType: dataType,
            dailyValues: dailyValues,
            average: average,
            max: max,
            min: min,
            trendDirection: trendDirection
        )
    }
    
    // MARK: - 实时监控
    
    /// 启动实时监控
    private func startRealTimeMonitoring() {
        for dataType in monitoredDataTypes {
            guard healthKitManager.authorizationStatus(for: dataType) == .sharingAuthorized else {
                continue
            }
            
            healthKitManager.startRealTimeMonitoring(for: dataType)
        }
    }
    
    /// 停止实时监控
    func stopRealTimeMonitoring() {
        healthKitManager.stopAllMonitoring()
    }
    
    // MARK: - 健康建议生成
    
    /// 生成健康建议
    private func generateRecommendations() -> [HealthRecommendation] {
        var recommendations: [HealthRecommendation] = []
        
        // 基于步数建议
        if let steps = healthSummary?.steps {
            let dailyGoal = 10000.0
            
            if steps < dailyGoal * 0.5 {
                recommendations.append(
                    HealthRecommendation(
                        id: UUID(),
                        priority: .high,
                        category: .activity,
                        title: "增加日常活动",
                        description: "今日步数较低，建议增加站立时间和短距离步行。",
                        actionSteps: [
                            "每小时站立活动5分钟",
                            "午餐后散步15分钟",
                            "使用楼梯代替电梯"
                        ],
                        estimatedImpact: "每日可增加2000-3000步",
                        validUntil: Calendar.current.date(byAdding: .day, value: 1, to: Date())
                    )
                )
            } else if steps >= dailyGoal {
                recommendations.append(
                    HealthRecommendation(
                        id: UUID(),
                        priority: .low,
                        category: .activity,
                        title: "保持活跃习惯",
                        description: "恭喜达成每日步数目标！继续保持均衡活动。",
                        actionSteps: [
                            "保持日常步行习惯",
                            "尝试不同运动形式",
                            "适当休息和恢复"
                        ],
                        estimatedImpact: "维持良好心血管健康",
                        validUntil: Calendar.current.date(byAdding: .day, value: 1, to: Date())
                    )
                )
            }
        }
        
        // 基于睡眠建议
        if let sleepHours = healthSummary?.sleepHours {
            let recommendedSleep = 7.0
            
            if sleepHours < recommendedSleep - 1 {
                recommendations.append(
                    HealthRecommendation(
                        id: UUID(),
                        priority: .medium,
                        category: .sleep,
                        title: "改善睡眠质量",
                        description: "睡眠时长不足，可能影响日间精力和认知功能。",
                        actionSteps: [
                            "建立固定睡眠时间表",
                            "睡前1小时避免蓝光设备",
                            "保持卧室黑暗安静",
                            "避免睡前摄入咖啡因"
                        ],
                        estimatedImpact: "提高日间注意力和工作效率",
                        validUntil: Calendar.current.date(byAdding: .day, value: 1, to: Date())
                    )
                )
            }
        }
        
        // 基于心率建议
        if let heartRate = healthSummary?.averageHeartRate {
            let normalRange = 60.0...100.0
            
            if heartRate > normalRange.upperBound {
                recommendations.append(
                    HealthRecommendation(
                        id: UUID(),
                        priority: .medium,
                        category: .stress,
                        title: "管理压力水平",
                        description: "静息心率偏高，可能与压力或缺乏锻炼有关。",
                        actionSteps: [
                            "尝试深呼吸练习",
                            "每日安排短暂休息",
                            "保持适度身体活动",
                            "考虑冥想或正念练习"
                        ],
                        estimatedImpact: "降低静息心率，改善心血管健康",
                        validUntil: Calendar.current.date(byAdding: .day, value: 1, to: Date())
                    )
                )
            }
        }
        
        // 通用建议（如果其他建议较少）
        if recommendations.count < 2 {
            recommendations.append(
                HealthRecommendation(
                    id: UUID(),
                    priority: .low,
                    category: .general,
                    title: "保持水分摄入",
                    description: "充足的水分摄入有助于新陈代谢和认知功能。",
                    actionSteps: [
                        "每日饮用6-8杯水",
                        "运动前后补充水分",
                        "通过尿液颜色判断水分状况"
                    ],
                    estimatedImpact: "改善能量水平和皮肤健康",
                    validUntil: Calendar.current.date(byAdding: .day, value: 1, to: Date())
                )
            )
        }
        
        return recommendations
    }
    
    // MARK: - 配置管理
    
    /// 更新同步配置
    func updateSyncConfiguration(_ configuration: HealthSyncConfiguration) {
        syncConfiguration = configuration
        
        // 应用配置
        if syncConfiguration.cloudSyncEnabled {
            encryptionManager.enableCloudSync()
        } else {
            encryptionManager.disableCloudSync()
        }
    }
    
    /// 获取当前配置
    func getSyncConfiguration() -> HealthSyncConfiguration {
        return syncConfiguration
    }
    
    // MARK: - 数据管理
    
    /// 刷新健康数据
    func refreshData() {
        Task {
            await loadHealthData()
        }
    }
    
    /// 清除所有数据（测试用）
    func clearAllData() throws {
        try encryptionManager.clearAllData()
        healthSummary = nil
        stepTrend = nil
        heartRateTrend = nil
        sleepTrend = nil
        recommendations = []
    }
    
    deinit {
        stopRealTimeMonitoring()
    }
}