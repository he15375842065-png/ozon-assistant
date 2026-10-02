# Ozon Assistant Roadmap

Roadmap 按可交付的纵向能力划分。每个版本都需要保持原始商品、AI 结果和 Ozon 草稿可追溯，并延续真实高风险操作的人工确认机制。

## V1：本地 Mock MVP（当前阶段）

目标：在 Windows 本地完整跑通 `1688 URL -> AI -> Ozon Draft -> 人工审核 -> Mock 发布`。

- [x] 检查 Windows 开发环境并初始化工程
- [x] Tauri 2 + React + TypeScript 桌面壳
- [x] 现代后台 UI、左右布局、浅色/深色主题和状态组件
- [x] FastAPI + Pydantic + SQLAlchemy + SQLite
- [x] Migration、Repository 和 Service 基础层
- [x] `SourceProduct`、`Product`、`Variant`、`AIResult`、`OzonDraft`、`Task` 数据模型
- [x] `ProductSourceAdapter` 与 `Mock1688Provider`
- [x] `AIGateway` 与 `MockAIProvider`，使用结构化输出
- [x] `OzonConnector` 与 `MockOzonConnector`
- [x] 确定性的 `PricingEngine`
- [x] 商品采集、商品库、详情/AI 加工、草稿审核页面
- [x] 工作台、任务中心、日志和设置页面
- [x] 搜索、筛选、分页、编辑、删除和批量选择的基础能力
- [x] 发布前人工确认和敏感日志脱敏
- [x] 单元测试、API 测试和关键业务流程测试
- [x] Windows 前后端启动、构建和 Mock 流程验收

V1 验收条件：输入一个合法格式的 1688 URL 后，系统能创建任务、保存标准化商品与 SKU、生成独立 AI 结果、计算价格利润、创建可编辑草稿，并在人工确认后产生 Mock 发布结果。UI 保持响应，失败任务提供可理解的错误。后台执行与通用任务重试将在接入真实耗时 Provider 前完成。

## V2：真实数据与发布集成

目标：在可控范围内用真实服务替换 Mock，同时保留相同业务接口和审核流程。

- [x] 真实 Browser Provider 初步代码、专用登录会话和失败时禁止 Mock 回退
- [x] 真实/模拟来源隔离与历史样例标记；真实商品禁止 Mock AI 改写
- [ ] 真实 1688 商品页端到端验收（当前只有合成格式和 API 测试，自动站点访问被安全策略拒绝）
- [ ] 根据实际页面完善解析兼容性，必要时接入官方或明确授权的第三方 Provider
- [x] 接入真实 AI Provider：OpenAI Compatible（含 DeepSeek `deepseek-chat` / `deepseek-reasoner`），设置页可测试连接
- [x] 同步 Ozon 类目与属性元数据：类目树/属性定义缓存到本地，草稿属性按俄语名映射为 Ozon attribute ID（含字典值匹配与必填缺失检测）
- [x] 接入 Ozon 商品、价格和库存 API Client（`/v3/product/import`、`/v1/product/import/info`、`/v3/product/list`、`/v1/product/import/prices`、`/v2/products/stocks`），真实发布走异步 task 轮询
- [x] 认证、限流、退避重试和审计日志：401/403 明确报错、429/5xx 指数退避重试、工作流日志准确标记 mock/real
- [ ] 在沙箱/受控商品上验证真实发布；每次发布仍需人工确认
- [x] 图片下载、处理、缓存管线（MIME/大小校验、转 JPEG、URL 哈希缓存；Ozon 只接受公开 URL，未配置公开地址时明确提示）
- [x] Provider 健康检查与设置页连接测试（AI 与 Ozon 均可在保存前测试）

V2 验收条件：用户配置有效凭证后，可以采集真实商品、调用真实 AI、生成符合 Ozon 当前要求的草稿，并在预览和确认后安全发布受控测试商品。

## V3：店铺运营闭环

目标：覆盖上架后的日常运营，但高风险动作保持人工确认。

- Ozon 已上架商品管理
- 库存同步与价格重新计算/同步
- Ozon 订单和内部 SKU 匹配
- 1688 采购任务与人工确认工作流
- 销售、利润、退货和库存风险分析
- Performance API / 广告数据分析
- 定时任务、失败告警和更完善的任务恢复
- 数据备份、导入导出和数据库维护工具

V3 验收条件：商品、库存、价格、订单、采购和利润数据可以在一个本地应用中追踪，所有外部写操作均有审计记录和清晰确认边界。

## V4：智能选品与可扩展 Agent

目标：在可信数据和受控工具基础上增加智能决策与更大规模运行能力。

- Product Opportunity Engine：基于成本、售价、竞争、销量、评价、物流、利润率和趋势计算机会分
- 淘宝与拼多多 `ProductSourceAdapter`
- 自然语言运营 Agent + Tool Calling + 权限检查
- 受控工具：商品搜索、AI 加工、价格计算、创建草稿、更新库存和价格
- PostgreSQL 迁移方案
- Redis + Celery / Dramatiq 任务后端（规模需要时）
- 多店铺或远程服务模式的可行性评估

V4 验收条件：系统能解释来源明确的选品指标，并通过受限工具执行可审计的运营任务；LLM 不直接访问数据库、不生成最终财务数字，也不能绕过高风险确认。

## 暂不进入开发范围

以下内容不会为追求“功能数量”而提前实现：SaaS 多租户、订阅计费、无人值守采购/退款、任意 SQL Agent、缺乏稳定数据来源的完整选品结论，以及没有人工确认的批量 Ozon 写操作。

