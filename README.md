# Ozon Assistant（ozon助手）

Ozon Assistant 是一个面向单个 Ozon 店铺的 Windows 桌面工具，目标是把国内货源发现、商品加工、定价、Ozon 草稿审核和后续运营集中到一个本地应用中。

当前开发重点是跑通第一条可演示、可测试的纵向链路：

```text
1688 商品 URL
  -> Mock 采集并保存原始数据
  -> Mock AI 生成俄语商品资料
  -> Ozon 类目与属性建议
  -> 确定性价格/利润计算
  -> Ozon Draft
  -> 人工审核
  -> Mock 发布
```

第一阶段默认使用 `Mock1688Provider`、`MockAIProvider` 和 `MockOzonConnector`。Mock 模式不会访问真实 1688、AI 或 Ozon 服务，也不会发布真实商品。真实 Ozon 发布必须经过明确的人工确认。

## 当前阶段

仓库已完成 V1 Mock MVP 的第一轮纵向链路。当前覆盖工作台、商品采集、商品库、AI 加工、Ozon 草稿审核、任务中心、日志和设置，以及支撑这些页面的本地 API 与数据库。

订单、采购、广告、自动库存/价格同步、完整 AI 选品、淘宝、拼多多和复杂 Agent 不属于当前实现范围。详见 [ROADMAP.md](./ROADMAP.md)。

## 技术栈

- 桌面端：Tauri 2、React 19、TypeScript、Vite
- UI：Tailwind CSS、可复用 React 组件、Lucide Icons
- 本地 API：Python 3、FastAPI、Pydantic、SQLAlchemy
- 数据库：SQLite；通过 Repository / Service 边界为 PostgreSQL 迁移预留空间
- 任务追踪：第一阶段在请求内执行快速 Mock 流程，并把任务状态持久化到 SQLite；真实耗时 Provider 接入前再引入后台执行器
- 测试：前端类型检查与构建、Python 单元测试和 API 测试、关键业务流程测试

## 项目结构

```text
Ozon Assistant/
|-- apps/
|   `-- desktop/              # Tauri + React + TypeScript 桌面端
|-- backend/                  # FastAPI、本地任务与领域逻辑
|   |-- app/
|   |   |-- api/              # HTTP 路由和依赖注入
|   |   |-- core/             # 配置、日志、错误和安全基础设施
|   |   |-- database/         # SQLAlchemy 会话和 Migration
|   |   |-- models/           # 持久化模型
|   |   |-- schemas/          # Pydantic 输入/输出模型
|   |   |-- repositories/     # 数据访问边界
|   |   |-- services/         # 应用服务、流程编排和 TaskService
|   |   |-- pricing/          # 确定性价格与利润计算
|   |   `-- integrations/     # 1688、AI、Ozon Provider / Connector
|   |-- tests/                # 后端及关键链路测试
|   `-- pyproject.toml
|-- ARCHITECTURE.md
`-- ROADMAP.md
```

模块边界和依赖规则见 [ARCHITECTURE.md](./ARCHITECTURE.md)。

## Windows 开发环境

建议准备：

- Windows 10/11
- Git
- Node.js 当前 LTS 版本与 npm
- Rust stable（通过 `rustup` 安装）
- Microsoft C++ Build Tools，包含“使用 C++ 的桌面开发”工作负载
- Microsoft Edge WebView2 Runtime
- Python 3.11 或更高版本

首次安装 Tauri 的 Windows 系统依赖时，请以 Tauri 2 官方前置要求为准。

## 配置

在仓库根目录创建本地配置：

```powershell
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item .env.example .env
}
```

`.env` 已被 Git 忽略。V1 的默认配置应保持三个集成均为 `mock`。不要把真实 API Key、Token、Client Secret 或密码提交到仓库；日志也不得输出完整凭证。

## 桌面端开发

当前 `apps/desktop/package.json` 已定义以下脚本：

