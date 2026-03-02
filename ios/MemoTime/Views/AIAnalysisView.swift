import SwiftUI

/// AI分析视图
/// 显示AI生成的洞察和建议
struct AIAnalysisView: View {
    @ObservedObject var analysisManager = AIAnalysisManager.shared
    @State private var analysisResult: AIAnalysisResponse?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingSettings = false
    
    // 分析天数选项
    private let analysisDaysOptions = [3, 7, 14, 30]
    @State private var selectedDays = 7
    
    var body: some View {
        NavigationView {
            ScrollView {
                VStack(spacing: 20) {
                    // 控制面板
                    controlPanel
                    
                    if isLoading {
                        loadingView
                    } else if let error = errorMessage {
                        errorView(message: error)
                    } else if let result = analysisResult {
                        analysisContentView(result: result)
                    } else {
                        emptyStateView
                    }
                }
                .padding()
            }
            .navigationTitle("AI分析")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    settingsButton
                }
            }
            .sheet(isPresented: $showingSettings) {
                AIAnalysisSettingsView()
            }
        }
        .onAppear {
            loadCachedAnalysis()
        }
    }
    
    // MARK: - 子视图
    
    /// 控制面板
    private var controlPanel: some View {
        VStack(spacing: 12) {
            HStack {
                Text("分析最近")
                    .font(.subheadline)
                
                Picker("天数", selection: $selectedDays) {
                    ForEach(analysisDaysOptions, id: \.self) { days in
                        Text("\(days)天").tag(days)
                    }
                }
                .pickerStyle(.segmented)
                
                Spacer()
            }
            
            Button(action: performAnalysis) {
                HStack {
                    Image(systemName: "brain.head.profile")
                    Text("开始分析")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Color.blue)
                .foregroundColor(.white)
                .cornerRadius(10)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 加载视图
    private var loadingView: some View {
        VStack(spacing: 16) {
            ProgressView()
                .scaleEffect(1.5)
            
            Text("正在分析数据...")
                .font(.headline)
                .foregroundColor(.secondary)
            
            Text("正在收集各模块数据并生成洞察")
                .font(.caption)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 错误视图
    private func errorView(message: String) -> some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 50))
                .foregroundColor(.orange)
            
            Text("分析失败")
                .font(.headline)
            
            Text(message)
                .font(.subheadline)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
            
            Button("重试") {
                performAnalysis()
            }
            .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 空状态视图
    private var emptyStateView: some View {
        VStack(spacing: 20) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 60))
                .foregroundColor(.blue.opacity(0.7))
            
            VStack(spacing: 8) {
                Text("尚未进行分析")
                    .font(.title2)
                    .fontWeight(.semibold)
                
                Text("点击\"开始分析\"按钮，获取AI生成的个人生产力洞察和建议")
                    .font(.body)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal)
            
            VStack(alignment: .leading, spacing: 12) {
                FeatureRow(
                    icon: "link",
                    title: "链接分类分析",
                    description: "了解您关注的领域分布"
                )
                
                FeatureRow(
                    icon: "creditcard",
                    title: "消费习惯洞察",
                    description: "发现潜在的节省机会"
                )
                
                FeatureRow(
                    icon: "calendar",
                    title: "日程安排优化",
                    description: "提高时间利用效率"
                )
                
                FeatureRow(
                    icon: "heart.fill",
                    title: "健康数据趋势",
                    description: "跟踪健康状况变化"
                )
            }
            .padding()
        }
        .frame(maxWidth: .infinity, minHeight: 400)
        .padding()
    }
    
    /// 分析内容视图
    private func analysisContentView(result: AIAnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            // 性能指标
            performanceMetricsView(result: result)
            
            // 关键洞察
            insightsSection(result: result)
            
            // 建议
            recommendationsSection(result: result)
            
            // 原始分析
            rawAnalysisSection(result: result)
        }
    }
    
    /// 性能指标视图
    private func performanceMetricsView(result: AIAnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("分析性能")
                .font(.headline)
            
            HStack(spacing: 20) {
                MetricCard(
                    title: "响应时间",
                    value: String(format: "%.2fs", result.performanceMetrics.responseTime),
                    icon: "clock",
                    color: .green
                )
                
                MetricCard(
                    title: "成功率",
                    value: result.performanceMetrics.success ? "100%" : "0%",
                    icon: result.performanceMetrics.success ? "checkmark.circle" : "xmark.circle",
                    color: result.performanceMetrics.success ? .green : .red
                )
                
                if let modelUsed = result.performanceMetrics.modelUsed {
                    MetricCard(
                        title: "AI模型",
                        value: modelUsed,
                        icon: "cpu",
                        color: .blue
                    )
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 洞察部分
    private func insightsSection(result: AIAnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("关键洞察")
                    .font(.headline)
                
                Spacer()
                
                Text("\(result.analysisResults.insights.count)条")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if result.analysisResults.insights.isEmpty {
                Text("暂无洞察")
                    .foregroundColor(.secondary)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
            } else {
                ForEach(Array(result.analysisResults.insights.enumerated()), id: \.offset) { index, insight in
                    InsightCard(insight: insight, index: index)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 建议部分
    private func recommendationsSection(result: AIAnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("改进建议")
                    .font(.headline)
                
                Spacer()
                
                Text("\(result.analysisResults.recommendations.count)条")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            if result.analysisResults.recommendations.isEmpty {
                Text("暂无建议")
                    .foregroundColor(.secondary)
                    .padding()
                    .frame(maxWidth: .infinity)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
            } else {
                ForEach(Array(result.analysisResults.recommendations.enumerated()), id: \.offset) { index, recommendation in
                    RecommendationCard(recommendation: recommendation, index: index)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 原始分析部分
    private func rawAnalysisSection(result: AIAnalysisResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("完整分析")
                    .font(.headline)
                
                Spacer()
            }
            
            ScrollView {
                Text(result.analysisResults.rawAnalysis)
                    .font(.body)
                    .padding()
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(.systemGray6))
                    .cornerRadius(8)
            }
            .frame(maxHeight: 300)
        }
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(12)
        .shadow(color: Color.black.opacity(0.05), radius: 5, x: 0, y: 2)
    }
    
    /// 设置按钮
    private var settingsButton: some View {
        Button(action: { showingSettings = true }) {
            Image(systemName: "gear")
        }
    }
    
    // MARK: - 方法
    
    /// 加载缓存的Analysis
    private func loadCachedAnalysis() {
        // 这里可以从本地缓存加载最近的分析结果
        // 简化实现
    }
    
    /// 执行分析
    private func performAnalysis() {
        isLoading = true
        errorMessage = nil
        
        analysisManager.analyzeRecentActivity(days: selectedDays) { result in
            isLoading = false
            
            switch result {
            case .success(let response):
                analysisResult = response
                // 保存到缓存
                saveAnalysisToCache(response)
                
            case .failure(let error):
                errorMessage = error.localizedDescription
            }
        }
    }
    
    /// 保存分析结果到缓存
    private func saveAnalysisToCache(_ result: AIAnalysisResponse) {
        // 简化实现：实际应用中可以保存到UserDefaults或文件
        UserDefaults.standard.set(Date().timeIntervalSince1970, forKey: "last_analysis_timestamp")
    }
}

// MARK: - 子组件

/// 功能行
struct FeatureRow: View {
    let icon: String
    let title: String
    let description: String
    
    var body: some View {
        HStack(spacing: 16) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundColor(.blue)
                .frame(width: 40, height: 40)
                .background(Color.blue.opacity(0.1))
                .cornerRadius(8)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(title)
                    .font(.headline)
                
                Text(description)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Spacer()
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
}

/// 指标卡片
struct MetricCard: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
        }
        .frame(maxWidth: .infinity)
        .padding()
        .background(Color(.systemBackground))
        .cornerRadius(10)
        .shadow(color: Color.black.opacity(0.05), radius: 3, x: 0, y: 2)
    }
}

/// 洞察卡片
struct InsightCard: View {
    let insight: Insight
    let index: Int
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("洞察 \(index + 1)")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundColor(.blue)
                
                Spacer()
                
                if insight.confidence > 0.8 {
                    Label("高置信度", systemImage: "star.fill")
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
            
            Text(insight.content)
                .font(.body)
                .lineLimit(4)
            
            if let supportingData = insight.supportingData, !supportingData.isEmpty {
                HStack {
                    Text("支持数据:")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    ForEach(Array(supportingData.keys.prefix(3)), id: \.self) { key in
                        if let value = supportingData[key] {
                            Text("\(key): \(String(describing: value))")
                                .font(.caption)
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color(.systemGray6))
                                .cornerRadius(4)
                        }
                    }
                    
                    if supportingData.keys.count > 3 {
                        Text("+\(supportingData.keys.count - 3)更多")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
}

/// 建议卡片
struct RecommendationCard: View {
    let recommendation: Recommendation
    let index: Int
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                // 优先级指示器
                priorityIndicator
                
                Text("建议 \(index + 1)")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                
                Spacer()
            }
            
            Text(recommendation.description)
                .font(.body)
            
            HStack {
                Text("预期影响:")
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Text(recommendation.estimatedImpact)
                    .font(.caption)
                    .foregroundColor(.green)
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(10)
    }
    
    /// 优先级指示器
    private var priorityIndicator: some View {
        Group {
            switch recommendation.priority {
            case "high":
                Circle()
                    .fill(Color.red)
                    .frame(width: 12, height: 12)
            case "medium":
                Circle()
                    .fill(Color.orange)
                    .frame(width: 12, height: 12)
            case "low":
                Circle()
                    .fill(Color.green)
                    .frame(width: 12, height: 12)
            default:
                Circle()
                    .fill(Color.gray)
                    .frame(width: 12, height: 12)
            }
        }
    }
}

/// AI分析设置视图
struct AIAnalysisSettingsView: View {
    @Environment(\.dismiss) var dismiss
    @ObservedObject var analysisManager = AIAnalysisManager.shared
    
    @State private var apiProvider = AIAnalysisManager.AIAnalysisConfiguration.APIProvider.deepseek
    @State private var apiKey = ""
    @State private var cacheDuration = 3600.0
    @State private var enableAutoAnalysis = true
    @State private var analysisSchedule = AIAnalysisManager.AIAnalysisConfiguration.AnalysisSchedule.weekly
    
    var body: some View {
        NavigationView {
            Form {
                Section(header: Text("API配置")) {
                    Picker("API提供商", selection: $apiProvider) {
                        Text("DeepSeek").tag(AIAnalysisManager.AIAnalysisConfiguration.APIProvider.deepseek)
                        Text("Coze").tag(AIAnalysisManager.AIAnalysisConfiguration.APIProvider.coze)
                    }
                    
                    SecureField("API密钥", text: $apiKey)
                        .textContentType(.password)
                }
                
                Section(header: Text("分析设置")) {
                    Toggle("自动分析", isOn: $enableAutoAnalysis)
                    
                    Picker("分析频率", selection: $analysisSchedule) {
                        Text("每日").tag(AIAnalysisManager.AIAnalysisConfiguration.AnalysisSchedule.daily)
                        Text("每周").tag(AIAnalysisManager.AIAnalysisConfiguration.AnalysisSchedule.weekly)
                        Text("每月").tag(AIAnalysisManager.AIAnalysisConfiguration.AnalysisSchedule.monthly)
                    }
                    .disabled(!enableAutoAnalysis)
                    
                    HStack {
                        Text("缓存时长")
                        Spacer()
                        Text("\(Int(cacheDuration / 3600))小时")
                            .foregroundColor(.secondary)
                    }
                }
                
                Section {
                    Button("保存设置") {
                        saveSettings()
                        dismiss()
                    }
                    .frame(maxWidth: .infinity)
                }
            }
            .navigationTitle("AI分析设置")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("取消") {
                        dismiss()
                    }
                }
            }
            .onAppear(loadSettings)
        }
    }
    
    private func loadSettings() {
        let config = analysisManager.shared.configuration
        apiProvider = config.apiProvider
        apiKey = config.apiKey
        cacheDuration = config.cacheDuration
        enableAutoAnalysis = config.enableAutoAnalysis
        analysisSchedule = config.analysisSchedule
    }
    
    private func saveSettings() {
        let newConfig = AIAnalysisManager.AIAnalysisConfiguration(
            apiProvider: apiProvider,
            apiKey: apiKey,
            cacheDuration: cacheDuration,
            enableAutoAnalysis: enableAutoAnalysis,
            analysisSchedule: analysisSchedule
        )
        
        analysisManager.updateConfiguration(newConfig)
    }
}

// MARK: - 预览
struct AIAnalysisView_Previews: PreviewProvider {
    static var previews: some View {
        AIAnalysisView()
    }
}