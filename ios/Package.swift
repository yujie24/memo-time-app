// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "MemoTime",
    platforms: [
        .iOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "MemoTimeHealth",
            targets: ["MemoTimeHealth"]),
        .library(
            name: "MemoTimeCalendar",
            targets: ["MemoTimeCalendar"]),
        .library(
            name: "MemoTimeAI",
            targets: ["MemoTimeAI"]),
    ],
    dependencies: [
        // 苹果官方框架，通过系统提供
        // 无外部依赖
    ],
    targets: [
        .target(
            name: "MemoTimeHealth",
            dependencies: [],
            path: "MemoTime",
            sources: [
                "Models/HealthModels.swift",
                "Services/HealthKitManager.swift",
                "Services/HealthDataEncryptionManager.swift",
                "ViewModels/HealthDashboardViewModel.swift"
            ],
            resources: [
                .process("Resources")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .target(
            name: "MemoTimeCalendar",
            dependencies: [],
            path: "MemoTime",
            sources: [
                "Models/CalendarModels.swift",
                "Services/CalendarSyncManager.swift",
                "Services/LocalStorageManager.swift",
                "Views/CalendarView.swift"
            ],
            resources: [
                .process("Resources")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .target(
            name: "MemoTimeAI",
            dependencies: [],
            path: "MemoTime",
            sources: [
                "Services/AIAnalysisManager.swift",
                "Views/AIAnalysisView.swift"
            ],
            resources: [
                .process("Resources")
            ],
            swiftSettings: [
                .enableExperimentalFeature("StrictConcurrency")
            ]
        ),
        .testTarget(
            name: "MemoTimeHealthTests",
            dependencies: ["MemoTimeHealth"],
            path: "Tests/MemoTimeHealthTests"
        ),
        .testTarget(
            name: "MemoTimeCalendarTests",
            dependencies: ["MemoTimeCalendar"],
            path: "Tests/MemoTimeCalendarTests"
        ),
    ]
)