//
//  HealthKitManager.swift
//  MemoTime
//
//  HealthKit 数据访问管理器
//  负责权限申请、数据查询、实时监控
//

import Foundation
import HealthKit
import Combine

class HealthKitManager: ObservableObject {
    
    // MARK: - Properties
    
    /// HealthKit 存储实例
    private let healthStore = HKHealthStore()
    
    /// 发布权限状态变化
    @Published private(set) var authorizationStatus: HKAuthorizationStatus = .notDetermined
    
    /// 发布健康数据变化
    @Published private(set) var latestHealthData: [HealthDataType: [HealthDataSample]] = [:]
    
    /// 发布错误信息
    @Published private(set) var error: Error?
    
    /// 当前激活的查询
    private var activeQueries: Set<HKQuery> = []
    
    /// 后台任务标识符
    private var backgroundDeliveryTasks: Set<HKObjectType> = []
    
    /// 组合取消管理
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - 权限管理
    
    /// 请求健康数据访问权限
    /// - Parameter dataTypes: 请求的数据类型列表
    func requestAuthorization(for dataTypes: [HealthDataType]) async -> HealthPermissionResult {
        guard HKHealthStore.isHealthDataAvailable() else {
            error = NSError(domain: "HealthKitManager", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: "设备不支持 HealthKit"])
            return HealthPermissionResult(
                requestedTypes: dataTypes,
                grantedTypes: [],
                deniedTypes: dataTypes,
                requestDate: Date()
            )
        }
        
        // 转换为 HealthKit 类型
        var readTypes: Set<HKObjectType> = []
        var writeTypes: Set<HKSampleType> = []
        
        for dataType in dataTypes {
            if let quantityType = dataType.hkIdentifier.flatMap({ HKObjectType.quantityType(forIdentifier: $0) }) {
                readTypes.insert(quantityType)
                writeTypes.insert(quantityType)
            } else if let categoryType = dataType.hkCategoryIdentifier.flatMap({ HKObjectType.categoryType(forIdentifier: $0) }) {
                readTypes.insert(categoryType)
                writeTypes.insert(categoryType)
            }
        }
        
