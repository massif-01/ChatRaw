# Hermes Integration

ChatRaw can route selected messages to a local or confirmed remote Hermes API Server through the Hermes Router plugin. ChatRaw still owns the chat UI, local chat list, message history, markdown rendering, export flow, and plugin hooks. Hermes owns its agent, tool, MCP, and session-side state.

This integration does not use A2A or MCP as the main chat transport. Browser plugins do not call Hermes directly, and `/api/proxy/request` remains blocked from localhost and private network targets.

## Prerequisites

Start Hermes independently and expose its local API server:

```env
API_SERVER_ENABLED=true
API_SERVER_KEY=<strong-secret>
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
```

```bash
hermes gateway
```

The current official Hermes API Server requires `API_SERVER_KEY`, including loopback-only binds. ChatRaw treats its saved API Server Key as optional so compatible no-auth servers can be used, but **Check** still probes `/v1/models`; official Hermes will return 401 until the matching key is saved.

The default ChatRaw Hermes settings are:

- Base URL: `http://127.0.0.1:8642/v1`
- Model: `hermes-agent`
- API key service id: `hermes`
- Optional session key service id: `hermes-session-key`

## Configure ChatRaw

1. Open ChatRaw and go to **Plugins**.
2. Install and enable **Hermes Router**.
3. Open the Hermes plugin settings.
4. Save the Hermes base URL and model name.
5. Enter the Hermes `API_SERVER_KEY` if the server requires one. Official Hermes requires it. Empty API key input does not delete an existing key; use **Clear key** to remove it.
6. Optionally enter a Session Key. Empty session key input does not delete an existing key; use **Clear session key** to remove it.
7. Use **Save** to persist the settings, then use **Check** to call `/api/hermes/health` with the saved configuration.
8. Turn on the Hermes toolbar toggle when a message should route through Hermes. The toggle is browser-local and defaults to off.

## Remote Base URLs

Loopback Base URLs such as `http://127.0.0.1:8642/v1`, `http://localhost:8642/v1`, and IPv6 `::1` are allowed by default.

To use a non-loopback Hermes server:

1. Expand **Remote Base URL access**.
2. Enter the remote URL in **Allowed remote base URLs**. Use one URL per line or comma-separated values.
3. Click **Review and enable remote URLs**.
4. Read the full warning, scroll to the bottom, check the confirmation box, and confirm.
5. Click **Save**.
6. Use **Check** to verify the saved configuration.

The backend canonicalizes the allowed list by trimming entries, lowercasing and punycoding hosts, removing a single trailing slash, deduplicating, sorting, and joining with newlines. Remote Base URL paths must be empty or simple ASCII paths such as `/v1` or `/api/v1`. If the allowed list is changed after confirmation, ChatRaw marks the confirmation as stale and the remote URL is rejected until the warning is confirmed again.

## Execution Modes

`chat_completions` is the default mode. The backend bridge calls Hermes `/chat/completions` and maps the response back into ChatRaw's existing JSON or NDJSON chat contract.

`runs` creates a Hermes run through `/runs`, subscribes to `/runs/{run_id}/events`, and maps text and reasoning deltas into the same ChatRaw assistant bubble. Tool progress is ignored by default and is not saved into final assistant `content`. If Hermes reports that approval is required, ChatRaw shows a clear error because an approval UI is not implemented.

The execution mode is saved in the backend plugin settings as `apiMode`. It is not a `route_message` return value and is not accepted in chat request bodies.

## Security Boundaries

- Hermes route selection is host-limited: the plugin may only return `{ success: true, route: "hermes" }`.
- The host maps `hermes` to the same-origin `/api/hermes/chat` endpoint.
- The browser never receives the Hermes API key or Session Key in plaintext.
- Hermes base URL must be `http` or `https`.
- Loopback hosts such as `localhost`, `127.0.0.1`, and `::1` are allowed by default.
- Non-loopback hosts are allowed only when the backend-normalized Base URL is listed in `allowedRemoteBaseUrls` and the saved risk-confirmation snapshot matches the current canonical list.
- Unicode domain names are normalized to punycode before allowlist and risk-confirmation comparison.
- Base URL paths must be empty or simple ASCII paths such as `/v1` or `/api/v1`; Unicode paths, percent escapes, dot segments, empty segments, and repeated slashes are rejected.
- The remote URL warning is a user-facing confirmation flow, not a sandbox boundary against already trusted same-origin UI code or installed plugins. The backend enforces the saved Hermes plugin configuration.
- URL credentials, query strings, and fragments are always rejected.
- Hermes bridge requests use `allow_redirects=False`; any 3xx response is blocked instead of followed.
- `/api/hermes/*` is not a plugin metadata or static resource path and should not be exempted from normal API rate limiting.
- `/api/proxy/request` is not used for Hermes and continues to reject localhost and private network targets.

## Troubleshooting

