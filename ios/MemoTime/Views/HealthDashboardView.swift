//
//  HealthDashboardView.swift
//  MemoTime
//
//  健康数据面板主视图
//

import SwiftUI
import Charts

struct HealthDashboardView: View {
    
    // MARK: - Properties
    
    @StateObject private var viewModel = HealthDashboardViewModel()
    @State private var showingSettings = false
    @State private var showingError = false
    @State private var lastRefreshTime = Date()
    
    // MARK: - Body
    
    var body: some View {
        NavigationStack {
            ZStack {
                // 背景
                Color(.systemGroupedBackground)
                    .ignoresSafeArea()
                
                if viewModel.isLoading {
                    loadingView
                } else if let error = viewModel.error {
                    errorView(error)
                } else {
                    contentView
                }
            }
            .navigationTitle("健康数据")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: refreshData) {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(.accentColor)
                    }
                    .disabled(viewModel.isLoading)
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { showingSettings = true }) {
                        Image(systemName: "gearshape")
                            .foregroundColor(.accentColor)
                    }
                }
            }
            .sheet(isPresented: $showingSettings) {
                HealthSettingsView(viewModel: viewModel)
            }
            .onAppear {
                if viewModel.authorizationStatus == .notDetermined || viewModel.healthSummary == nil {
                    Task {
                        await viewModel.loadHealthData()
                    }
                }
            }
            .refreshable {
                await viewModel.loadHealthData()
            }
            .onChange(of: viewModel.error) { error in
                showingError = error != nil
            }
            .alert("错误", isPresented: $showingError, presenting: viewModel.error) { _ in
                Button("确定") {
                    viewModel.error = nil
                }
            } message: { error in
                Text(error.localizedDescription)
            }
        }
    }
    
    // MARK: - Subviews
    
    private var loadingView: some View {
        VStack(spacing: 20) {
            ProgressView()
                .scaleEffect(1.5)
            
            Text("加载健康数据...")
                .font(.headline)
                .foregroundColor(.secondary)
        }
    }
    
    private func errorView(_ error: Error) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "heart.slash")
                .font(.system(size: 60))
                .foregroundColor(.red)
            
            Text("无法加载健康数据")
                .font(.title2)
                .fontWeight(.semibold)
            
            Text(error.localizedDescription)
                .font(.body)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
            
            Button("重试") {
                refreshData()
            }
            .buttonStyle(.borderedProminent)
            .padding(.top)
        }
        .padding()
    }
    
    private var contentView: some View {
        ScrollView {
            VStack(spacing: 20) {
                // 1. 健康概览卡片
                HealthOverviewCard(viewModel: viewModel)
                
                // 2. 趋势分析图表
                if viewModel.stepTrend != nil ||
                   viewModel.heartRateTrend != nil ||
                   viewModel.sleepTrend != nil {
                    HealthTrendCharts(viewModel: viewModel)
                }
                
                // 3. 健康建议
                if !viewModel.recommendations.isEmpty {
                    HealthRecommendationsView(recommendations: viewModel.recommendations)
                }
                
                // 4. 存储状态
                if let stats = viewModel.storageStats {
                    StorageStatusView(stats: stats)
                }
                
                // 底部间距
                Color.clear.frame(height: 50)
            }
            .padding()
        }
    }
    
    // MARK: - Actions
    
    private func refreshData() {
        Task {
            await viewModel.loadHealthData()
            lastRefreshTime = Date()
        }
    }
}

// MARK: - 健康概览卡片

