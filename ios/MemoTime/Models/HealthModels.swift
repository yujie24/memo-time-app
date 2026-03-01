//
//  HealthModels.swift
//  MemoTime
//
//  HealthKit 数据模型与相关类型定义
//

import Foundation
import HealthKit

/// 健康数据类型枚举
enum HealthDataType: String, CaseIterable, Codable {
    case stepCount = "步数"
    case heartRate = "心率"
    case sleepAnalysis = "睡眠"
    case bodyMass = "体重"
    case activeEnergyBurned = "活动能量"
    case distanceWalkingRunning = "步行距离"
    case bloodPressureSystolic = "收缩压"
    case bloodPressureDiastolic = "舒张压"
    case bloodOxygenSaturation = "血氧"
    case respiratoryRate = "呼吸频率"
    
    /// 对应的 HKQuantityTypeIdentifier
    var hkIdentifier: HKQuantityTypeIdentifier? {
        switch self {
        case .stepCount:
            return .stepCount
        case .heartRate:
            return .heartRate
        case .sleepAnalysis:
            return .sleepAnalysis
        case .bodyMass:
            return .bodyMass
        case .activeEnergyBurned:
            return .activeEnergyBurned
        case .distanceWalkingRunning:
            return .distanceWalkingRunning
        case .bloodPressureSystolic:
            return .bloodPressureSystolic
        case .bloodPressureDiastolic:
            return .bloodPressureDiastolic
        case .bloodOxygenSaturation:
            return .bloodOxygenSaturation
        case .respiratoryRate:
            return .respiratoryRate
        }
    }
    
    /// 对应的 HKCategoryTypeIdentifier（睡眠）
    var hkCategoryIdentifier: HKCategoryTypeIdentifier? {
        switch self {
        case .sleepAnalysis:
            return .sleepAnalysis
        default:
            return nil
        }
    }
    
    /// 单位描述
    var unitDescription: String {
        switch self {
        case .stepCount:
            return "步"
        case .heartRate:
            return "次/分钟"
        case .sleepAnalysis:
            return "小时"
        case .bodyMass:
            return "kg"
        case .activeEnergyBurned:
            return "千卡"
        case .distanceWalkingRunning:
            return "公里"
        case .bloodPressureSystolic, .bloodPressureDiastolic:
            return "mmHg"
        case .bloodOxygenSaturation:
            return "%"
        case .respiratoryRate:
            return "次/分钟"
        }
    }
    
    /// 对应的 HKUnit
    var healthKitUnit: HKUnit? {
        switch self {
        case .stepCount:
            return .count()
        case .heartRate:
            return HKUnit(from: "count/min")
        case .sleepAnalysis:
            return .hour()
        case .bodyMass:
            return .gramUnit(with: .kilo)
        case .activeEnergyBurned:
            return .kilocalorie()
        case .distanceWalkingRunning:
            return .meterUnit(with: .kilo)
        case .bloodPressureSystolic, .bloodPressureDiastolic:
            return .millimeterOfMercury()
        case .bloodOxygenSaturation:
            return .percent()
        case .respiratoryRate:
            return HKUnit(from: "count/min")
        }
    }
    
    /// 是否为敏感数据（需要额外加密保护）
    var isSensitive: Bool {
        switch self {
        case .heartRate, .bloodPressureSystolic, .bloodPressureDiastolic,
             .bloodOxygenSaturation, .respiratoryRate, .bodyMass:
            return true
        default:
            return false
        }
    }
}

/// 健康数据样本
struct HealthDataSample: Codable, Identifiable {
    let id: UUID
    let dataType: HealthDataType
    let value: Double
    let startDate: Date
    let endDate: Date
    let sourceDevice: String?
    let metadata: [String: Any]?
    
    init(id: UUID = UUID(), dataType: HealthDataType, value: Double, 
         startDate: Date, endDate: Date, sourceDevice: String? = nil, metadata: [String: Any]? = nil) {
        self.id = id
        self.dataType = dataType
        self.value = value
        self.startDate = startDate
        self.endDate = endDate
        self.sourceDevice = sourceDevice
        self.metadata = metadata
    }
    
    /// 从 HKQuantitySample 转换
    init?(from sample: HKQuantitySample, dataType: HealthDataType) {
        guard let unit = dataType.healthKitUnit else {
            return nil
        }
        
        self.id = UUID(uuidString: sample.uuid.uuidString) ?? UUID()
        self.dataType = dataType
        self.value = sample.quantity.doubleValue(for: unit)
        self.startDate = sample.startDate
        self.endDate = sample.endDate
        self.sourceDevice = sample.sourceRevision.source.name
        self.metadata = sample.metadata
    }
    
    /// 从 HKCategorySample 转换（睡眠）
    init?(from sample: HKCategorySample, dataType: HealthDataType) {
        guard dataType == .sleepAnalysis else {
            return nil
        }
        
        let sleepHours = sample.endDate.timeIntervalSince(sample.startDate) / 3600.0
        
        self.id = UUID(uuidString: sample.uuid.uuidString) ?? UUID()
        self.dataType = dataType
        self.value = sleepHours
        self.startDate = sample.startDate
        self.endDate = sample.endDate
        self.sourceDevice = sample.sourceRevision.source.name
        self.metadata = sample.metadata
    }
    
    // MARK: - Codable
    