- **Hermes plugin is not enabled**: install the Hermes Router plugin and enable it in ChatRaw's plugin panel.
- **Remote Hermes base URL requires risk confirmation**: add the URL to **Allowed remote base URLs**, review the warning, confirm it, and save settings.
- **Remote Hermes base URL risk confirmation is stale**: the allowed list changed after confirmation. Review and confirm the warning again, then save settings.
- **Hermes base URL must be listed in allowed remote base URLs**: the saved Base URL is remote but does not match any normalized URL in the allowed list.
- **Invalid Hermes base URL / Allowed remote Hermes base URL**: use `http` or `https`; remove credentials, query strings, fragments, and complex paths.
- **Hermes API error (401)**: the saved API key is missing or does not match Hermes `API_SERVER_KEY`.
- **Hermes network error / timeout**: confirm `hermes gateway` is running and listening on the configured host and port.
- **Hermes run requires approval**: Runs approval events are surfaced as a clear error; ChatRaw does not implement an approval panel.
- **Hermes run event stream ended before completion**: Hermes closed the events stream without a terminal event. ChatRaw stops the run best-effort and does not save a partial assistant message as a completed answer.

## Manual QA Checklist

- Install the Hermes Router plugin from the plugin market.
- Enable and disable the ChatRaw plugin; the toolbar button should appear and disappear with the plugin state.
- Toggle Hermes off; a normal message should still use the default ChatRaw backend.
- Toggle Hermes on; a normal message should route to `/api/hermes/chat`.
- Save base URL, model, API key if required, and optional Session Key with **Save**, then use **Check**.
- Add multiple allowed remote Base URLs, confirm the warning, save, and verify a listed remote Base URL can be checked.
- Modify the allowed remote list after confirmation; **Check** should fail until the warning is confirmed and saved again.
- Confirm **Check** calls `/api/hermes/health` and not `/api/proxy/request`.
- Test stream and non-stream chat settings.
- Test `chat_completions` and `runs` modes.
- Test a search/RAG-style `before_send` plugin together with Hermes routing; the enhanced body should still reach the Hermes bridge.
- Create a new chat, switch back to an old chat, and delete a chat; Hermes session ids should remain tied to final ChatRaw `chat_id` values.
- Stop generation while a Runs request is active; ChatRaw should request `/runs/{run_id}/stop` without exposing the run id to the browser.

# Hermes 集成

ChatRaw 可以通过 Hermes Router 插件，把选定消息经由后端安全桥接路由到本机或已确认放行的远程 Hermes API Server。ChatRaw 仍负责聊天 UI、本地对话列表、消息历史、Markdown 渲染、导出流程和插件 hooks；Hermes 负责 agent、工具、MCP 配置和 session 侧状态。

该集成不把 A2A 或 MCP 作为主聊天通道。浏览器插件不会直接调用 Hermes，`/api/proxy/request` 也继续拒绝 localhost 和私网目标。

## 前置配置

独立启动 Hermes，并暴露本机 API Server：

```env
API_SERVER_ENABLED=true
API_SERVER_KEY=<strong-secret>
API_SERVER_HOST=127.0.0.1
API_SERVER_PORT=8642
```

```bash
hermes gateway
```

当前官方 Hermes API Server 要求设置 `API_SERVER_KEY`，即使只绑定 loopback 也一样。ChatRaw 会把保存的 API Server Key 视为可选，以兼容无鉴权服务；但 **检查** 仍会探测 `/v1/models`，因此官方 Hermes 在未保存匹配 key 时会返回 401。

ChatRaw 的 Hermes 默认设置为：

- Base URL：`http://127.0.0.1:8642/v1`
- Model：`hermes-agent`
- API key service id：`hermes`
- 可选 Session Key service id：`hermes-session-key`

## 配置 ChatRaw

1. 打开 ChatRaw，进入**插件**。
2. 安装并启用 **Hermes Router**。
3. 打开 Hermes 插件设置。
4. 保存 Hermes base URL 和 model name。
5. 如果服务要求，输入 Hermes `API_SERVER_KEY`。官方 Hermes 需要填写。API key 输入框留空不会删除已有 key；需要点击 **Clear key** 才会清除。
6. 可选输入 Session Key。Session key 输入框留空不会删除已有 key；需要点击 **Clear session key** 才会清除。
7. 点击 **保存** 保存配置，然后点击 **检查** 使用已保存配置调用 `/api/hermes/health`。
8. 需要让某条消息走 Hermes 时，打开输入框工具栏中的 Hermes toggle。该 toggle 是浏览器本地偏好，默认关闭。

## 远程 Base URL

`http://127.0.0.1:8642/v1`、`http://localhost:8642/v1` 和 IPv6 `::1` 等 loopback Base URL 默认允许。

如需使用非 loopback Hermes 服务：

1. 展开 **远程 Base URL 放行**。
2. 在 **允许的远程 Base URL** 中填写远程地址，一行一个或用逗号分隔。
3. 点击 **查看风险并启用远程地址放行**。
4. 阅读完整警示内容，滚动到底部，勾选确认框并确认。
5. 点击 **保存**。
6. 点击 **检查** 验证已保存配置。