```powershell
# 从仓库根目录运行
Set-Location .\apps\desktop
npm ci
npm run dev
```

这会启动 Vite 前端。启动完整 Tauri 桌面窗口：

```powershell
Set-Location .\apps\desktop
npm run tauri dev
```

前端生产构建与 Tauri Rust 检查：

```powershell
Set-Location .\apps\desktop
npm run build
cargo check --manifest-path .\src-tauri\Cargo.toml
```

本轮暂不交付正式安装包。开发时可使用根目录的 `scripts/dev.ps1` 一次启动桌面界面和 Python API；需要独立分发时，再把 Python API 打包为 Tauri sidecar 并生成安装包。

## 本地后端开发

从仓库根目录创建虚拟环境并安装开发依赖：

```powershell
py -3 -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item .env.example .env
}
```

启动 FastAPI 开发服务：

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8001 --reload
```

运行后端测试：

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend\tests
```

后端入口为 `app.main:app`，API 前缀为 `/api/v1`。从仓库根目录运行上述命令时，配置系统读取根目录 `.env`；从 `backend` 目录运行时则读取 `backend/.env`。

桌面端通过环境变量 `VITE_API_URL` 指向本地 API；默认地址为 `http://127.0.0.1:8001/api/v1`。`8000` 已被本机其他项目占用，因此 Ozon Assistant 固定使用 `8001`。后端设置使用 `OZON_ASSISTANT_` 前缀。本地服务只应绑定回环地址，除非用户明确配置局域网访问。

数据库 Migration 采用 Alembic。应用启动时会自动应用已提交的版本，也可以手动执行：

```powershell
.\backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
```

## 一键开发与验证

完成首次依赖安装：

```powershell
.\scripts\bootstrap.ps1
```

同时启动 FastAPI 与 Tauri 桌面端：

```powershell
.\scripts\dev.ps1
```

仅以浏览器模式调试 React 界面：

```powershell
.\scripts\dev.ps1 -Web
```

运行后端测试、前端类型检查/构建和 Rust 检查：

```powershell
.\scripts\test.ps1
```

## V1 验收记录

2026-10-02 已在当前 Windows 环境完成第一轮验收：

- 后端单元、API、安全和完整业务链路测试：`43 passed`。
- TypeScript 严格类型检查、Vite 生产构建和 Rust `cargo check` 通过。
- 使用全新 SQLite 数据库完成 Migration，并实际跑通 `1688 URL -> Mock 采集 -> Mock AI -> 定价 -> 草稿编辑 -> 人工确认 -> Mock 发布`。
- 使用真实浏览器检查桌面、390px 窄屏、浅色/深色主题；控制台无错误或警告。
- Tauri Rust 桌面壳编译检查通过；本轮按要求不交付正式安装包。

开发使用 `scripts/dev.ps1` 可一次启动桌面界面和本地 Python API。

## 开发约束

- 原始 1688 数据、AI 加工结果、Ozon 最终草稿分别保存，AI 结果不能覆盖原始商品。
- 业务服务依赖 Provider / Connector 接口，不直接依赖 Playwright、具体 LLM SDK 或零散 HTTP 请求。
- 数字由 `PricingEngine` 和规则代码计算；LLM 只负责理解、翻译、解释和策略建议。
- V1 Mock 流程会创建并持久化 Task Center 记录。接入真实采集、AI、图片处理或同步 Provider 前，必须把这些耗时操作迁移到后台执行器，避免长请求占用 API 工作线程。
- 发布、批量改价、库存修改、采购和退款等操作必须保留人工确认边界。
- 日志必须脱敏，严禁记录完整 API Key、Token 或密码。

## 文档

- [ARCHITECTURE.md](./ARCHITECTURE.md)：模块关系、数据流和关键设计决策
- [ROADMAP.md](./ROADMAP.md)：V1 至 V4 范围和验收目标

