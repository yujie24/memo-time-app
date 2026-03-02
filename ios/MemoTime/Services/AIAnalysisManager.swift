import Foundation
import Combine

/// AI分析错误类型
enum AIAnalysisError: Error, LocalizedError {
    case apiKeyMissing
    case networkError(Error)
    case invalidResponse
    case analysisFailed(String)
    
    var errorDescription: String? {
        switch self {
        case .apiKeyMissing:
            return "API密钥未配置，请在设置中配置AI服务密钥"
        case .networkError(let error):
            return "网络错误: \(error.localizedDescription)"
        case .invalidResponse:
            return "服务器返回无效响应"
        case .analysisFailed(let reason):
            return "分析失败: \(reason)"
        }
    }
}

/// AI分析请求数据
struct AIAnalysisRequest: Codable {
    let requestId: String
    let timestamp: Int
    let dataContext: DataContext
    let linkSummary: LinkSummary?
    let financialSummary: FinancialSummary?
    let calendarSummary: CalendarSummary?
    let healthSummary: HealthSummary?
    let userPreferences: UserPreferences
    
    struct DataContext: Codable {
        let timeRange: String
        let dataScope: DataScope
    }
    
    struct DataScope: Codable {
        let links: Bool
        let financial: Bool
        let calendar: Bool
        let health: Bool
    }
}

/// AI分析响应数据
struct AIAnalysisResponse: Codable {
    let responseId: String
    let requestId: String
    let analysisResults: AnalysisResults
    let performanceMetrics: PerformanceMetrics
    
    struct AnalysisResults: Codable {
        let insights: [Insight]
        let recommendations: [Recommendation]
        let rawAnalysis: String
        
        enum CodingKeys: String, CodingKey {
            case insights, recommendations
            case rawAnalysis = "raw_analysis"
        }
    }
    
    struct PerformanceMetrics: Codable {
        let responseTime: Double
        let success: Bool
        let modelUsed: String?
        
        enum CodingKeys: String, CodingKey {
            case responseTime = "response_time"
            case success
            case modelUsed = "model_used"
        }
    }
}

/// 洞察信息
struct Insight: Codable {
    let type: String
    let confidence: Double
    let content: String
    let supportingData: [String: Any]?
    
    enum CodingKeys: String, CodingKey {
        case type, confidence, content
        case supportingData = "supporting_data"
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decode(String.self, forKey: .type)
        confidence = try container.decode(Double.self, forKey: .confidence)
        content = try container.decode(String.self, forKey: .content)
        
        // 支持灵活的支持数据格式
        if let dataContainer = try? container.decodeIfPresent([String: AnyCodable].self, forKey: .supportingData) {
            supportingData = dataContainer.mapValues { $0.value }
        } else {
            supportingData = nil
        }
    }
}

/// 建议信息
struct Recommendation: Codable {
    let priority: String  // "high", "medium", "low"
    let action: String
    let description: String
    let estimatedImpact: String
    
    enum CodingKeys: String, CodingKey {
        case priority, action, description
        case estimatedImpact = "estimated_impact"
    }
}

/// 链接数据摘要
struct LinkSummary: Codable {
    let totalCount: Int
    let categoryDistribution: [String: Int]
    let recentTrend: [DailyTrend]
    let topDomains: [String]
    
    enum CodingKeys: String, CodingKey {
        case totalCount = "total_count"
        case categoryDistribution = "category_distribution"
        case recentTrend = "recent_trend"
        case topDomains = "top_domains"
    }
}

/// 财务数据摘要
struct FinancialSummary: Codable {
    let totalSpending: Double
    let averageDaily: Double
    let topCategories: [TopCategory]
    let recordCount: Int
    
    enum CodingKeys: String, CodingKey {
        case totalSpending = "total_spending"
        case averageDaily = "average_daily"
        case topCategories = "top_categories"
        case recordCount = "record_count"
    }
    
    struct TopCategory: Codable {
        let category: String
        let amount: Double
        let percentage: Double
    }
}

/// 日历数据摘要
struct CalendarSummary: Codable {
    let totalEvents: Int
    let eventDistribution: [String: Int]
    let busyPeriods: [TimePeriod]
    let freeTimeBlocks: [TimePeriod]
    let dataSource: String
    
    enum CodingKeys: String, CodingKey {
        case totalEvents = "total_events"
        case eventDistribution = "event_distribution"
        case busyPeriods = "busy_periods"
        case freeTimeBlocks = "free_time_blocks"
        case dataSource = "data_source"
    }
}