        do {
            // 请求权限
            try await healthStore.requestAuthorization(toShare: writeTypes, read: readTypes)
            
            // 检查每个类型的授权状态
            var grantedTypes: [HealthDataType] = []
            var deniedTypes: [HealthDataType] = []
            
            for dataType in dataTypes {
                if let quantityType = dataType.hkIdentifier.flatMap({ HKObjectType.quantityType(forIdentifier: $0) }) {
                    let status = healthStore.authorizationStatus(for: quantityType)
                    if status == .sharingAuthorized {
                        grantedTypes.append(dataType)
                    } else {
                        deniedTypes.append(dataType)
                    }
                } else if let categoryType = dataType.hkCategoryIdentifier.flatMap({ HKObjectType.categoryType(forIdentifier: $0) }) {
                    let status = healthStore.authorizationStatus(for: categoryType)
                    if status == .sharingAuthorized {
                        grantedTypes.append(dataType)
                    } else {
                        deniedTypes.append(dataType)
                    }
                }
            }
            
            let result = HealthPermissionResult(
                requestedTypes: dataTypes,
                grantedTypes: grantedTypes,
                deniedTypes: deniedTypes,
                requestDate: Date()
            )
            
            // 更新发布的状态
            await MainActor.run {
                self.authorizationStatus = .sharingAuthorized
            }
            
            return result
            
        } catch {
            self.error = error
            return HealthPermissionResult(
                requestedTypes: dataTypes,
                grantedTypes: [],
                deniedTypes: dataTypes,
                requestDate: Date()
            )
        }
    }
    
    // MARK: - 数据查询
    
    /// 查询指定时间范围的健康数据
    /// - Parameters:
    ///   - dataType: 数据类型
    ///   - startDate: 开始时间
    ///   - endDate: 结束时间
    /// - Returns: 健康数据样本数组
    func queryHealthData(
        for dataType: HealthDataType,
        from startDate: Date,
        to endDate: Date
    ) async throws -> [HealthDataSample] {
        
        guard let sampleType = getSampleType(for: dataType) else {
            throw NSError(domain: "HealthKitManager", code: -2,
                        userInfo: [NSLocalizedDescriptionKey: "不支持的数据类型: \(dataType.rawValue)"])
        }
        
        // 创建谓词
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        
        // 排序描述符
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
        
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: sampleType,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }
                
                guard let samples = samples else {
                    continuation.resume(returning: [])
                    return
                }
                
                // 转换为 HealthDataSample
                let healthSamples = samples.compactMap { sample -> HealthDataSample? in
                    if let quantitySample = sample as? HKQuantitySample {
                        return HealthDataSample(from: quantitySample, dataType: dataType)
                    } else if let categorySample = sample as? HKCategorySample {
                        return HealthDataSample(from: categorySample, dataType: dataType)
                    }
                    return nil
                }
                
                continuation.resume(returning: healthSamples)
            }
            
            healthStore.execute(query)
        }
    }
    
    /// 查询今日汇总数据
    /// - Parameter dataType: 数据类型
    /// - Returns: 汇总值
    func queryTodaySummary(for dataType: HealthDataType) async throws -> Double {
        guard let quantityType = dataType.hkIdentifier.flatMap({ HKQuantityType.quantityType(forIdentifier: $0) }) else {
            throw NSError(domain: "HealthKitManager", code: -2,
                        userInfo: [NSLocalizedDescriptionKey: "不支持的数据类型: \(dataType.rawValue)"])
        }
        
        let calendar = Calendar.current
        let now = Date()
        let startOfDay = calendar.startOfDay(for: now)
        
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: now, options: .strictStartDate)
        
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsQuery(
                quantityType: quantityType,
                quantitySamplePredicate: predicate,
                options: .cumulativeSum
            ) { _, statistics, error in
                if let error = error {
                    continuation.resume(throwing: error)
                    return
                }
                
                guard let sum = statistics?.sumQuantity(),
                      let unit = dataType.healthKitUnit else {
                    continuation.resume(returning: 0.0)
                    return
                }
                
                let value = sum.doubleValue(for: unit)
                continuation.resume(returning: value)
            }
            
            healthStore.execute(query)
        }
    }
    
    /// 获取过去7天的趋势数据
    /// - Parameter dataType: 数据类型
    /// - Returns: 每日数据
    func queryWeeklyTrend(for dataType: HealthDataType) async throws -> [Date: Double] {
        let calendar = Calendar.current
        let now = Date()
        let startDate = calendar.date(byAdding: .day, value: -7, to: now) ?? now
        
        let samples = try await queryHealthData(for: dataType, from: startDate, to: now)
        
        // 按日期分组并计算每日平均值
        var dailyData: [Date: [Double]] = [:]
        
        for sample in samples {
            let dateKey = calendar.startOfDay(for: sample.startDate)
            if dailyData[dateKey] == nil {
                dailyData[dateKey] = []
            }
            dailyData[dateKey]?.append(sample.value)
        }
        
        // 计算每日平均值
        var result: [Date: Double] = [:]
        for (date, values) in dailyData {
            let average = values.reduce(0, +) / Double(values.count)
            result[date] = average
        }
        
        return result
    }
    
    // MARK: - 实时监控
    
    /// 启动指定数据类型的实时监控
    /// - Parameter dataType: 数据类型
    func startRealTimeMonitoring(for dataType: HealthDataType) {
        guard let sampleType = getSampleType(for: dataType) else {
            return
        }
        
        // 创建观察者查询
        let query = HKObserverQuery(sampleType: sampleType, predicate: nil) { [weak self] query, completionHandler, error in
            guard let self = self else {
                completionHandler()
                return
            }
            
            if let error = error {
                await MainActor.run {
                    self.error = error
                }
                completionHandler()
                return
            }
            
            // 获取最新数据
            Task {
                let now = Date()
                let startDate = Calendar.current.date(byAdding: .hour, value: -1, to: now) ?? now
                
                do {
                    let samples = try await self.queryHealthData(for: dataType, from: startDate, to: now)
                    
                    await MainActor.run {
                        self.latestHealthData[dataType] = samples
                    }
                } catch {
                    await MainActor.run {
                        self.error = error
                    }
                }
                
                completionHandler()
            }
        }
        
        healthStore.execute(query)
        activeQueries.insert(query)
        
        // 启用后台交付
        enableBackgroundDelivery(for: sampleType, frequency: .immediate)
    }
    
    /// 停止所有实时监控
    func stopAllMonitoring() {
        for query in activeQueries {
            healthStore.stop(query)
        }
        activeQueries.removeAll()
        
        // 禁用后台交付
        disableAllBackgroundDelivery()
    }
    
    /// 启用后台数据交付
    /// - Parameters:
    ///   - sampleType: 样本类型
    ///   - frequency: 交付频率
    private func enableBackgroundDelivery(for sampleType: HKSampleType, frequency: HKUpdateFrequency) {
        healthStore.enableBackgroundDelivery(for: sampleType, frequency: frequency) { [weak self] success, error in
            if success {
                Task { @MainActor in
                    self?.backgroundDeliveryTasks.insert(sampleType)
                }
            } else if let error = error {
                Task { @MainActor in
                    self?.error = error
                }
            }
        }
    }
    
    /// 禁用所有后台交付
    private func disableAllBackgroundDelivery() {
        for sampleType in backgroundDeliveryTasks {
            healthStore.disableBackgroundDelivery(for: sampleType) { [weak self] success, error in
                if !success, let error = error {
                    Task { @MainActor in
                        self?.error = error
                    }
                }
            }
        }
        backgroundDeliveryTasks.removeAll()
    }
    
    // MARK: - 锚点查询（增量同步）
    
    /// 启动锚点查询，用于增量数据同步
    /// - Parameters:
    ///   - dataType: 数据类型
    ///   - anchor: 上次查询的锚点（nil 表示首次查询）
    ///   - completion: 查询结果回调
    func startAnchoredQuery(
        for dataType: HealthDataType,
        anchor: HKQueryAnchor?,
        completion: @escaping ([HealthDataSample], HKQueryAnchor?, Error?) -> Void
    ) {
        guard let sampleType = getSampleType(for: dataType) else {
            completion([], nil, NSError(domain: "HealthKitManager", code: -2,
                                      userInfo: [NSLocalizedDescriptionKey: "不支持的数据类型: \(dataType.rawValue)"]))
            return
        }
        
        let query = HKAnchoredObjectQuery(
            type: sampleType,
            predicate: nil,
            anchor: anchor,
            limit: HKObjectQueryNoLimit
        ) { query, newSamples, deletedSamples, newAnchor, error in
            if let error = error {
                completion([], nil, error)
                return
            }
            
            // 转换为 HealthDataSample
            let healthSamples = (newSamples ?? []).compactMap { sample -> HealthDataSample? in
                if let quantitySample = sample as? HKQuantitySample {
                    return HealthDataSample(from: quantitySample, dataType: dataType)
                } else if let categorySample = sample as? HKCategorySample {
                    return HealthDataSample(from: categorySample, dataType: dataType)
                }
                return nil
            }
            
            completion(healthSamples, newAnchor, nil)
        }
        
        healthStore.execute(query)
        activeQueries.insert(query)
    }
    
    // MARK: - 辅助方法
    
    /// 获取 HealthKit 样本类型
    /// - Parameter dataType: 健康数据类型
    /// - Returns: HKSampleType
    private func getSampleType(for dataType: HealthDataType) -> HKSampleType? {
        if let quantityType = dataType.hkIdentifier.flatMap({ HKObjectType.quantityType(forIdentifier: $0) }) {
            return quantityType
        } else if let categoryType = dataType.hkCategoryIdentifier.flatMap({ HKObjectType.categoryType(forIdentifier: $0) }) {
            return categoryType
        }
        return nil
    }
    
    /// 检查特定数据类型的授权状态
    /// - Parameter dataType: 数据类型
    /// - Returns: 授权状态
    func authorizationStatus(for dataType: HealthDataType) -> HKAuthorizationStatus {
        guard let sampleType = getSampleType(for: dataType) else {
            return .notDetermined
        }
        
        return healthStore.authorizationStatus(for: sampleType)
    }
    
    /// 检查设备是否支持 HealthKit
    var isHealthDataAvailable: Bool {
        return HKHealthStore.isHealthDataAvailable()
    }
    
    // MARK: - 数据清理
    
    deinit {
        stopAllMonitoring()
    }
}