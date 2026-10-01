# Ozon Assistant 桌面端

这是 Ozon Assistant 的 Tauri 2 + React + TypeScript 桌面界面。开发模式默认连接 `http://127.0.0.1:8001/api/v1`，也可以通过 `VITE_API_URL` 覆盖。

常用命令：

- `npm run dev`：启动 Vite 开发服务器。
- `npm run typecheck`：执行 TypeScript 严格类型检查。
- `npm run build`：构建前端静态资源。
- `npm run tauri dev`：在 Tauri 窗口中联调桌面应用。
- `npm run tauri build`：生成 Windows 桌面安装产物。

启动桌面端前，请先启动本地 FastAPI 服务。也可以从仓库根目录运行 `.\scripts\dev.ps1` 同时启动 API 与 Tauri，或运行 `.\scripts\dev.ps1 -Web` 进行浏览器调试。

当前 Tauri 构建只打包桌面界面，Python API 尚未作为 sidecar 随安装包分发。因此 `npm run tauri build` 生成的是开发预览安装包，不能脱离本地后端独立运行。
