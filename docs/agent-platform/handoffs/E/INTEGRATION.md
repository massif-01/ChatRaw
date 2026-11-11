# E 线集成复验

## B 前端集成基线

提交 `bd9ad55a4161f69bba51a5e6345c27fb4ae63f01`。Node 24.10.0、npm 11.6.0、PostCSS 8.5.32。执行 `npm ci`、`npm run build` 和 `npm run vendor:check` 均通过。实际运行的 `app.min.js` SHA-256 为 `1a564fcc68818cab760266b01ee78c24f2a5cbe9f7fe7b7a04a9ebb4c430a463`，`styles.min.css` 为 `1d40b0bc10a1700f38a829eac2fafa1fd9bba439d98533cedd10fa24166f0d82`。

| 检查 | Chromium 109.0.5414.46 | Chrome 157.0.8103.51 | 证据范围 |
| --- | --- | --- | --- |
| `node scripts/test-agent-ui.mjs` | 通过 | 通过 | 阻断浏览器外部请求。五个 Agent 插件界面生命周期、模式切换、绑定、提交及恢复、附件、问答与审批、停止、压缩和普通聊天路径。API 使用协议 fixture |
| `node scripts/test-stream-markdown.mjs` | 通过 | 通过 | 加载真实 Marked、高亮和 Markdown 增强插件。流式增量、停顿及收敛、KaTeX、Mermaid、代码高亮、原文复制和减少动态效果 |

两款浏览器均在 macOS arm64 启动真实二进制。109 的获取方式见 [首批交付](README.md#运行兼容检查)。移动宽度、横屏和软键盘使用桌面浏览器模拟。

## A 集成后的续验

`scripts/test-offline-ui.mjs` 已适配新版界面，静态语法检查通过。它启动隔离的真实 ChatRaw，在市场界面走 `POST /api/plugins/install-bundled` 安装 Excel、Markmap 和 PDF 导出，并将缺少 KaTeX 字体的 1.0.0 清单形态升级到新版。升级后检查禁用状态和用户设置保留，再启用并检查字体、公式和图表。普通聊天使用本地模拟 SSE，同时验证旧 CSV 清单和实际模型请求中的附件正文。

当前提交缺少 A 的 Agent 路由及本地市场安装接口。基线版离线脚本实跑曾遇到 `GET /api/agents` 和聊天绑定接口返回 404。新版离线脚本及真实网关测试均待在 A 集成提交上运行。G11/G12 正式结论、Windows 8 的 Chrome 109 与手机设备验收仍待更新。

在包含 A 和 B 的树中执行 `npm ci` 和 `npm run build`，再使用目标浏览器和装有后端及 Runner 依赖的 Python：

~~~sh
export CHROME_PATH=/absolute/path/to/chromium109
export PYTHON=/absolute/path/to/python
npm run test:chrome109
node scripts/test-agent-gateway-ui.mjs
~~~

现代 Chrome 使用实际可执行文件并把离线检查命令换成 `npm run test:offline-ui`。网关检查使用真实 ChatRaw 和 Runner，Agent 端为 ControlledAdapter。
