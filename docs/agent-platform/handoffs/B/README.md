# B 线前端交付

## 集成

B 线提交建立在公共契约 `6874553` 与 E 首批资源提交上。总控可从已有 E 资源的集成树摘取 B 线业务提交，保留集成树的 PostCSS 锁，并运行 `npm run build`。主入口按顺序加载本地 Marked、Collapse、Alpine、增量渲染模块和 Agent UI 模块。B 提交只含源码，压缩产物在集成树生成。

五插件的市场安装和升级使用 `POST /api/plugins/install-bundled`。可编辑参数取自 `GET /api/agents` 的 `settings_schema`，使用原有插件设置 API 保存。模型建议来自健康检查的 `models`。可执行程序、凭据和宿主项目访问仍由执行服务管理。浏览器工作目录选择只发送受控项目 ID 或独立工作目录类型。

原有 Hermes Router 的市场包可原位升级到 Hermes Agent 插件，升级入口复用 A 的本地 bundle 安装。已安装的 Markdown 增强和思维导图插件也有升级入口。新版本等正文收敛后处理公式和图表，旧版已插入的增强节点在正文不变时会保留。共享 Markdown 把原始 HTML 显示为文字并限制链接协议，原文复制保留源 Markdown。

普通聊天走原上下文处理链。Agent 路径仅发送当前输入和附件引用。Agent 草稿及待核实提交保存在当前标签页的 sessionStorage，换聊天和刷新可以恢复。任务状态、交互是否有效及已保存消息由后端提供。

## 重跑

从 A、B、E 已集成的仓库执行。Python 环境需包含 `backend/requirements.txt` 和 `agent_runner/requirements.txt` 的依赖。将浏览器路径换成目标 Chromium/Chrome 的实际可执行文件。

```sh
npm ci
npm run build
export CHROME_PATH=/absolute/path/to/chromium
export PYTHON=/absolute/path/to/python
node scripts/test-agent-ui.mjs
node scripts/test-stream-markdown.mjs
node scripts/test-agent-gateway-ui.mjs
```

`test-agent-ui.mjs` 使用浏览器协议 fixture，验证插件安装、编辑、健康检查、禁用、启用和卸载，及绑定、两个发送入口、未知接收核对、断线重放、审批、问答、附件、产物下载、压缩和停止。默认读取构建后的静态资源。可用 `CHATRAW_TEST_ASSET_DIR` 指向另行生成的两个压缩文件。测试禁止浏览器外部请求。

`test-stream-markdown.mjs` 加载真实 Marked、高亮和 Markdown 增强插件，覆盖旧段 DOM 保留、仅新片段显现、停顿后 KaTeX 和 Mermaid 收敛、Python 高亮、Markdown 原文复制、减少动态效果和空终稿。UI 测试另覆盖表格、列表、Markmap 和复制按钮。

`test-agent-gateway-ui.mjs` 启动真实 ChatRaw ASGI 和 Runner HTTP，以 A 的 ControlledAdapter 模拟原生 Agent。关闭首个浏览器上下文后，第二个独立上下文选择同一聊天并审批，检查最终正文替换、文件落在受控工作目录、刷新仅有一条回复。默认使用当前集成树。可用 `CHATRAW_GATEWAY_CODE_ROOT` 指向单独的 A 源码快照，快照须包含已构建的 B 前端及插件市场。截图可用 `CHATRAW_EVIDENCE_DIR` 指定，测试进程和临时数据在结束时清理。

## 验证边界

- 浏览器环境为 macOS arm64 上的 Chromium 109.0.5414.46 和 Chrome 157.0.8103.51。移动检查使用 320、375、390、430 CSS 像素和 740×320 横屏。键盘检查模拟可视视口缩小，验证焦点控件和弹窗底部动作仍在可视范围。
- 实际后端纵向检查使用 A 工作树 `44013238f0297fa41e33e26144c395e5d7720df6` 上的开发源码快照。它包含当时尚未提交的 gateway、数据库投影和本地插件安装。对应文件摘要记录于下方。五种真实 Agent 的原生进程、认证、RM-01、iPhone Safari 和 Android Chrome 设备仍需集成验收。
- 基线普通聊天后端回归检查中，上下文压缩 20 项、HTTP TLS 4 项、Skills 57 项、字体路由 2 项通过。生产镜像与发布验收由集成树重跑。
- 已发送附件名称会显示在发起浏览器的用户消息下。现有消息投影提供 `run_id`，跨设备历史可重放产物；恢复后的用户消息正文取自后端投影。

### A 快照 SHA-256

```text
b132fb99e2fa2e7f303d766d4aaab914cd32e8dea6ea60047e602bb47f4c953c  backend/main.py
d64a9b6996584ba2be8889874a835bc7a8922702f0a723464c6ee18152d33f6c  backend/agent_gateway.py
9be16e1d04a6d5217d068029a4da84d6900b1b6d3e338bff5c0aca736fa8af8a  backend/agent_storage.py
d68703bcfbf3c54e7d65a45cc84872af2c64942df4068d65bcb79868dce857ca  backend/bundled_plugins.py
4b25d9812d9636e1081ef16299f0ab00ac95345c0660c62737097ea5862203ae  agent_runner/runtime.py
abd7d5dc19b7328b890dbdab1ee6d7ec0b72ac23aee0b927301bcaaa374e580a  agent_runner/server.py
bcd803674b0867d4d09b0355ca73b39c659ffdfa2f5be46aa0aee9ad8f52c10e  agent_runner/store.py
```
