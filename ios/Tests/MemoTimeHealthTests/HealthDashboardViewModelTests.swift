//
//  HealthDashboardViewModelTests.swift
//  MemoTimeHealthTests
//
//  健康数据面板视图模型单元测试
//

import XCTest
@testable import MemoTimeHealth
import Combine

final class HealthDashboardViewModelTests: XCTestCase {
    
    var viewModel: HealthDashboardViewModel!
    var mockHealthKitManager: MockHealthKitManager!
    var mockEncryptionManager: MockHealthDataEncryptionManager!
    var cancellables: Set<AnyCancellable>!
    
    override func setUp() {
        super.setUp()
        
        cancellables = []
        mockHealthKitManager = MockHealthKitManager()
        mockEncryptionManager = MockHealthDataEncryptionManager()
        
        viewModel = HealthDashboardViewModel(
            healthKitManager: mockHealthKitManager,
            encryptionManager: mockEncryptionManager
        )
    }
    
    override func tearDown() {
        viewModel = nil
        mockHealthKitManager = nil
        mockEncryptionManager = nil
        cancellables = nil
        
        super.tearDown()
    }
    
    // MARK: - 权限测试
    
    func testLoadHealthData_WhenPermissionsNotGranted_ShouldRequestPermissions() async {
        // 设置模拟权限状态
        mockHealthKitManager.authorizationStatusToReturn = .notDetermined
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证是否请求了权限
        XCTAssertTrue(mockHealthKitManager.didRequestAuthorization,
                     "应该请求健康数据权限")
    }
    
    func testLoadHealthData_WhenPermissionsDenied_ShouldSetError() async {
        // 设置模拟权限拒绝
        mockHealthKitManager.authorizationStatusToReturn = .sharingDenied
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证错误状态
        XCTAssertNotNil(viewModel.error, "权限拒绝时应该设置错误")
        XCTAssertFalse(viewModel.isLoading, "加载完成后应该停止加载状态")
    }
    
    // MARK: - 数据加载测试
    
    func testLoadHealthData_WhenPermissionsGranted_ShouldLoadSummaryAndTrends() async {
        // 设置模拟权限授予
        mockHealthKitManager.authorizationStatusToReturn = .sharingAuthorized
        
        // 设置模拟数据
        mockHealthKitManager.todaySummaryToReturn = 5000.0
        mockHealthKitManager.weeklyTrendToReturn = [
            Date().addingTimeInterval(-6 * 86400): 4000.0,
            Date().addingTimeInterval(-5 * 86400): 4500.0,
            Date().addingTimeInterval(-4 * 86400): 5000.0,
            Date().addingTimeInterval(-3 * 86400): 5500.0,
            Date().addingTimeInterval(-2 * 86400): 5000.0,
            Date().addingTimeInterval(-1 * 86400): 5500.0,
            Date(): 5000.0
        ]
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证数据加载状态
        XCTAssertNotNil(viewModel.healthSummary, "应该加载健康摘要数据")
        XCTAssertNotNil(viewModel.stepTrend, "应该加载步数趋势数据")
        XCTAssertFalse(viewModel.isLoading, "加载完成后应该停止加载状态")
        XCTAssertNil(viewModel.error, "成功加载时不应该有错误")
    }
    
    func testLoadHealthData_WhenQueryFails_ShouldSetError() async {
        // 设置模拟权限授予但查询失败
        mockHealthKitManager.authorizationStatusToReturn = .sharingAuthorized
        mockHealthKitManager.queryError = NSError(domain: "HealthKit", code: -1,
                                                userInfo: [NSLocalizedDescriptionKey: "查询失败"])
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证错误状态
        XCTAssertNotNil(viewModel.error, "查询失败时应该设置错误")
        XCTAssertFalse(viewModel.isLoading, "加载完成后应该停止加载状态")
    }
    
    // MARK: - 趋势数据分析测试
    
    func testTrendData_Analysis_ShouldCalculateCorrectStatistics() async {
        // 设置模拟数据
        let testData: [Date: Double] = [
            Date().addingTimeInterval(-6 * 86400): 1000.0,
            Date().addingTimeInterval(-5 * 86400): 2000.0,
            Date().addingTimeInterval(-4 * 86400): 3000.0,
            Date().addingTimeInterval(-3 * 86400): 4000.0,
            Date().addingTimeInterval(-2 * 86400): 5000.0,
            Date().addingTimeInterval(-1 * 86400): 6000.0,
            Date(): 7000.0
        ]
        
        mockHealthKitManager.authorizationStatusToReturn = .sharingAuthorized
        mockHealthKitManager.weeklyTrendToReturn = testData
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证统计计算
        guard let stepTrend = viewModel.stepTrend else {
            XCTFail("应该加载步数趋势数据")
            return
        }
        
        XCTAssertEqual(stepTrend.average, 4000.0, accuracy: 0.001,
                      "平均值计算错误")
        XCTAssertEqual(stepTrend.max, 7000.0, accuracy: 0.001,
                      "最大值计算错误")
        XCTAssertEqual(stepTrend.min, 1000.0, accuracy: 0.001,
                      "最小值计算错误")
        XCTAssertEqual(stepTrend.trendDirection, .increasing,
                      "趋势方向判断错误")
    }
    
    // MARK: - 健康建议生成测试
    
