# MemoTime App - 个人生产力系统

## 项目概述

MemoTime App 是一款面向个人用户的集成生产力系统，深度整合日历、笔记、日记、项目管理功能，并通过智能自动化引擎实现链接内容的自动分类与多格式保存。系统支持扩展模块：同步 iOS 健身和健康数据、同步 iOS 日历、自动同步支付宝/微信消费记录或拍照录入财务数据，并支持接入 Coze、DeepSeek 等 AI 工具进行分析。

### 核心价值主张
- **智能化**：自动识别链接内容，智能分类到对应项目、笔记或任务
- **一体化**：统一管理日程、笔记、日记和项目，消除工具切换成本
- **自动化**：从链接分享到内容保存、分类、索引的全流程自动化
- **隐私优先**：本地处理优先，端到端加密，用户数据完全可控

### 目标用户
- 知识工作者、研究人员、学生等需要大量收集和整理网络信息的用户
- 追求高效率、喜欢自动化工作流的科技爱好者
- 重视数据隐私，希望数据存储在本地或可控云端的用户

## 核心功能模块

### 1. 多源链接抓取模块
- 浏览器扩展（Chrome/Safari/Firefox）捕获用户分享的链接
- 移动端分享集成（iOS 分享菜单、Android 分享面板）
- RESTful API 接收外部应用推送的链接
- 链接去重机制，避免重复内容

### 2. 智能分类引擎
- **双层分类系统**：
  - 第一层：基于规则的关键词匹配（快速、可解释）
  - 第二层：基于 BERT 微调模型的语义理解（精准、智能）
- 分类标签体系：项目关联、主题分类、内容类型、优先级
- 用户反馈闭环，系统学习用户偏好

### 3. 格式转换管道
- 支持 PDF、PPTX、DOCX 三种主要格式
- 智能格式选择：根据内容类型自动推荐最佳格式
- 模板系统：支持用户自定义输出模板
- 批量转换：支持多个链接的批量格式转换

### 4. iOS 健康与日历集成
- 读取 iOS 健身和健康数据，整合到个人数据面板
- 同步 iOS 日历功能，实现日程与待办事项联动
- 隐私保护：基于可选的受控云同步模式，默认本地存储端到端加密

### 5. 财务数据同步
- 自动同步支付宝/微信消费记录
- 或通过拍照录入账单信息（OCR 识别）
- 财务数据本地加密存储，可选云同步

### 6. AI 接口接入
- 支持接入 Coze、DeepSeek 等 AI 工具
- 用户可直接调用 AI 分析最近的记录数据
- 分析结果可视化展示

## 技术架构选型

### 后端技术栈
- **网页渲染与内容提取**：Puppeteer（支持 JavaScript 动态内容）+ Readability（核心内容提取）
- **智能分类**：基于 Hugging Face Transformers 的 BERT 微调模型 + 规则引擎（正则表达式 + 关键词库）
- **格式转换**：
  - PDF 生成：Puppeteer + HTML 转 PDF（高保真）
  - PPT 导出：基于模板的 JSON 到 PPTX 转换
  - Word 保存：Markdown 到 DOCX 标准化转换
- **数据存储**：
  - 结构化数据：PostgreSQL（链接元数据、分类标签、用户项目关联）
  - 文档文件：对象存储/S3 兼容（原始 HTML、提取文本、生成文件）
  - 缓存/会话：Redis
  - 全文搜索：Elasticsearch（标题、摘要、全文内容索引）
- **任务队列**：Celery（异步处理、批量转换）
- **API 设计**：RESTful API（符合 OpenAPI 规范），OAuth 2.0 认证，Webhook 支持

### 前端技术栈
- **iOS/Mac 原生应用**：SwiftUI，EventKit 框架（日历），HealthKit 框架（健康数据）
- **Web 管理界面**：React + TypeScript，ECharts 数据可视化
- **浏览器扩展**：JavaScript（Chrome/Safari/Firefox 跨平台支持）

### 部署与运维
- **容器化**：Docker + Kubernetes
- **监控告警**：Prometheus + Grafana
- **日志管理**：ELK Stack（Elasticsearch, Logstash, Kibana）
- **CI/CD**：GitHub Actions / GitLab CI

## 构建与运行说明

### 环境要求
- Python 3.9+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+
- Elasticsearch 8+

### 本地开发环境设置

1. **克隆仓库**
   ```bash
   git clone https://github.com/<your-username>/memo-time-app.git
   cd memo-time-app
   ```

2. **安装后端依赖**
   ```bash
   # 创建虚拟环境（可选）
   python -m venv venv
   source venv/bin/activate  # Linux/macOS
   # venv\Scripts\activate   # Windows

   # 安装依赖
   pip install -r requirements.txt
   ```

3. **安装前端依赖**
   ```bash
   cd web
   npm install
   cd ..
   ```

4. **配置环境变量**
   复制 `.env.example` 为 `.env` 并填写相应配置：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，设置数据库连接、API密钥等
   ```

5. **启动数据库服务**
   ```bash
   # 使用 Docker Compose 启动依赖服务
   docker-compose up -d postgres redis elasticsearch
   ```

6. **运行数据库迁移**
   ```bash
   python manage.py migrate
   ```

7. **启动开发服务器**
   ```bash
   # 后端 API 服务器
   python manage.py runserver

   # 前端开发服务器（另一个终端）
   cd web
   npm start
   ```

8. **访问应用**
   - Web 界面：http://localhost:3000
   - API 文档：http://localhost:8000/api/docs

### 生产环境部署

参考 `docs/部署指南.md` 进行生产环境配置。

## 贡献指南

我们欢迎社区贡献！请阅读以下指南：

### 开发流程

1. **Fork 仓库**：点击右上角的 Fork 按钮，创建你的仓库副本
2. **创建分支**：从 `main` 分支创建功能分支
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **提交更改**：遵循 Conventional Commits 规范
   ```
   feat: 添加新功能
   fix: 修复bug
   docs: 文档更新
   style: 代码格式调整
   refactor: 代码重构
   test: 测试相关
   chore: 构建过程或辅助工具变动
   ```
4. **运行测试**：确保所有测试通过
   ```bash
   pytest
   npm test
   ```
5. **推送分支**：推送到你的 Fork 仓库
6. **创建 Pull Request**：向主仓库发起 PR，描述变更内容

### 代码规范
- **Python**：遵循 PEP 8，使用 Black 格式化
- **JavaScript/TypeScript**：使用 ESLint + Prettier
- **提交信息**：使用 Conventional Commits 格式
- **文档**：所有公共 API 必须有文档字符串

### 问题报告
- 使用 GitHub Issues 报告 bug 或建议功能
- 提供复现步骤、期望行为、实际行为
- 对于 bug，请注明环境信息（操作系统、Python/Node版本等）

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

## 联系方式

- 项目仓库：https://github.com/<your-username>/memo-time-app
- 问题追踪：GitHub Issues

---

## 项目状态

当前项目处于 **第一阶段：初始化**，已完成竞品分析、PRD 初稿、技术可行性验证（日历/健康模块），正在进行第三方服务技术验证（财务+AI接口）。

详细路线图见 `docs/执行路线图.md`。