struct HealthOverviewCard: View {
    @ObservedObject var viewModel: HealthDashboardViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 标题
            HStack {
                Image(systemName: "heart.fill")
                    .foregroundColor(.red)
                
                Text("健康概览")
                    .font(.headline)
                
                Spacer()
                
                Text(Date(), style: .date)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // 指标网格
            LazyVGrid(columns: [
                GridItem(.flexible()),
                GridItem(.flexible()),
                GridItem(.flexible())
            ], spacing: 16) {
                if let steps = viewModel.healthSummary?.steps {
                    HealthMetricCard(
                        title: "步数",
                        value: Int(steps),
                        unit: "步",
                        icon: "figure.walk",
                        color: .blue,
                        trend: viewModel.stepTrend?.trendDirection
                    )
                }
                
                if let heartRate = viewModel.healthSummary?.averageHeartRate {
                    HealthMetricCard(
                        title: "心率",
                        value: Int(heartRate),
                        unit: "次/分钟",
                        icon: "heart",
                        color: .red,
                        trend: viewModel.heartRateTrend?.trendDirection
                    )
                }
                
                if let sleepHours = viewModel.healthSummary?.sleepHours {
                    HealthMetricCard(
                        title: "睡眠",
                        value: sleepHours,
                        unit: "小时",
                        icon: "moon.zzz.fill",
                        color: .indigo,
                        format: "%.1f",
                        trend: viewModel.sleepTrend?.trendDirection
                    )
                }
                
                if let weight = viewModel.healthSummary?.weight {
                    HealthMetricCard(
                        title: "体重",
                        value: weight,
                        unit: "kg",
                        icon: "scalemass",
                        color: .green,
                        format: "%.1f"
                    )
                }
                
                if let energy = viewModel.healthSummary?.activeEnergy {
                    HealthMetricCard(
                        title: "活动能量",
                        value: Int(energy),
                        unit: "千卡",
                        icon: "flame",
                        color: .orange
                    )
                }
                
                if let distance = viewModel.healthSummary?.walkingDistance {
                    HealthMetricCard(
                        title: "步行距离",
                        value: distance,
                        unit: "公里",
                        icon: "point.topleft.down.curvedto.point.bottomright.up",
                        color: .purple,
                        format: "%.2f"
                    )
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.05), radius: 10, x: 0, y: 5)
    }
}

struct HealthMetricCard: View {
    let title: String
    let value: Double
    let unit: String
    let icon: String
    let color: Color
    var format: String = "%.0f"
    var trend: TrendDirection?
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // 图标和标题
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.caption)
                    .foregroundColor(color)
                
                Text(title)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // 数值和单位
            HStack(alignment: .firstTextBaseline, spacing: 4) {
                Text(String(format: format, value))
                    .font(.title2)
                    .fontWeight(.semibold)
                
                Text(unit)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            
            // 趋势指示器（如果有）
            if let trend = trend {
                HStack(spacing: 4) {
                    Image(systemName: trendIconName(trend))
                        .font(.caption2)
                    
                    Text(trend.rawValue)
                        .font(.caption2)
                }
                .foregroundColor(trendColor(trend))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private func trendIconName(_ trend: TrendDirection) -> String {
        switch trend {
        case .increasing:
            return "arrow.up"
        case .decreasing:
            return "arrow.down"
        case .stable:
            return "minus"
        case .fluctuating:
            return "arrow.left.arrow.right"
        }
    }
    
    private func trendColor(_ trend: TrendDirection) -> Color {
        switch trend {
        case .increasing:
            return .green
        case .decreasing:
            return .red
        case .stable, .fluctuating:
            return .gray
        }
    }
}

// MARK: - 趋势图表

struct HealthTrendCharts: View {
    @ObservedObject var viewModel: HealthDashboardViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 标题
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundColor(.blue)
                
                Text("趋势分析")
                    .font(.headline)
                
                Spacer()
                
                Text("过去7天")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal)
            
            // 步数趋势图表
            if let stepTrend = viewModel.stepTrend {
                TrendChartView(
                    title: "每日步数",
                    dataType: stepTrend.dataType,
                    dailyValues: stepTrend.dailyValues,
                    average: stepTrend.average,
                    color: .blue
                )
            }
            
            // 心率趋势图表
            if let heartRateTrend = viewModel.heartRateTrend {
                TrendChartView(
                    title: "平均心率",
                    dataType: heartRateTrend.dataType,
                    dailyValues: heartRateTrend.dailyValues,
                    average: heartRateTrend.average,
                    color: .red
                )
            }
            
            // 睡眠趋势图表
            if let sleepTrend = viewModel.sleepTrend {
                TrendChartView(
                    title: "睡眠时长",
                    dataType: sleepTrend.dataType,
                    dailyValues: sleepTrend.dailyValues,
                    average: sleepTrend.average,
                    color: .indigo
                )
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.05), radius: 10, x: 0, y: 5)
    }
}

