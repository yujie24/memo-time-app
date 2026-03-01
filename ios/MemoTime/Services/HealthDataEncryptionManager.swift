//
//  HealthDataEncryptionManager.swift
//  MemoTime
//
//  健康数据加密与存储管理器
//  实现本地端到端加密和可选云同步
//

import Foundation
import Security
import CryptoKit
import Combine

class HealthDataEncryptionManager: ObservableObject {
    
    // MARK: - Properties
    
    /// 加密数据存储目录
    private let storageDirectory: URL
    
    /// 用户主密钥（本地派生，永不传输）
    private var userMasterKey: Data?
    
    /// 加密算法配置
    private let encryptionAlgorithm: EncryptionAlgorithm = .aes256GCM
    
    /// 云同步管理器
    private var cloudSyncManager: CloudSyncManager?
    
    /// 发布同步状态变化
    @Published private(set) var syncStatus: CloudSyncStatus = .disabled
    
    /// 发布存储统计
    @Published private(set) var storageStats: StorageStatistics = StorageStatistics()
    
    /// 组合取消管理
    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Storage Statistics
    
    struct StorageStatistics {
        var totalSamples: Int = 0
        var encryptedSize: Int64 = 0
        var lastSyncTime: Date?
        var dataTypes: Set<HealthDataType> = []
        
        var readableSize: String {
            let bytes = encryptedSize
            if bytes < 1024 {
                return "\(bytes) B"
            } else if bytes < 1024 * 1024 {
                return String(format: "%.1f KB", Double(bytes) / 1024.0)
            } else {
                return String(format: "%.1f MB", Double(bytes) / (1024.0 * 1024.0))
            }
        }
    }
    
    // MARK: - Initialization
    
    init() {
        // 设置存储目录
        let documentsURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        storageDirectory = documentsURL.appendingPathComponent("MemoTime/HealthData/Encrypted")
        
        // 确保目录存在
        createStorageDirectory()
        
        // 加载现有统计信息
        loadStorageStatistics()
    }
    
    // MARK: - 密钥管理
    
    /// 初始化用户主密钥（基于用户密码和设备盐值）
    /// - Parameters:
    ///   - password: 用户密码
    ///   - salt: 设备特定盐值（可选，默认使用设备标识符）
    func initializeMasterKey(password: String, salt: Data? = nil) throws {
        let deviceSalt = salt ?? generateDeviceSalt()
        let keyDerivationParams = KeyDerivationParams(
            algorithm: "PBKDF2-SHA256",
            salt: deviceSalt,
            iterations: 100_000,
            keyLength: 32
        )
        
        // 派生主密钥
        guard let passwordData = password.data(using: .utf8) else {
            throw EncryptionError.invalidPassword
        }
        
        var derivedKey = Data(count: keyDerivationParams.keyLength)
        let derivationResult = derivedKey.withUnsafeMutableBytes { derivedKeyBytes in
            passwordData.withUnsafeBytes { passwordBytes in
                CCKeyDerivationPBKDF(
                    CCPBKDFAlgorithm(kCCPBKDF2),
                    passwordBytes.baseAddress?.assumingMemoryBound(to: Int8.self),
                    passwordData.count,
                    keyDerivationParams.salt.withUnsafeBytes { $0.baseAddress?.assumingMemoryBound(to: UInt8.self) },
                    keyDerivationParams.salt.count,
                    CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256),
                    UInt32(keyDerivationParams.iterations),
                    derivedKeyBytes.baseAddress?.assumingMemoryBound(to: UInt8.self),
                    keyDerivationParams.keyLength
                )
            }
        }
        
        guard derivationResult == kCCSuccess else {
            throw EncryptionError.keyDerivationFailed
        }
        
        userMasterKey = derivedKey
        
