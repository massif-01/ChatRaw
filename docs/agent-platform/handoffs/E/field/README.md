# RM-01 浏览器现场证据

2026-11-13 在 macOS 27.0.1 arm64 用独立浏览器上下文访问 `http://10.10.99.99:51111`。

## Chromium 109 和 Chrome 157

- 在部署前端字节对应 `2d770f0` 时，真实 Chromium 109.0.5414.46 与 Chrome 157.0.8103.51 各加载 35 条同源静态或插件资源路径，打开五个 Agent 的各自设置。1280×850、320×740、390×844、740×320 下菜单和设置均位于视口内。横屏设置区可滚动。复验中外部请求、写入尝试和页面错误为零。
- 首轮异常来自 Playwright 1.29.2 在 HTTP 上注入的 Service Worker 拦截。通过 CDP 绕过后复验通过。Chrome 157 首轮另有一次设置字段超时，未捕获对应 HTTP 错误，逐次等待目录响应后复验通过，首轮超时根因未确认。
- Chromium 109 从独立验收聊天发出一条原生 Codex CLI 请求，使用 `10.10.99.98` 的现场模型。运行终态 `completed`，9 次可见正文更新。刷新后只有一条助手回复，Copy 触发的选区与服务端 Markdown 原文一致。拦截复制事件避免覆盖系统剪贴板。
- 运行详情热修 `agents.js?v=2` 在 Chromium 109 只读复验通过。暂缓三个真实事件流时，终态快照先到仍显示加载中。事件回放后，两个纯文本回合显示无额外详情，工具回合显示一项工具和一项已结束审批。消息 API 前后完全相同。

[结构化证据](rm01-chromium-20261113.json)。记录中的浏览器版本取自实际进程。窄屏为桌面尺寸模拟。

## Firefox 150.0.2

使用官方 Playwright 1.60.0 的 Firefox build 1522，实际可执行文件和进程均报告 Firefox 150.0.2。测试系统为 macOS 27.0.1 arm64。以 `c3308ad9956aba3e8829a810380ec7009782334c` 的根树前端构建，重建产物与该提交相同。之后截至 `8c0da0c` 的根树前端及插件字节相同。

| 检查 | 结果 |
| --- | --- |
| `test-agent-ui.mjs` | 通过。普通聊天、五个 Agent 的菜单与独立设置、会话绑定、问答审批、恢复、停止、压缩与附件。接口使用本地受控 fixture |
| `test-stream-markdown.mjs` | 通过。真实 Marked、高亮、公式、Mermaid、原文复制和减少动效 |
| `test-agent-run-details.mjs` | 通过。纯文本提示、详情回放、断线重连、工具和审批历史。兼容性测试脚本在真实 Chromium 109 也通过 |
| 部署入口和专用验收聊天 | 核心资源均为同源 200。恢复原生 Codex 既有回复，六条 Markdown 列表、空详情提示、复制原文通过。复制事件拦截避免覆盖系统剪贴板。前后消息一致，外部请求、写入尝试和浏览器错误为零 |
| 部署窄屏 | 320×740、390×844 通过。740×320 的已绑定 Codex 菜单上边缘位于 `-17px`，顶栏盖住上部，菜单仍可内部滚动。Chrome 157 的同尺寸、同聊天、同细指针环境同样复现 |

Firefox 150.0.2 可用上述核心界面。740×320 菜单缺陷待 B 修复。Firefox 侧的真实推理请求、Mozilla 品牌发行版、ESR 115 和实际手机设备不在本次证据内。

### B 线修复建议

在部署页选中已绑定 Codex 的验收聊天 `b1a8f3a5-2234-4945-bae0-1f4a4b4372d6`，用 740×320 的桌面视口打开 Agent 菜单。菜单底边 217px，允许高度 234px，顶边因此为 -17px。可用空间由实际锚点至可视视口顶部或固定顶栏下缘决定。建议在打开菜单及视口变化时，将向上展开的最大高度限制到这段空间，保留内部滚动。复验时同时检查菜单与固定顶栏的相对位置。现有短屏规则用视口高度减固定值，无法覆盖当前锚点位置。该现象也能在细指针 Chrome 157 复现，建议修正通用布局。

[现场数据](rm01-firefox-20261113.json) · [Firefox 既有回复回放](firefox-codex-replay.png) · [横屏裁切截图](firefox-landscape-menu.png)

### 重跑 Firefox

使用官方 Playwright 1.60.0 安装 Firefox，设置 `CHATRAW_PLAYWRIGHT_MODULE` 为该安装的 `playwright-core/index.mjs`，`CHATRAW_TEST_ENGINE=firefox`。macOS 27 本次启动通过为 Firefox 进程设置临时 `CFFIXED_USER_HOME`，系统权限未调整。用 `PYTHON` 指定 fixture 环境，然后从仓库执行下列命令。 [Playwright Firefox 说明](https://playwright.dev/docs/browsers#firefox) · [macOS 27 启动问题](https://github.com/microsoft/playwright/issues/42768)

~~~sh
npm run build
node scripts/test-agent-ui.mjs
node scripts/test-stream-markdown.mjs
node scripts/test-agent-run-details.mjs

CHATRAW_TEST_URL=http://10.10.99.99:51111 \
CHATRAW_TEST_CHAT_ID=b1a8f3a5-2234-4945-bae0-1f4a4b4372d6 \
node scripts/test-firefox-deployed-readonly.mjs
~~~