struct TrendChartView: View {
    let title: String
    let dataType: HealthDataType
    let dailyValues: [Date: Double]
    let average: Double
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 图表标题
            HStack {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                
                Spacer()
                
                // 平均值
                HStack(spacing: 4) {
                    Text("平均")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text(String(format: "%.0f", average))
                        .font(.caption)
                        .fontWeight(.medium)
                    
                    Text(dataType.unitDescription)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
            
            // 图表
            Chart {
                ForEach(sortedDailyValues, id: \.date) { item in
                    LineMark(
                        x: .value("日期", item.date),
                        y: .value("数值", item.value)
                    )
                    .foregroundStyle(color)
                    .lineStyle(StrokeStyle(lineWidth: 2))
                    
                    PointMark(
                        x: .value("日期", item.date),
                        y: .value("数值", item.value)
                    )
                    .foregroundStyle(color)
                    .symbolSize(8)
                }
                
                // 平均线
                RuleMark(y: .value("平均值", average))
                    .foregroundStyle(color.opacity(0.5))
                    .lineStyle(StrokeStyle(lineWidth: 1, dash: [5, 5]))
            }
            .frame(height: 200)
            .chartXAxis {
                AxisMarks(values: .stride(by: .day)) { value in
                    AxisGridLine()
                    AxisTick()
                    AxisValueLabel(format: .dateTime.day().month())
                }
            }
            .chartYAxis {
                AxisMarks { value in
                    AxisGridLine()
                    AxisTick()
                    AxisValueLabel()
                }
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private var sortedDailyValues: [(date: Date, value: Double)] {
        dailyValues.sorted { $0.key < $1.key }.map { (date: $0.key, value: $0.value) }
    }
}

// MARK: - 健康建议

struct HealthRecommendationsView: View {
    let recommendations: [HealthRecommendation]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            // 标题
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.yellow)
                
                Text("健康建议")
                    .font(.headline)
                
                Spacer()
                
                Text("\(recommendations.count) 条")
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .padding(.horizontal)
            
            // 建议列表
            ForEach(recommendations) { recommendation in
                HealthRecommendationCard(recommendation: recommendation)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.05), radius: 10, x: 0, y: 5)
    }
}

struct HealthRecommendationCard: View {
    let recommendation: HealthRecommendation
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 优先级和类别
            HStack {
                // 优先级标签
                Text(recommendation.priority.rawValue)
                    .font(.caption2)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(priorityColor(recommendation.priority).opacity(0.2))
                    .foregroundColor(priorityColor(recommendation.priority))
                    .clipShape(Capsule())
                
                // 类别
                Text(recommendation.category.rawValue)
                    .font(.caption)
                    .foregroundColor(.secondary)
                
                Spacer()
            }
            
            // 标题
            Text(recommendation.title)
                .font(.subheadline)
                .fontWeight(.semibold)
            
            // 描述
            Text(recommendation.description)
                .font(.caption)
                .foregroundColor(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            
            // 行动步骤
            if !recommendation.actionSteps.isEmpty {
                VStack(alignment: .leading, spacing: 6) {
                    Text("行动步骤：")
                        .font(.caption)
                        .fontWeight(.medium)
                    
                    ForEach(recommendation.actionSteps, id: \.self) { step in
                        HStack(alignment: .top, spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.caption2)
                                .foregroundColor(.green)
                            
                            Text(step)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
                .padding(.top, 4)
            }
            
            // 预估影响
            if !recommendation.estimatedImpact.isEmpty {
                HStack {
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.caption2)
                        .foregroundColor(.blue)
                    
                    Text(recommendation.estimatedImpact)
                        .font(.caption)
                        .foregroundColor(.blue)
                }
                .padding(.top, 4)
            }
        }
        .padding()
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }
    
    private func priorityColor(_ priority: HealthRecommendation.Priority) -> Color {
        switch priority {
        case .high:
            return .red
        case .medium:
            return .orange
        case .low:
            return .green
        }
    }
}

// MARK: - 存储状态