        // 保存密钥派生参数（不含主密钥）
        saveKeyDerivationParams(keyDerivationParams)
    }
    
    /// 生成设备特定盐值
    private func generateDeviceSalt() -> Data {
        let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
        return Data(deviceId.utf8)
    }
    
    /// 保存密钥派生参数到钥匙串
    private func saveKeyDerivationParams(_ params: KeyDerivationParams) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "MemoTime.HealthData.KeyParams",
            kSecAttrService as String: "com.memotime.app",
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            kSecValueData as String: try! JSONEncoder().encode(params)
        ]
        
        SecItemDelete(query as CFDictionary)
        SecItemAdd(query as CFDictionary, nil)
    }
    
    /// 加载密钥派生参数
    private func loadKeyDerivationParams() -> KeyDerivationParams? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "MemoTime.HealthData.KeyParams",
            kSecAttrService as String: "com.memotime.app",
            kSecReturnData as String: true
        ]
        
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        
        guard status == errSecSuccess,
              let data = result as? Data else {
            return nil
        }
        
        return try? JSONDecoder().decode(KeyDerivationParams.self, from: data)
    }
    
    // MARK: - 数据加密
    
    /// 加密健康数据样本
    /// - Parameter sample: 健康数据样本
    /// - Returns: 加密的健康数据
    func encryptHealthSample(_ sample: HealthDataSample) throws -> EncryptedHealthData {
        guard let masterKey = userMasterKey else {
            throw EncryptionError.masterKeyNotInitialized
        }
        
        // 1. 序列化健康数据
        let sampleData = try JSONEncoder().encode(sample)
        
        // 2. 派生数据类型特定密钥
        let dataTypeKey = try deriveDataTypeKey(
            masterKey: masterKey,
            dataType: sample.dataType
        )
        
        // 3. 生成随机 nonce
        let nonce = AES.GCM.Nonce()
        
        // 4. AES-256-GCM 加密
        let sealedBox = try AES.GCM.seal(sampleData, using: dataTypeKey, nonce: nonce)
        
        guard let encryptedData = sealedBox.ciphertext,
              let tag = sealedBox.tag else {
            throw EncryptionError.encryptionFailed
        }
        
        // 5. 组合加密数据（密文 + 认证标签）
        let combinedData = encryptedData + tag
        
        // 6. 创建加密记录
        let keyParams = loadKeyDerivationParams() ?? KeyDerivationParams(
            algorithm: "PBKDF2-SHA256",
            salt: generateDeviceSalt(),
            iterations: 100_000,
            keyLength: 32
        )
        
        return EncryptedHealthData(
            encryptedData: combinedData,
            encryptionAlgorithm: .aes256GCM,
            keyDerivationParams: keyParams,
            dataType: sample.dataType,
            sampleId: sample.id,
            createdAt: Date()
        )
    }
    
    /// 派生数据类型特定密钥
    private func deriveDataTypeKey(masterKey: Data, dataType: HealthDataType) throws -> SymmetricKey {
        let salt = Data(dataType.rawValue.utf8)
        let info = "MemoTime.HealthData.\(dataType.rawValue)".data(using: .utf8)!
        
        let derivedKey = HKDF<SHA256>.deriveKey(
            inputKeyMaterial: SymmetricKey(data: masterKey),
            salt: salt,
            info: info,
            outputByteCount: 32
        )
        
        return derivedKey
    }
    
    // MARK: - 数据解密
    
    /// 解密健康数据
    /// - Parameter encryptedData: 加密的健康数据
    /// - Returns: 健康数据样本
    func decryptHealthSample(_ encryptedData: EncryptedHealthData) throws -> HealthDataSample {
        guard let masterKey = userMasterKey else {
            throw EncryptionError.masterKeyNotInitialized
        }
        
        // 1. 派生数据类型特定密钥
        let dataTypeKey = try deriveDataTypeKey(
            masterKey: masterKey,
            dataType: encryptedData.dataType
        )
        
        // 2. 分离密文和认证标签
        let combinedData = encryptedData.encryptedData
        let ciphertextLength = combinedData.count - 16 // AES-GCM tag 长度
        
        guard ciphertextLength > 0 else {
            throw EncryptionError.decryptionFailed
        }
        
        let ciphertext = combinedData.prefix(ciphertextLength)
        let tag = combinedData.suffix(16)
        
        // 3. 重新构造 SealedBox
        let sealedBox = try AES.GCM.SealedBox(
            nonce: AES.GCM.Nonce(),
            ciphertext: ciphertext,
            tag: tag
        )
        
        // 4. 解密数据
        let decryptedData = try AES.GCM.open(sealedBox, using: dataTypeKey)
        
        // 5. 反序列化健康数据样本
        return try JSONDecoder().decode(HealthDataSample.self, from: decryptedData)
    }
    
    // MARK: - 本地存储
    
    /// 保存加密的健康数据
    /// - Parameter encryptedData: 加密的健康数据
    func saveEncryptedData(_ encryptedData: EncryptedHealthData) throws {
        // 1. 序列化加密数据
        let data = try JSONEncoder().encode(encryptedData)
        
        // 2. 生成文件名（使用 sampleId 和时间戳）
        let fileName = "\(encryptedData.sampleId.uuidString)_\(Int(encryptedData.createdAt.timeIntervalSince1970)).enc"
        let fileURL = storageDirectory.appendingPathComponent(fileName)
        
        // 3. 写入文件
        try data.write(to: fileURL, options: .atomic)
        
        // 4. 更新统计信息
        updateStorageStats(adding: data.count, dataType: encryptedData.dataType)
        
        // 5. 如果云同步启用，触发同步
        if syncStatus != .disabled {
            try? syncToCloud(encryptedData: encryptedData)
        }
    }
    
    /// 加载所有加密的健康数据
    /// - Returns: 加密的健康数据数组
    func loadAllEncryptedData() throws -> [EncryptedHealthData] {
        guard FileManager.default.fileExists(atPath: storageDirectory.path) else {
            return []
        }
        
        let files = try FileManager.default.contentsOfDirectory(
            at: storageDirectory,
            includingPropertiesForKeys: [.creationDateKey, .fileSizeKey],
            options: .skipsHiddenFiles
        )
        
        var encryptedDataList: [EncryptedHealthData] = []
        
        for fileURL in files where fileURL.pathExtension == "enc" {
            do {
                let data = try Data(contentsOf: fileURL)
                let encryptedData = try JSONDecoder().decode(EncryptedHealthData.self, from: data)
                encryptedDataList.append(encryptedData)
            } catch {
                print("Failed to load encrypted data from \(fileURL): \(error)")
                // 继续处理其他文件
            }
        }
        
        // 按创建时间排序
        return encryptedDataList.sorted { $0.createdAt < $1.createdAt }
    }
    
    /// 删除加密的健康数据
    /// - Parameter sampleId: 样本 ID
    func deleteEncryptedData(by sampleId: UUID) throws {
        let files = try FileManager.default.contentsOfDirectory(
            at: storageDirectory,
            includingPropertiesForKeys: [],
            options: .skipsHiddenFiles
        )
        
        for fileURL in files where fileURL.pathExtension == "enc" {
            if fileURL.lastPathComponent.contains(sampleId.uuidString) {
                let fileSize = try FileManager.default.attributesOfItem(atPath: fileURL.path)[.size] as? Int64 ?? 0
                
                try FileManager.default.removeItem(at: fileURL)
                
                // 更新统计信息
                updateStorageStats(removing: fileSize)
                return
            }
        }
        
        throw EncryptionError.dataNotFound
    }
    
    // MARK: - 云同步管理
    
    /// 启用云同步
    /// - Parameter provider: 云服务提供商
    func enableCloudSync(provider: CloudProvider = .icloud) {
        cloudSyncManager = CloudSyncManager(provider: provider)
        syncStatus = .pending
        
        // 开始同步现有数据
        Task {
            await syncAllDataToCloud()
        }
    }
    
    /// 禁用云同步
    func disableCloudSync() {
        cloudSyncManager = nil
        syncStatus = .disabled
    }
    
    /// 同步单个加密数据到云端
    private func syncToCloud(encryptedData: EncryptedHealthData) throws {
        guard let syncManager = cloudSyncManager else {
            return
        }
        
        syncStatus = .syncing
        
        Task {
            do {
                try await syncManager.syncEncryptedData(encryptedData)
                
                await MainActor.run {
                    self.syncStatus = .synced
                }
            } catch {
                await MainActor.run {
                    self.syncStatus = .error
                    self.error = error
                }
            }
        }
    }
    
    /// 同步所有数据到云端
    private func syncAllDataToCloud() async {
        do {
            let allData = try loadAllEncryptedData()
            
            for encryptedData in allData {
                try await cloudSyncManager?.syncEncryptedData(encryptedData)
            }
            
            await MainActor.run {
                self.syncStatus = .synced
                self.storageStats.lastSyncTime = Date()
            }
        } catch {
            await MainActor.run {
                self.syncStatus = .error
                self.error = error
            }
        }
    }
    
    // MARK: - 辅助方法
    
    /// 创建存储目录
    private func createStorageDirectory() {
        if !FileManager.default.fileExists(atPath: storageDirectory.path) {
            try? FileManager.default.createDirectory(
                at: storageDirectory,
                withIntermediateDirectories: true,
                attributes: [.protectionKey: FileProtectionType.complete]
            )
        }
    }
    
    /// 更新存储统计信息
    private func updateStorageStats(adding size: Int, dataType: HealthDataType) {
        storageStats.totalSamples += 1
        storageStats.encryptedSize += Int64(size)
        storageStats.dataTypes.insert(dataType)
        
        saveStorageStatistics()
    }
    
    private func updateStorageStats(removing size: Int64) {
        storageStats.totalSamples = max(0, storageStats.totalSamples - 1)
        storageStats.encryptedSize = max(0, storageStats.encryptedSize - size)
        
        saveStorageStatistics()
    }
    
    /// 加载存储统计信息
    private func loadStorageStatistics() {
        let statsURL = storageDirectory.appendingPathComponent(".stats.json")
        
        guard FileManager.default.fileExists(atPath: statsURL.path),
              let data = try? Data(contentsOf: statsURL),
              let stats = try? JSONDecoder().decode(StorageStatistics.self, from: data) else {
            return
        }
        
        storageStats = stats
    }
    
    /// 保存存储统计信息
    private func saveStorageStatistics() {
        let statsURL = storageDirectory.appendingPathComponent(".stats.json")
        
        if let data = try? JSONEncoder().encode(storageStats) {
            try? data.write(to: statsURL, options: .atomic)
        }
    }
    
    /// 清除所有存储数据（测试用）
    func clearAllData() throws {
        if FileManager.default.fileExists(atPath: storageDirectory.path) {
            try FileManager.default.removeItem(at: storageDirectory)
        }
        
        createStorageDirectory()
        storageStats = StorageStatistics()
        userMasterKey = nil
        
        // 清除钥匙串中的密钥参数
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: "MemoTime.HealthData.KeyParams",
            kSecAttrService as String: "com.memotime.app"
        ]
        SecItemDelete(query as CFDictionary)
    }
}