后端会把允许列表规范化：trim 每一项、host 小写并转为 punycode、去掉单个末尾 `/`、去重、排序，并用换行拼成确认快照。远程 Base URL path 必须为空或 `/v1`、`/api/v1` 这类简单 ASCII path。确认后如果修改允许列表，ChatRaw 会把确认状态视为过期；远程 URL 会被拒绝，直到重新确认风险并保存。

## 执行模式

`chat_completions` 是默认模式。后端桥接调用 Hermes `/chat/completions`，并把响应映射回 ChatRaw 现有 JSON 或 NDJSON 聊天 contract。

`runs` 会通过 `/runs` 创建 Hermes run，订阅 `/runs/{run_id}/events`，并把文本和 reasoning delta 映射到同一个 ChatRaw assistant 气泡。工具进度默认忽略，不保存进最终 assistant `content`。如果 Hermes 返回需要审批的事件，ChatRaw 会显示清晰错误；当前不实现审批面板。

执行模式保存在后端插件设置 `apiMode` 中。它不是 `route_message` 返回值，也不接受来自聊天请求 body 的覆盖。

## 安全边界

- Hermes 路由选择由宿主限制：插件只能返回 `{ success: true, route: "hermes" }`。
- 宿主把 `hermes` 映射到同源 `/api/hermes/chat`。
- 浏览器永远拿不到 Hermes API key 或 Session Key 明文。
- Hermes base URL 必须使用 `http` 或 `https`。
- `localhost`、`127.0.0.1`、`::1` 等 loopback host 默认允许。
- 非 loopback host 只有在后端规范化后的 Base URL 写入 `allowedRemoteBaseUrls`，且保存的风险确认快照与当前 canonical 列表一致时才会放行。
- Unicode 域名会先规范化为 punycode，再参与 allowlist 和风险确认快照比较。
- Base URL path 必须为空或 `/v1`、`/api/v1` 这类简单 ASCII path；Unicode path、percent escape、dot segment、空 segment 和重复 slash 都会被拒绝。
- 远程 URL 警示是面向用户的确认流程，不是用来隔离已信任的同源 UI 代码或已安装插件的沙箱边界。后端会按已保存的 Hermes 插件配置执行校验。
- URL 凭据、query 和 fragment 始终会被拒绝。
- Hermes bridge 请求使用 `allow_redirects=False`；任何 3xx 响应都会被阻断，不会跟随跳转。
- `/api/hermes/*` 不是插件元数据或静态资源路径，不应被加入普通 API 限流豁免。
- Hermes 不使用 `/api/proxy/request`；该 proxy 继续拒绝 localhost 和私网目标。

## 常见错误

- **Hermes plugin is not enabled**：请安装 Hermes Router 插件，并在插件面板中启用。
- **Remote Hermes base URL requires risk confirmation**：请把地址加入 **允许的远程 Base URL**，阅读并确认风险，然后保存设置。
- **Remote Hermes base URL risk confirmation is stale**：允许列表在确认后发生了变化。请重新查看并确认风险，然后保存设置。
- **Hermes base URL must be listed in allowed remote base URLs**：已保存 Base URL 是远程地址，但没有命中规范化后的允许列表。
- **Invalid Hermes base URL / Allowed remote Hermes base URL**：请使用 `http` 或 `https`，并移除 URL 凭据、query、fragment 和复杂 path。
- **Hermes API error (401)**：未保存 API key，或保存的 API key 与 Hermes `API_SERVER_KEY` 不一致。
- **Hermes network error / timeout**：确认 `hermes gateway` 正在运行，并监听配置中的 host 和 port。
- **Hermes run requires approval**：Runs 审批事件会显示为清晰错误；ChatRaw 当前不实现审批面板。
- **Hermes run event stream ended before completion**：Hermes 在终态事件前关闭 events stream。ChatRaw 会 best-effort stop run，并且不会把 partial assistant message 当作完整回答保存。

## 手动验收清单

- 从插件市场安装 Hermes Router。
- 启用和禁用 ChatRaw 插件；工具栏按钮应随插件状态出现和消失。
- 关闭 Hermes toggle；普通消息仍走默认 ChatRaw 后端。
- 打开 Hermes toggle；普通消息应路由到 `/api/hermes/chat`。
- 点击 **保存** 保存 base URL、model、按服务要求填写的 API key 和可选 Session Key，然后点击 **检查**。
- 添加多个允许的远程 Base URL，确认风险并保存；确认命中的远程 Base URL 可以通过 **检查**。
- 确认后修改允许列表；在重新确认并保存前，**检查** 应失败。
- 确认 **检查** 调用 `/api/hermes/health`，不调用 `/api/proxy/request`。
- 测试 stream 和 non-stream 聊天设置。
- 测试 `chat_completions` 和 `runs` 模式。
- 与搜索/RAG 类 `before_send` 插件同时启用；增强后的 body 应继续到达 Hermes bridge。
- 新建对话、切换回旧对话、删除对话；Hermes session id 应始终绑定最终有效的 ChatRaw `chat_id`。
- Runs 请求执行中点击停止生成；ChatRaw 应请求 `/runs/{run_id}/stop`，且不把 run id 暴露给浏览器。