struct StorageStatusView: View {
    let stats: HealthDataEncryptionManager.StorageStatistics
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            // 标题
            HStack {
                Image(systemName: "internaldrive.fill")
                    .foregroundColor(.gray)
                
                Text("存储状态")
                    .font(.headline)
                
                Spacer()
            }
            
            // 统计信息
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("数据样本")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("\(stats.totalSamples) 个")
                        .font(.body)
                        .fontWeight(.medium)
                }
                
                Spacer()
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("存储空间")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text(stats.readableSize)
                        .font(.body)
                        .fontWeight(.medium)
                }
                
                Spacer()
                
                VStack(alignment: .leading, spacing: 4) {
                    Text("数据类型")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    
                    Text("\(stats.dataTypes.count) 种")
                        .font(.body)
                        .fontWeight(.medium)
                }
            }
            .padding(.top, 4)
            
            // 最后同步时间（如果有）
            if let lastSync = stats.lastSyncTime {
                HStack {
                    Image(systemName: "icloud")
                        .font(.caption)
                    
                    Text("最后同步：\(lastSync, style: .time)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.top, 8)
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.05), radius: 10, x: 0, y: 5)
    }
}

// MARK: - 设置视图

struct HealthSettingsView: View {
    @ObservedObject var viewModel: HealthDashboardViewModel
    @Environment(\.dismiss) private var dismiss
    
    @State private var syncConfig: HealthSyncConfiguration
    @State private var showingClearConfirmation = false
    
    init(viewModel: HealthDashboardViewModel) {
        self.viewModel = viewModel
        _syncConfig = State(initialValue: viewModel.getSyncConfiguration())
    }
    
    var body: some View {
        NavigationStack {
            Form {
                // 数据同步设置
                Section("数据同步设置") {
                    Picker("同步频率", selection: $syncConfig.syncFrequency) {
                        ForEach(HealthSyncConfiguration.SyncFrequency.allCases, id: \.self) { frequency in
                            Text(frequency.rawValue).tag(frequency)
                        }
                    }
                    
                    Picker("数据保留期限", selection: $syncConfig.retentionPeriod) {
                        ForEach(HealthSyncConfiguration.RetentionPeriod.allCases, id: \.self) { period in
                            Text(period.rawValue).tag(period)
                        }
                    }
                    
                    Toggle("启用云同步", isOn: $syncConfig.cloudSyncEnabled)
                        .onChange(of: syncConfig.cloudSyncEnabled) { newValue in
                            if newValue {
                                // 显示云同步配置选项
                            }
                        }
                }
                
                // 监控的数据类型
                Section("监控的数据类型") {
                    ForEach(HealthDataType.allCases, id: \.self) { dataType in
                        Toggle(dataType.rawValue, isOn: binding(for: dataType))
                    }
                }
                
                // 数据管理
                Section {
                    Button("刷新数据") {
                        viewModel.refreshData()
                        dismiss()
                    }
                    
                    Button("清除所有数据", role: .destructive) {
                        showingClearConfirmation = true
                    }
                }
            }
            .navigationTitle("健康设置")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("取消") {
                        dismiss()
                    }
                }
                
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("保存") {
                        viewModel.updateSyncConfiguration(syncConfig)
                        dismiss()
                    }
                }
            }
            .alert("清除数据", isPresented: $showingClearConfirmation) {
                Button("取消", role: .cancel) { }
                Button("清除", role: .destructive) {
                    do {
                        try viewModel.clearAllData()
                    } catch {
                        print("Failed to clear data: \(error)")
                    }
                }
            } message: {
                Text("这将删除所有本地存储的健康数据，包括加密记录。此操作不可撤销。")
            }
        }
    }
    
    private func binding(for dataType: HealthDataType) -> Binding<Bool> {
        Binding(
            get: { syncConfig.enabledDataTypes.contains(dataType) },
            set: { newValue in
                if newValue {
                    syncConfig.enabledDataTypes.append(dataType)
                } else {
                    syncConfig.enabledDataTypes.removeAll { $0 == dataType }
                }
            }
        )
    }
}

// MARK: - 预览

struct HealthDashboardView_Previews: PreviewProvider {
    static var previews: some View {
        HealthDashboardView()
    }
}