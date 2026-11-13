# DeepSeek 官方 Flash 原生接入复验

2026-11-14。基线为集成提交 `4f3f788`，Codex CLI `0.153.4`，Claude Agent SDK `0.2.180` 和内置 Claude Code `2.1.321`。两端使用 `deepseek-flash`，官方目录当前对应 DeepSeek-V4.1-Flash-1017，支持 Responses、Messages 和图片输入。现场配置、密钥注入和真实请求由 A 执行。现有会话绑定保留，测试用新聊天及独立工作目录。[DeepSeek 模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)

## Codex

为隔离的 `CODEX_HOME` 写入 `config.toml`，沿用验收环境的沙箱策略。从官方手动接入页的 `models.json` 提取 `slug=deepseek-flash` 一项，保留官方模型指令、上下文、`freeform` patch、文本和图片模态以及 `low/high/max`。将 `supports_search_tool` 设为 `false`，并用绝对路径引用 catalog。本机 0.153.4 已读入官方条目并在 `model/list` 返回 Flash、三档推理、文本及图片。官方安装脚本的 Alpha Search 路径要求 0.164，当前复验关闭搜索。[官方 Codex 接入](https://api-docs.deepseek.com/quick_start/agent_integrations/codex/)

```toml
model = "deepseek-flash"
model_provider = "deepseek-official"
model_catalog_json = "/absolute/isolated/codex-home/models.json"
model_reasoning_effort = "low"
model_reasoning_summary = "none"
web_search = "disabled"

[model_providers.deepseek-official]
name = "DeepSeek API"
base_url = "https://api.deepseek.com"
wire_api = "responses"
env_key = "CHATRAW_CODEX_DEEPSEEK_API_KEY"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0

[model_providers.deepseek-official.capabilities]
remote_compaction = "unsupported"

[shell_environment_policy]
exclude = ["CHATRAW_CODEX_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
```

独立 Runner 配置省略 `agents.codex.responses_compat_upstream`，使原生 app-server 直接向官方 `/responses` 发请求。Codex 插件选择 `model=deepseek-flash`、`reasoning=low`。官方 Responses 为无状态协议，要求客户端重放完整上下文。回环中原生 HTTP 使用 `store:false`、完整历史及匹配的工具调用和结果 ID，未使用 `previous_response_id`。本机 fixture 返回明文 `reasoning` 和 `custom_tool_call` 时，Codex 执行 `apply_patch` 并在下一请求重放明文推理及 `custom_tool_call_output`。官方只接受 `apply_patch` 这一种 custom tool。图片使用 `input_image`，原生 `localImage` 到线上的图片字节仍按矩阵验收。[Responses 兼容字段与工具](https://api-docs.deepseek.com/guides/responses_api/#compatibility-details)

官方文档没有列出 `/responses/compact`。显式 `/compact` 走 0.153.4 原生本地压缩并使用普通 `/responses` 请求。回环验证压缩与后续同 thread 回合。官方是否接受压缩后原生历史须现场验证。若失败，先记录具体 HTTP 状态、错误类型和压缩前后历史角色，再判断改动。`.98` 的模板错误证据只对应局域网服务。[Codex app-server API](https://learn.chatgpt.com/docs/app-server#api-overview)

## Claude

在隔离 Runner 环境配置以下变量。`ANTHROPIC_API_KEY` 由 A 从现有受限凭据载入。现有适配器以该变量检查并使用 `x-api-key`，同时主动清空 `ANTHROPIC_AUTH_TOKEN`。DeepSeek 官方 Messages 文档支持这条 API key 路径。Claude 插件选择 `model=deepseek-flash`、`reasoning=low`。

```sh
CLAUDE_CONFIG_DIR=/absolute/isolated/claude-home
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-flash
ANTHROPIC_DEFAULT_HAIKU_MODEL=deepseek-flash
ANTHROPIC_DEFAULT_SONNET_MODEL=deepseek-flash
ANTHROPIC_DEFAULT_OPUS_MODEL=deepseek-flash
CLAUDE_CODE_SUBAGENT_MODEL=deepseek-flash
CLAUDE_CODE_EFFORT_LEVEL=low
CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1
```

在独立 `CLAUDE_CONFIG_DIR/settings.json` 写入 `{"permissions":{"deny":["WebSearch","WebFetch"]}}`，保留原生工具审批。当前回环实际收到 `/anthropic/v1/messages?beta=true`、`deepseek-flash`、`thinking.type=adaptive`、`output_config.effort=low` 和 PNG base64。DeepSeek 将 `adaptive` 当作 enabled。一次获准的回环 Bash 只检查占位 Key 是否为空，验证该运行版本未把四个示例 provider 凭据传给普通子进程。`deepseek-flash` 在本机 CLI 发出 `unrecognized_model` 诊断，HTTP 请求仍使用正确模型名。1M catalog 标记和自动压缩阈值未纳入短回合复验。[DeepSeek Messages](https://api-docs.deepseek.com/guides/anthropic_api/) · [Claude Code 模型映射](https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code/) · [Claude Code 权限](https://code.claude.com/docs/en/permissions)

## A 的现场用例

每个 Agent 从新建 ChatRaw 聊天进入原生运行时。按顺序短回合执行，记录公开 run、native session/thread、终态、工具或审批 ID、有效模型与 token 使用。使用合成文本、图片和临时工作区。工具侧效应以工作区或原生账本核验。

| 用例 | 输入与验收 |
| --- | --- |
| C1 / L1 文本和续接 | 首轮给随机标记并要求仅回复 `READY`。在同一聊天下一轮只问标记，核对精确回显、相同原生 ID、流式正文及 completed。 |
| C2 工具 | 在工作区创建一个固定内容文件。确认真实 `apply_patch` 的原生文件变更、工作区内容和配对结果，再用只读工具复核。若模型改用 shell，记录工具正常但 custom patch 尚未覆盖。 |
| L2 工具 | 用原生 `Read` 读取临时 marker 文件。核对 tool/result 与回显，随后续接并确认同一 session。 |
| C3 / L3 图片 | 上传仅像素包含随机标记的合成 PNG，正文和文件名均不泄露答案。核对回显和原生图片类型，Codex 为 `input_image`，Claude 为 Messages `image`。 |
| C4 / L4 压缩 | 同一聊天发 `/compact`，等待原生压缩事件和 completed，再追问首轮标记。Codex 验证普通 `/responses`，Claude 验证 `compact_boundary`。 |
| C5 / L5 审批 | 使用会触发原生审批的固定单次命令，分别在新聊天拒绝和允许一次。批准前与拒绝后 marker 不存在，允许后精确存在。核对完整命令和一次性决定。Codex 可明确请求 `require_escalated`，Claude 用原生 Bash 权限提示。 |
| C6 / L6 停止 | 对受控 `started → sleep → late marker` 工具链，在观察到 started 后点击停止。核对公开终态、所属进程退出和超过 sleep 窗口仍无 late marker。 |
| C7 / L7 原生问答 | Codex 用 Plan mode 的 `request_user_input`，Claude 用 `AskUserQuestion`。核对公开题目、提交回执和同一原生回合继续。模型未实际发出工具时记录未覆盖。 |

本机已有六项原生回环通过，覆盖两端续接、压缩和图片。另有两项使用 Flash 官方 catalog 和路径形状的真实原生 runtime 回环通过，覆盖 Codex stateless、明文推理重放、custom patch 及压缩，Claude 的 API key、模型、低档推理、图片与 Bash 占位凭据隔离。官方 HTTP 认证、真实生成和现场验收均待 A，当前无需修改适配器。
