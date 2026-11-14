# RM-01 本地模型接线

2026-11-13 本机验证使用 macOS arm64、Python 3.14.2、Codex CLI 0.153.4、Claude Agent SDK 0.2.180 和内置 Claude Code 2.1.321。10.10.99.98 的模型服务为 vLLM `0.21.1rc1.dev104+g301d98647`。`GET /v1/models` 无需认证，返回 `RM-01 VLM`，目录声明上下文上限为 262,144 tokens。

## 现场配置

所有 Agent 均选择 `RM-01 VLM`。模型服务使用明文局域网 HTTP。本机验证使用临时原生 home，Claude 使用非秘密占位值满足适配器对 `ANTHROPIC_API_KEY` 的检查。

| Agent | 地址和设置 | 已验证到哪一层 |
|---|---|---|
| Codex | 自定义 provider，`base_url=http://10.10.99.98:58000/v1`，`wire_api=responses`，`requires_openai_auth=false`，`supports_websockets=false`。复测脚本含完整 TOML。 | 本机原生 app-server 纯文本和工具回合完成。 |
| Claude | `ANTHROPIC_BASE_URL=http://10.10.99.98:58000`，显式设置模型，并将 `ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS}_MODEL` 指向同一模型。 | 本机原生 SDK 的 Read 工具回合完成。 |
| Hermes | `model.provider: custom`，`model.base_url: http://10.10.99.98:58000/v1`，使用 Chat Completions。 | 已探测 HTTP 协议，原生回合由 A 现场验收。 |
| Pi | Runner 用户的 Pi `models.json` 设 `baseUrl: http://10.10.99.98:58000/v1`、`api: openai-completions`，Runner 选择该自定义 provider 和模型。 | 已探测 HTTP 协议，原生回合由 A 现场验收。 |
| DeepSeek Harness | 0.2.2rc2 的 SDK profile 使用 Anthropic Messages。设 `DEEPSEEK_BASE_URL=http://10.10.99.98:58000/v1` 和本地占位 `DEEPSEEK_API_KEY`。 | 已探测 HTTP 协议，原生模型选择和回合由 A 现场验收。 |

本机 Codex 在系统代理路径收到 HTTP 503。给临时进程加 `NO_PROXY=10.10.99.98` 和 `no_proxy=10.10.99.98` 后，同一端点的文本和工具回合通过。现场若有代理，为该内网 IP 配置相同的直连例外。

## 证据和边界

- 三种 HTTP 接口均流式返回 `READY` 并发出正常结束事件。命名工具探测分别收到 Chat Completions 的 `tool_calls`、Responses 的 `function_call`、Anthropic Messages 的 `tool_use`。手工回传探测字符串 `PROBE_OK` 后，真实模型在三个接口均准确回显。该探测由脚本提供工具结果。
- 原生回合确实执行了工具。Codex 执行 `exec_command`，Claude 执行 `Read`，均读取临时文件并返回 `RM98_NATIVE_OK`。脱敏的 [证据记录](evidence.ndjson) 同时保留 HTTP 探测和原生运行结果。
- 命名工具探测中，Chat Completions 带 `tool_calls` 时标记 `finish_reason=stop`，Messages 带 `tool_use` 时标记 `stop_reason=end_turn`。Claude 的独立原生工具回合已收敛。若其他原生客户端因该语义提前结束，兼容层可仅在完整工具调用已收到、且流正常结束时调整结束原因，仍由 .98 生成文本和工具调用。
- 当前 OpenAPI 未注册 `/v1/responses/compact`。Codex 配置使用 `capabilities.remote_compaction="unsupported"` 以选择本地压缩路径。实际压缩、停止及工具停止收敛、RM-01 .99 上的五 Agent 和浏览器全链路均待现场验收。

## 串行复测

从仓库根目录运行。先协调推理窗口，再显式选择模式。脚本无参数时只显示帮助。

```sh
python3 docs/agent-platform/handoffs/C-local-model-98/probe.py http
python3 docs/agent-platform/handoffs/C-local-model-98/probe.py native
```

`http` 包括模型目录、版本、流式文本、工具和 token 计数。`native` 需要上述 Codex CLI 和 Claude SDK，并使用临时 home 与标记文件。两种模式都串行执行，输出筛选后的 JSON 行。

[Codex 配置参考](https://developers.openai.com/codex/config-reference) · [Claude 网关配置](https://code.claude.com/docs/en/llm-gateway) · [Hermes 配置](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) · [Pi 自定义提供方](https://pi.dev/docs/latest/custom-provider)
