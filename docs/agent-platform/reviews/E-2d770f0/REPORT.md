# ChatRaw G11/G12 本机复验

2026-11-12，提交 `2d770f0e079652d2dc99b49124d60f3305c8c393`，独立分支 `codex/agent-platform-e-final-verification`。macOS 27.0.1 arm64，Node 24.10.0、npm 11.6.0、PostCSS 8.5.32、Python 3.12.4、FastAPI 0.123.7、aiohttp 3.13.3、Uvicorn 0.40.0。

| 检查 | Chromium 109.0.5414.46 | Google Chrome 157.0.8103.51 |
| --- | --- | --- |
| 离线市场、普通聊天与插件资源 | 通过。外部请求、HTTP 错误和浏览器错误均为 0 | 通过。外部请求、HTTP 错误和浏览器错误均为 0 |
| 真实 ChatRaw 网关与 Runner | 通过。外部请求尝试为 0 | 通过。外部请求尝试为 0 |

`npm ci --no-audit --no-fund`、`npm run build` 和 `npm run vendor:check` 通过。重建后的两个压缩文件与提交逐字节一致。[构建日志](build.log)

## 实际验证结果

- 市场通过本地接口新装 Excel Parser Pro 1.0.2、Mindmap Renderer 1.0.1、Enhanced Export 1.0.0。缺少 KaTeX 字体的 Markdown Renderer Plus 1.0.0 升级到 1.0.1，保留原禁用状态和设置。重新启用后，公式及同源字体、Mermaid、Markmap 和 PDF 下载正常。旧 CSV manifest 通过同源 Papa Parse 解析，模拟模型接收到了表格正文。
- 普通聊天用真实 ChatRaw 后端与本地模拟 SSE，验证流式 Markdown、表格、高亮、转义和推理区展开。
- 网关用真实 ASGI、Runner HTTP 和临时数据目录。市场安装 Hermes 2.0.0，配置、附件、关闭首个浏览器上下文后由第二个上下文审批、受控目录写入、终稿替换与刷新去重均通过。Agent 端使用 ControlledAdapter。此次复验的范围是本机浏览器及这些界面链路。Windows 8 上的 Google Chrome 109 和五个原生 Agent 现场验收另行记录。

## 重跑与证据

在 `2d770f0` 的独立树安装 `backend/requirements-test.txt`，执行 `npm ci`、`npm run build` 和 `npm run vendor:check`。用 `CHROME_PATH` 指向实际浏览器二进制，`PYTHON` 指向测试环境。109 执行 `npm run test:chrome109`，现代 Chrome 执行 `npm run test:offline-ui`。两版网关均执行 `node scripts/test-agent-gateway-ui.mjs`。本次额外用 `node --import ./outputs/e-2d770f0/gateway-network-audit.mjs scripts/test-agent-gateway-ui.mjs` 记录网关测试的浏览器外部请求尝试，脚本自带的同源阻断继续生效。

- Chromium 109 的 CDP 修订为 `@6e36b77363ef3febbe792af680fa1367993ddcf0`。[离线日志](109/offline-ui.log) · [离线截图](109/offline-ui.png) · [网关日志](109/gateway-ui.log) · [网关截图](109/real-gateway-controlled-adapter.png)
- Chrome 157 的 CDP 修订为 `@653674df293788cf4932c40d914e9e15b41a2d31`。[离线日志](157/offline-ui.log) · [离线截图](157/offline-ui.png) · [网关日志](157/gateway-ui.log) · [网关截图](157/real-gateway-controlled-adapter.png)
