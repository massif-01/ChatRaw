# Codex 与 Claude 适配器交付

## 运行条件

| Agent | 本机验证版本 | Runner 配置 |
|---|---|---|
| Codex | Codex CLI 0.153.4 | 在服务账户 PATH 提供 Codex。app-server 通过进程标准输入输出通讯，复用服务账户的 Codex 原生认证与会话目录。由管理员配置 API key、Codex 管理的 ChatGPT 登录或经过授权的原生模型供应商。 |
| Claude | Claude Agent SDK 0.2.180，轮子内置 Claude Code 2.1.321 | 由 A/总控将 `claude-agent-sdk==0.2.180` 加入宿主 Runner 环境。当前适配器使用由服务账户环境提供的 `ANTHROPIC_API_KEY`。若未提供，返回未配置。已有 Claude Code 订阅登录不能作为此第三方 SDK 集成的认证依据。 |

Claude SDK 是可选依赖。未安装时模块仍可注册并报告不可用。两个适配器的 `model` 和 `reasoning` 均为可编辑的非秘密设置，留空沿用各 Agent 默认值。Codex 另提供 `mode`，设为 `plan` 可启用原生计划模式下的提问。模型目录取自原生握手，目录存在不代表账号已经获准调用其中的模型。

Claude 执行使用原生 `claude_code` 系统提示预设。SDK 0.2.180 在执行时按 CLI 默认加载用户、项目和本地设置，发现项目 `CLAUDE.md` 和 Skills。Skill 正文由 Claude 在调用时加载。适配器只提交本轮消息和附件。

健康探测验证程序和协议。Codex 使用 `account/read(refreshToken=false)` 读取配置状态，Claude 检查服务账户环境是否提供 API key。探测不发起模型请求，也不返回账号身份和凭据。配置存在时，认证验证仍为 `unknown`，实际模型调用为 `not_checked`。

## 能力与边界

| 能力 | Codex | Claude |
|---|---|---|
| 文本与工具 | `turn/start` 提交本轮文本，读取增量、原生推理摘要和工具生命周期。工具事件省略原始参数和输出。 | `ClaudeSDKClient` 流式输入与输出。流式文本按消息 ID 与 SDK 完整消息合并，展示工具调用状态和原生用量。 |
| 问答 | 转发原生 `request_user_input` 的批次、单选与可用自由输入。Secret 类型拒绝进入 ChatRaw 记录，原生定时输入到期以空答案收敛。 | `AskUserQuestion` 支持批次、单选、多选和自由输入，按原生问题文本与选项标签回传。 |
| 审批 | 支持命令、文件更改和受管网络审批，按原生选项限制回复。单独的权限授权、终端 stdin 审批、命令额外权限、策略修订及 MCP elicitation 目前不可用。 | `can_use_tool` 支持当次允许、拒绝和取消。收到带计划正文的 `ExitPlanMode` 时以计划审批展示。CLI 的原生权限规则仍决定何时弹出回调。 |
| 停止 | 匹配的 `turn/completed` 确认模型轮次结束。对本轮登记的后台终端调用原生终止接口，并复查终端列表。工具终止无法核实时保留 `unknown`。 | SDK 原生 interrupt，读取当前查询终止结果后释放该次专属 CLI。后续操作用新的客户端续接同一会话，旧流不会成为下一轮输入。 |
| 续接与恢复 | 空闲会话按已持久化 thread ID 续接。恢复只接受同一原生 turn 的明确完成或失败记录。已请求停止、原生中断或工具状态无法核实的执行保留 `unknown`。 | 空闲会话用已保存的 SDK session ID 与项目目录续接。失联执行仍为 `unknown`，因为 SDK 转录不能确认未完成操作的终态。 |
| 压缩 | `thread/compact/start`，等待专用 turn 终态。 | 原生 `/compact`，要求 SDK 提供命令且实际出现 `compact_boundary`。 |
| 附件 | `localImage` 传递 Runner 已接纳的 PNG、JPEG、WebP、GIF 文件。 | SDK 用户消息图片块，PNG、JPEG、WebP、GIF，每轮最多四张，每张最多 5 MiB。 |

两边均支持直接输入 `/compact`，通过同一原生压缩路径执行。其余 slash 输入原样交给运行时，Codex TUI 专用命令没有在 app-server 中复刻。通用文件上传、产物映射、steer 和 queue 未开放。Codex 每个 Runner 会话持有独立 app-server 连接，Claude 每次执行独占一个 SDK 客户端。取消等待终态的上限为 30 秒，超时或流断开后没有可靠原生终态则保留 `unknown`。

命令审批显示原生完整命令，公共字段上限为 100,000 字符。超限、缺失或触发凭据遮蔽的命令会被拒绝，并显示拒绝原因。

## 验证与验收边界

- `python3 -m unittest agent_runner.tests.test_adapter_base agent_runner.tests.test_c_adapter_protocol` 验证公共契约和确定性边界，包括 EOF、错误 thread/turn、秘密问答、超时后迟到回复、非图片附件、取消 ACK 无终态与恢复不重发。
- `CHATRAW_C_NATIVE_TESTS=1 python -m unittest agent_runner.tests.test_c_native_adapters` 使用两个实际原生程序、临时目录和仅监听 loopback 的模型替身。覆盖文本和跨客户端续接、Codex 已保存 turn 的恢复、问答、审批正反例、停止与下一轮、停止时拒绝迟到批准、压缩和图片出站。审批用临时工作区文件是否实际创建核验，图片用替身收到的模型请求核验。
- 本机原生测试使用 macOS arm64、Python 3.14.2 和表中版本。另在无凭据的临时账户目录验证两边健康探测报告已握手、认证未配置、模型调用未检查。
- Claude 原生上下文测试在本地模型端点确认三种设置来源的原生 Hook 均生效，收到原生预设、项目 `CLAUDE.md` 和 Skill 描述，直接发 slash 指令后才收到 Skill 正文。另在执行请求携带普通聊天的 system、历史、摘要、RAG 和 Skill 测试标记，连续两轮模型请求均未收到这些标记。
- 停止回归在 Codex 已返回运行中 shell 的会话 ID 后取消，并确认实际文件系统没有延迟写入。协议测试覆盖后台进程稍晚登记、跳过其他轮次的进程，以及未核实的停止在恢复后仍占用活动位。两边的命令审批都验证了 2,300 字符后的后缀可见且可执行，超出公共上限时标记文件未创建。
- 将 C 叶文件叠加到 A 的 `44013238` 快照，在临时目录跑通两边原生问答经 Runner 注册、SQLite 持久化、回复和原生确认的链路。两边均只发布一次 `done`，原生键及私有绑定未进入公共事件。
- G02、G05、G06、G08 已有本地原生协议配合模型替身的证据。RM-01 的 Linux 服务账户、实际模型认证、浏览器到 Runner 的完整链路与现场重启仍待总控协调。现场需使用总控授权的真实 Codex 认证及 Claude API key 分别核验，测试替身不计为 `real_pass`。

协议来源 [OpenAI Docs 的 Codex App Server](https://learn.chatgpt.com/docs/app-server)、[Claude Agent SDK Python](https://code.claude.com/docs/en/agent-sdk/python)、[Claude SDK 系统提示](https://code.claude.com/docs/en/agent-sdk/modifying-system-prompts)、[Claude SDK Skills](https://code.claude.com/docs/en/agent-sdk/skills)、[Claude SDK 问答与审批](https://code.claude.com/docs/en/agent-sdk/user-input)、[Claude SDK 认证](https://code.claude.com/docs/en/agent-sdk/quickstart)。