    enum CodingKeys: String, CodingKey {
        case id, dataType, value, startDate, endDate, sourceDevice, metadata
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(UUID.self, forKey: .id)
        dataType = try container.decode(HealthDataType.self, forKey: .dataType)
        value = try container.decode(Double.self, forKey: .value)
        startDate = try container.decode(Date.self, forKey: .startDate)
        endDate = try container.decode(Date.self, forKey: .endDate)
        sourceDevice = try container.decodeIfPresent(String.self, forKey: .sourceDevice)
        
        // 自定义 metadata 解码
        if let metadataData = try container.decodeIfPresent(Data.self, forKey: .metadata) {
            metadata = try JSONSerialization.jsonObject(with: metadataData, options: []) as? [String: Any]
        } else {
            metadata = nil
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(dataType, forKey: .dataType)
        try container.encode(value, forKey: .value)
        try container.encode(startDate, forKey: .startDate)
        try container.encode(endDate, forKey: .endDate)
        try container.encodeIfPresent(sourceDevice, forKey: .sourceDevice)
        
        // 自定义 metadata 编码
        if let metadata = metadata {
            let metadataData = try JSONSerialization.data(withJSONObject: metadata, options: [])
            try container.encode(metadataData, forKey: .metadata)
        }
    }
}

/// 健康数据摘要
struct HealthDataSummary: Codable {
    let date: Date
    var metrics: [HealthDataType: Double] = [:]
    
    /// 今日步数
    var steps: Double? {
        return metrics[.stepCount]
    }
    
    /// 平均心率
    var averageHeartRate: Double? {
        return metrics[.heartRate]
    }
    
    /// 睡眠时长（小时）
    var sleepHours: Double? {
        return metrics[.sleepAnalysis]
    }
    
    /// 体重（kg）
    var weight: Double? {
        return metrics[.bodyMass]
    }
    
    /// 活动能量（千卡）
    var activeEnergy: Double? {
        return metrics[.activeEnergyBurned]
    }
    
    /// 步行距离（公里）
    var walkingDistance: Double? {
        return metrics[.distanceWalkingRunning]
    }
}

/// 健康趋势数据
struct HealthTrendData: Codable {
    let period: DateInterval
    let dataType: HealthDataType
    let dailyValues: [Date: Double]
    let average: Double
    let max: Double
    let min: Double
    let trendDirection: TrendDirection
}

/// 趋势方向
enum TrendDirection: String, Codable {
    case increasing = "上升"
    case decreasing = "下降"
    case stable = "稳定"
    case fluctuating = "波动"
}

/// 健康建议
struct HealthRecommendation: Codable, Identifiable {
    let id: UUID
    let priority: Priority
    let category: RecommendationCategory
    let title: String
    let description: String
    let actionSteps: [String]
    let estimatedImpact: String
    let validUntil: Date?
    
    enum Priority: String, Codable {
        case high = "高优先级"
        case medium = "中优先级"
        case low = "低优先级"
    }
    
    enum RecommendationCategory: String, Codable {
        case activity = "活动"
        case nutrition = "营养"
        case sleep = "睡眠"
        case stress = "压力管理"
        case hydration = "水分"
        case general = "一般健康"
    }
}

/// 加密的健康数据存储结构
struct EncryptedHealthData: Codable {
    let encryptedData: Data
    let encryptionAlgorithm: EncryptionAlgorithm
    let keyDerivationParams: KeyDerivationParams
    let dataType: HealthDataType
    let sampleId: UUID
    let createdAt: Date
    
    enum EncryptionAlgorithm: String, Codable {
        case aes256GCM = "AES-256-GCM"
        case chacha20Poly1305 = "ChaCha20-Poly1305"
    }
}

/// 密钥派生参数
struct KeyDerivationParams: Codable {
    let algorithm: String
    let salt: Data
    let iterations: Int
    let keyLength: Int
}

/// 云同步状态
enum CloudSyncStatus: String, Codable {
    case pending = "待同步"
    case syncing = "同步中"
    case synced = "已同步"
    case error = "同步错误"
    case disabled = "已禁用"
}

/// 权限请求结果
struct HealthPermissionResult: Codable {
    let requestedTypes: [HealthDataType]
    let grantedTypes: [HealthDataType]
    let deniedTypes: [HealthDataType]
    let requestDate: Date
    
    var isFullyGranted: Bool {
        return grantedTypes.count == requestedTypes.count
    }
    
    var isPartiallyGranted: Bool {
        return grantedTypes.count > 0 && grantedTypes.count < requestedTypes.count
    }
    
    var isDenied: Bool {
        return grantedTypes.isEmpty
    }
}

/// 健康数据同步配置
struct HealthSyncConfiguration: Codable {
    var enabledDataTypes: [HealthDataType] = [.stepCount, .heartRate, .sleepAnalysis]
    var syncFrequency: SyncFrequency = .hourly
    var retentionPeriod: RetentionPeriod = .threeMonths
    var cloudSyncEnabled: Bool = false
    
    enum SyncFrequency: String, Codable {
        case immediate = "实时"
        case hourly = "每小时"
        case daily = "每天"
        case weekly = "每周"
    }
    
    enum RetentionPeriod: String, Codable {
        case oneMonth = "一个月"
        case threeMonths = "三个月"
        case sixMonths = "六个月"
        case oneYear = "一年"
        case unlimited = "无限制"
    }
}