    func testRecommendationGeneration_WhenStepsBelowGoal_ShouldGenerateActivityRecommendation() async {
        // 设置模拟数据：步数低于目标
        mockHealthKitManager.authorizationStatusToReturn = .sharingAuthorized
        mockHealthKitManager.todaySummaryToReturn = 3000.0 // 低于10000的一半
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证建议生成
        XCTAssertFalse(viewModel.recommendations.isEmpty,
                      "步数不足时应该生成建议")
        
        let activityRecommendations = viewModel.recommendations.filter {
            $0.category == .activity
        }
        XCTAssertFalse(activityRecommendations.isEmpty,
                      "应该有活动相关的建议")
        
        if let firstRecommendation = activityRecommendations.first {
            XCTAssertEqual(firstRecommendation.priority, .high,
                          "步数严重不足时应该是高优先级")
            XCTAssertTrue(firstRecommendation.title.contains("增加") ||
                         firstRecommendation.title.contains("活跃"),
                         "建议标题应该与增加活动相关")
        }
    }
    
    func testRecommendationGeneration_WhenSleepInsufficient_ShouldGenerateSleepRecommendation() async {
        // 设置模拟数据：睡眠不足
        mockHealthKitManager.authorizationStatusToReturn = .sharingAuthorized
        
        // 模拟睡眠数据（少于6小时）
        let sleepSample = HealthDataSample(
            dataType: .sleepAnalysis,
            value: 5.5,
            startDate: Date().addingTimeInterval(-8 * 3600),
            endDate: Date().addingTimeInterval(-2 * 3600)
        )
        mockHealthKitManager.queryResults = [sleepSample]
        
        // 触发数据加载
        await viewModel.loadHealthData()
        
        // 验证建议生成
        let sleepRecommendations = viewModel.recommendations.filter {
            $0.category == .sleep
        }
        XCTAssertFalse(sleepRecommendations.isEmpty,
                      "睡眠不足时应该生成睡眠建议")
        
        if let firstRecommendation = sleepRecommendations.first {
            XCTAssertEqual(firstRecommendation.priority, .medium,
                          "睡眠不足时应该是中优先级")
            XCTAssertTrue(firstRecommendation.title.contains("睡眠") ||
                         firstRecommendation.title.contains("质量"),
                         "建议标题应该与睡眠质量相关")
        }
    }
    
    // MARK: - 状态绑定测试
    
    func testViewModel_ShouldBindToHealthKitManagerAuthorizationStatus() {
        let expectation = XCTestExpectation(description: "Authorization status binding")
        
        // 监听授权状态变化
        viewModel.$authorizationStatus
            .dropFirst()
            .sink { status in
                XCTAssertEqual(status, .sharingAuthorized,
                              "授权状态应该与模拟管理器同步")
                expectation.fulfill()
            }
            .store(in: &cancellables)
        
        // 触发模拟管理器状态变化
        mockHealthKitManager.authorizationStatusToReturn = .sharingAuthorized
        mockHealthKitManager.objectWillChange.send()
        
        wait(for: [expectation], timeout: 1.0)
    }
    
    func testViewModel_ShouldBindToEncryptionManagerSyncStatus() {
        let expectation = XCTestExpectation(description: "Sync status binding")
        
        // 监听同步状态变化
        viewModel.$syncStatus
            .dropFirst()
            .sink { status in
                XCTAssertEqual(status, .syncing,
                              "同步状态应该与模拟加密管理器同步")
                expectation.fulfill()
            }
            .store(in: &cancellables)
        
        // 触发模拟加密管理器状态变化
        mockEncryptionManager.syncStatus = .syncing
        mockEncryptionManager.objectWillChange.send()
        
        wait(for: [expectation], timeout: 1.0)
    }
    
    // MARK: - 配置管理测试
    
    func testSyncConfiguration_Update_ShouldApplyToEncryptionManager() {
        // 初始配置
        let initialConfig = viewModel.getSyncConfiguration()
        XCTAssertFalse(initialConfig.cloudSyncEnabled,
                      "初始配置应该禁用云同步")
        
        // 更新配置
        var newConfig = initialConfig
        newConfig.cloudSyncEnabled = true
        viewModel.updateSyncConfiguration(newConfig)
        
        // 验证配置已应用
        let updatedConfig = viewModel.getSyncConfiguration()
        XCTAssertTrue(updatedConfig.cloudSyncEnabled,
                     "更新配置后应该启用云同步")
    }
}

// MARK: - Mock 类

class MockHealthKitManager: HealthKitManager {
    var authorizationStatusToReturn: HKAuthorizationStatus = .notDetermined
    var didRequestAuthorization = false
    var todaySummaryToReturn: Double = 0.0
    var weeklyTrendToReturn: [Date: Double] = [:]
    var queryResults: [HealthDataSample] = []
    var queryError: Error?
    
    override func requestAuthorization(for dataTypes: [HealthDataType]) async -> HealthPermissionResult {
        didRequestAuthorization = true
        
        return HealthPermissionResult(
            requestedTypes: dataTypes,
            grantedTypes: authorizationStatusToReturn == .sharingAuthorized ? dataTypes : [],
            deniedTypes: authorizationStatusToReturn == .sharingDenied ? dataTypes : [],
            requestDate: Date()
        )
    }
    
    override func authorizationStatus(for dataType: HealthDataType) -> HKAuthorizationStatus {
        return authorizationStatusToReturn
    }
    
    override func queryTodaySummary(for dataType: HealthDataType) async throws -> Double {
        if let error = queryError {
            throw error
        }
        return todaySummaryToReturn
    }
    
    override func queryWeeklyTrend(for dataType: HealthDataType) async throws -> [Date: Double] {
        if let error = queryError {
            throw error
        }
        return weeklyTrendToReturn
    }
}

class MockHealthDataEncryptionManager: HealthDataEncryptionManager {
    override var syncStatus: CloudSyncStatus {
        get { return _syncStatus }
        set { _syncStatus = newValue }
    }
    
    private var _syncStatus: CloudSyncStatus = .disabled
    
    override func enableCloudSync(provider: CloudProvider = .icloud) {
        _syncStatus = .pending
    }
    
    override func disableCloudSync() {
        _syncStatus = .disabled
    }
}