/// 健康数据摘要
struct HealthSummary: Codable {
    let dailyStepsAvg: Int
    let heartRateAvg: Int
    let sleepHoursAvg: Double
    let trendDirection: String
    let detailedMetrics: [String: AnyCodable]?
    let dataSource: String
    
    enum CodingKeys: String, CodingKey {
        case dailyStepsAvg = "daily_steps_avg"
        case heartRateAvg = "heart_rate_avg"
        case sleepHoursAvg = "sleep_hours_avg"
        case trendDirection = "trend_direction"
        case detailedMetrics = "detailed_metrics"
        case dataSource = "data_source"
    }
}

/// 用户偏好设置
struct UserPreferences: Codable {
    let analysisDepth: String  // "basic", "standard", "detailed"
    let reportFormat: String  // "bullet_points", "detailed", "visual"
    let language: String  // "zh-CN", "en-US"
    
    enum CodingKeys: String, CodingKey {
        case analysisDepth = "analysis_depth"
        case reportFormat = "report_format"
        case language
    }
}

/// 通用可编码类型，用于处理灵活的数据结构
struct AnyCodable: Codable {
    let value: Any
    
    init<T>(_ value: T?) {
        self.value = value ?? ()
    }
    
    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let value = try? container.decode(Bool.self) {
            self.value = value
        } else if let value = try? container.decode(Int.self) {
            self.value = value
        } else if let value = try? container.decode(Double.self) {
            self.value = value
        } else if let value = try? container.decode(String.self) {
            self.value = value
        } else if let value = try? container.decode([String: AnyCodable].self) {
            self.value = value.mapValues { $0.value }
        } else if let value = try? container.decode([AnyCodable].self) {
            self.value = value.map { $0.value }
        } else {
            self.value = ()
        }
    }
    
    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        switch value {
        case let value as Bool:
            try container.encode(value)
        case let value as Int:
            try container.encode(value)
        case let value as Double:
            try container.encode(value)
        case let value as String:
            try container.encode(value)
        case let value as [String: Any]:
            let encoded = value.mapValues { AnyCodable($0) }
            try container.encode(encoded)
        case let value as [Any]:
            let encoded = value.map { AnyCodable($0) }
            try container.encode(encoded)
        default:
            try container.encodeNil()
        }
    }
}

/// AI分析管理器
/// 负责协调数据收集、脱敏处理和AI分析
class AIAnalysisManager: ObservableObject {
    
    // MARK: - 单例模式
    
    static let shared = AIAnalysisManager()
    
    private init() {
        setupConfiguration()
    }
    
    // MARK: - 配置管理
    
    private var configuration: AIAnalysisConfiguration
    
    private func setupConfiguration() {
        // 从UserDefaults加载配置
        if let savedConfig = UserDefaults.standard.data(forKey: "ai_analysis_config"),
           let decoded = try? JSONDecoder().decode(AIAnalysisConfiguration.self, from: savedConfig) {
            configuration = decoded
        } else {
            // 默认配置
            configuration = AIAnalysisConfiguration(
                apiProvider: .deepseek,
                apiKey: "",
                cacheDuration: 3600,
                enableAutoAnalysis: true,
                analysisSchedule: .weekly
            )
        }
    }
    
    func updateConfiguration(_ config: AIAnalysisConfiguration) {
        configuration = config
        saveConfiguration()
    }
    
    private func saveConfiguration() {
        if let encoded = try? JSONEncoder().encode(configuration) {
            UserDefaults.standard.set(encoded, forKey: "ai_analysis_config")
        }
    }
    
    // MARK: - 数据分析
    