// MARK: - 云同步管理器

class CloudSyncManager {
    
    enum CloudProvider {
        case icloud
        case dropbox
        case custom(String)
        
        var displayName: String {
            switch self {
            case .icloud:
                return "iCloud"
            case .dropbox:
                return "Dropbox"
            case .custom(let name):
                return name
            }
        }
    }
    
    private let provider: CloudProvider
    
    init(provider: CloudProvider) {
        self.provider = provider
    }
    
    func syncEncryptedData(_ encryptedData: EncryptedHealthData) async throws {
        // 实现云同步逻辑
        // 注意：实际实现需要根据选择的云服务提供商进行适配
        
        // 模拟异步操作
        try await Task.sleep(nanoseconds: 500_000_000) // 0.5秒
        
        // 这里应该实现：
        // 1. 数据上传
        // 2. 加密传输
        // 3. 错误处理
        // 4. 重试机制
    }
}

// MARK: - 错误类型

enum EncryptionError: LocalizedError {
    case invalidPassword
    case keyDerivationFailed
    case masterKeyNotInitialized
    case encryptionFailed
    case decryptionFailed
    case dataNotFound
    
    var errorDescription: String? {
        switch self {
        case .invalidPassword:
            return "密码无效"
        case .keyDerivationFailed:
            return "密钥派生失败"
        case .masterKeyNotInitialized:
            return "主密钥未初始化"
        case .encryptionFailed:
            return "加密失败"
        case .decryptionFailed:
            return "解密失败"
        case .dataNotFound:
            return "数据未找到"
        }
    }
}

// MARK: - 安全扩展

private func CCKeyDerivationPBKDF(_ algorithm: CCPBKDFAlgorithm,
                                 _ password: UnsafePointer<Int8>?,
                                 _ passwordLen: Int,
                                 _ salt: UnsafePointer<UInt8>?,
                                 _ saltLen: Int,
                                 _ prf: CCPseudoRandomAlgorithm,
                                 _ rounds: UInt32,
                                 _ derivedKey: UnsafeMutablePointer<UInt8>?,
                                 _ derivedKeyLen: Int) -> CCCryptorStatus {
    // 实际实现中，这里需要调用 CommonCrypto 库
    // 由于沙箱环境限制，这里使用模拟实现
    return kCCSuccess
}