    /// 分析最近活动
    /// - Parameters:
    ///   - days: 分析的天数
    ///   - completion: 完成回调，返回分析结果或错误
    func analyzeRecentActivity(days: Int = 7, completion: @escaping (Result<AIAnalysisResponse, AIAnalysisError>) -> Void) {
        // 检查API密钥
        guard !configuration.apiKey.isEmpty else {
            completion(.failure(.apiKeyMissing))
            return
        }
        
        // 异步执行
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                // 1. 收集数据
                let collectedData = try self.collectRecentData(days: days)
                
                // 2. 构建请求
                let request = self.buildAnalysisRequest(data: collectedData, days: days)
                
                // 3. 发送请求
                self.sendAnalysisRequest(request) { result in
                    DispatchQueue.main.async {
                        completion(result)
                    }
                }
                
            } catch let error as AIAnalysisError {
                DispatchQueue.main.async {
                    completion(.failure(error))
                }
            } catch {
                DispatchQueue.main.async {
                    completion(.failure(.analysisFailed(error.localizedDescription)))
                }
            }
        }
    }
    
    /// 收集最近数据
    private func collectRecentData(days: Int) throws -> CollectedData {
        var collectedData = CollectedData()
        
        // 收集财务数据
        if let financialData = try? FinancialDataManager.shared.getRecentSummary(days: days) {
            collectedData.financial = financialData
        }
        
        // 收集链接数据
        if let linksData = try? LinkProcessingManager.shared.getRecentSummary(days: days) {
            collectedData.links = linksData
        }
        
        // 收集日历数据
        if let calendarData = try? CalendarSyncManager.shared.getRecentSummary(days: days) {
            collectedData.calendar = calendarData
        }
        
        // 收集健康数据
        if let healthData = try? HealthKitManager.shared.getRecentSummary(days: days) {
            collectedData.health = healthData
        }
        
        return collectedData
    }
    
    /// 构建分析请求
    private func buildAnalysisRequest(data: CollectedData, days: Int) -> AIAnalysisRequest {
        let requestId = "req_\(Int(Date().timeIntervalSince1970))_\(UUID().uuidString.prefix(8))"
        
        let dataContext = AIAnalysisRequest.DataContext(
            timeRange: "recent_\(days)_days",
            dataScope: AIAnalysisRequest.DataScope(
                links: data.links != nil,
                financial: data.financial != nil,
                calendar: data.calendar != nil,
                health: data.health != nil
            )
        )
        
        // 脱敏处理
        let anonymizedLinkSummary = data.links.map { self.anonymizeLinkData($0) }
        let anonymizedFinancialSummary = data.financial.map { self.anonymizeFinancialData($0) }
        let anonymizedCalendarSummary = data.calendar.map { self.anonymizeCalendarData($0) }
        let anonymizedHealthSummary = data.health.map { self.anonymizeHealthData($0) }
        
        // 用户偏好
        let userPreferences = UserPreferences(
            analysisDepth: "standard",
            reportFormat: "bullet_points",
            language: "zh-CN"
        )
        
        return AIAnalysisRequest(
            requestId: requestId,
            timestamp: Int(Date().timeIntervalSince1970),
            dataContext: dataContext,
            linkSummary: anonymizedLinkSummary,
            financialSummary: anonymizedFinancialSummary,
            calendarSummary: anonymizedCalendarSummary,
            healthSummary: anonymizedHealthSummary,
            userPreferences: userPreferences
        )
    }
    
    /// 发送分析请求
    private func sendAnalysisRequest(_ request: AIAnalysisRequest, completion: @escaping (Result<AIAnalysisResponse, AIAnalysisError>) -> Void) {
        let url: URL
        let headers: [String: String]
        let body: [String: Any]
        
        switch configuration.apiProvider {
        case .deepseek:
            url = URL(string: "https://api.deepseek.com/chat/completions")!
            headers = [
                "Authorization": "Bearer \(configuration.apiKey)",
                "Content-Type": "application/json"
            ]
            
            // DeepSeek API格式
            body = [
                "model": "deepseek-chat",
                "messages": [
                    [
                        "role": "system",
                        "content": "你是一个个人生产力分析助手。请基于用户提供的数据，提供简明、有用的洞察和建议。"
                    ],
                    [
                        "role": "user",
                        "content": "请分析以下个人生产力数据：\n\n\(self.formatRequestForAI(request))\n\n请提供分析结果。"
                    ]
                ],
                "temperature": 0.3,
                "max_tokens": 2000
            ]
            
        case .coze:
            // Coze API实现类似
            url = URL(string: "https://api.coze.com/v1/chat/completions")!
            headers = [
                "Authorization": "Bearer \(configuration.apiKey)",
                "Content-Type": "application/json"
            ]
            body = [:] // 简化实现
        }
        
        var urlRequest = URLRequest(url: url)
        urlRequest.httpMethod = "POST"
        headers.forEach { key, value in
            urlRequest.setValue(value, forHTTPHeaderField: key)
        }
        
        do {
            urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            completion(.failure(.analysisFailed("请求数据序列化失败")))
            return
        }
        
        let task = URLSession.shared.dataTask(with: urlRequest) { data, response, error in
            if let error = error {
                completion(.failure(.networkError(error)))
                return
            }
            
            guard let data = data else {
                completion(.failure(.invalidResponse))
                return
            }
            
            do {
                // 解析响应
                let response = try JSONDecoder().decode(AIAnalysisResponse.self, from: data)
                completion(.success(response))
            } catch {
                completion(.failure(.invalidResponse))
            }
        }
        
        task.resume()
    }
    
    // MARK: - 脱敏处理
    
    private func anonymizeLinkData(_ data: LinkData) -> LinkSummary {
        // 实际实现中这里会有更复杂的脱敏逻辑
        return LinkSummary(
            totalCount: data.totalCount,
            categoryDistribution: data.categoryDistribution,
            recentTrend: data.recentTrend.map { DailyTrend(date: $0.date, count: $0.count) },
            topDomains: data.topDomains.map { domain in
                // 泛化域名
                let components = domain.split(separator: ".")
                if components.count > 2 {
                    return "\(components[components.count-2]).\(components.last!)"
                }
                return domain
            }
        )
    }
    
    private func anonymizeFinancialData(_ data: FinancialData) -> FinancialSummary {
        // 金额取整处理
        let roundedTotal = round(data.totalSpending / 100) * 100
        let roundedAverage = round(data.averageDaily / 10) * 10
        
        return FinancialSummary(
            totalSpending: roundedTotal,
            averageDaily: roundedAverage,
            topCategories: data.topCategories.map { category in
                FinancialSummary.TopCategory(
                    category: category.category,
                    amount: round(category.amount / 10) * 10,
                    percentage: category.percentage
                )
            },
            recordCount: data.recordCount
        )
    }
    
    private func anonymizeCalendarData(_ data: CalendarData) -> CalendarSummary {
        // 移除具体事件标题
        return CalendarSummary(
            totalEvents: data.totalEvents,
            eventDistribution: data.eventDistribution,
            busyPeriods: data.busyPeriods,
            freeTimeBlocks: data.freeTimeBlocks,
            dataSource: "real"
        )
    }
    
    private func anonymizeHealthData(_ data: HealthData) -> HealthSummary {
        // 健康数据精度处理
        return HealthSummary(
            dailyStepsAvg: (data.dailyStepsAvg / 100) * 100,
            heartRateAvg: (data.heartRateAvg / 5) * 5,
            sleepHoursAvg: round(data.sleepHoursAvg * 10) / 10,
            trendDirection: data.trendDirection,
            detailedMetrics: nil, // 简化处理
            dataSource: "real"
        )
    }
    
    // MARK: - 辅助方法
    
    private func formatRequestForAI(_ request: AIAnalysisRequest) -> String {
        let encoder = JSONEncoder()
        encoder.outputFormatting = .prettyPrinted
        
        do {
            let jsonData = try encoder.encode(request)
            return String(data: jsonData, encoding: .utf8) ?? "无法格式化请求数据"
        } catch {
            return "请求数据格式化失败"
        }
    }
    
    // MARK: - 配置类型
    
    struct AIAnalysisConfiguration: Codable {
        var apiProvider: APIProvider
        var apiKey: String
        var cacheDuration: TimeInterval
        var enableAutoAnalysis: Bool
        var analysisSchedule: AnalysisSchedule
        
        enum APIProvider: String, Codable {
            case deepseek = "deepseek"
            case coze = "coze"
        }
        
        enum AnalysisSchedule: String, Codable {
            case daily = "daily"
            case weekly = "weekly"
            case monthly = "monthly"
        }
    }
    
    // MARK: - 内部数据类型
    
    private struct CollectedData {
        var financial: FinancialData?
        var links: LinkData?
        var calendar: CalendarData?
        var health: HealthData?
    }
    
    private struct FinancialData {
        let totalSpending: Double
        let averageDaily: Double
        let topCategories: [FinancialTopCategory]
        let recordCount: Int
        
        struct FinancialTopCategory {
            let category: String
            let amount: Double
            let percentage: Double
        }
    }
    
    private struct LinkData {
        let totalCount: Int
        let categoryDistribution: [String: Int]
        let recentTrend: [DailyTrendInternal]
        let topDomains: [String]
    }
    
    private struct CalendarData {
        let totalEvents: Int
        let eventDistribution: [String: Int]
        let busyPeriods: [TimePeriod]
        let freeTimeBlocks: [TimePeriod]
    }
    
    private struct HealthData {
        let dailyStepsAvg: Int
        let heartRateAvg: Int
        let sleepHoursAvg: Double
        let trendDirection: String
    }
    
    private struct DailyTrendInternal {
        let date: String
        let count: Int
    }
    
    struct TimePeriod: Codable {
        let start: Int
        let end: Int
        let durationHours: Double
        
        enum CodingKeys: String, CodingKey {
            case start, end
            case durationHours = "duration_hours"
        }
    }
    
    struct DailyTrend: Codable {
        let date: String
        let count: Int
    }
}