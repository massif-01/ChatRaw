# Codex 现场压缩与前台停止复查

2026-11-13。对 .99 的 Runner SQLite、两个验收 thread 的 Codex 0.153.4 原生 rollout 和测试目录进行只读核查。本机用同版 Codex 和 loopback 模型替身复现。此次未发起 .98 推理。

## 压缩后请求被模型服务拒绝

- ChatRaw session `2fa5efdd1bfa4e41ad0673570446a1b2` 对应同一个原生 thread `01a1d534-4b2b-7aa2-85a6-f7f761d62bd7`。compact run `b892d61229604a969fadde19a3d9bef4` 的原生 rollout 在 21:59:23 写入 `compacted`。替换历史有四条 user 消息，早期识别码仍在。
- continuity run `cb7fea5232db43f093a71b0be18bef57` 追加的第一项是原生 developer 权限说明，其后是环境和用户消息。原生 turn 在 121 ms 内收到 HTTP 400 `System message must be at the beginning.`。公开 ledger 记录 `codex_native_failed`。
- 用 `remote_compaction="unsupported"` 的隔离 Codex 0.153.4 向本地 HTTP 接收端复现，压缩后首个真实 Responses 请求的 `input` 角色顺序为 `user, user, developer, user, user`。现场 vLLM `301d98647` 的 HF renderer 原样传递消息顺序给 chat template。现有记录未保存现场 HTTP 请求体，结合原生 rollout、400 和本机接收端证据，故障定位在本地模型的消息模板兼容层。

建议在经批准的 Codex 专用 Responses 兼容入口上，将顶层 instructions 与原生 developer/system 文本按原序合并为唯一首位指令，保留其余消息、工具 ID、图片和 SSE 原样，然后转发给 .98。也可由模型服务 owner 选择带相应模板兼容修复的 vLLM 构建。当前 vLLM 主线已有集中前置 system 的实现。复验先用新 managed 会话验证普通回合、真实压缩与同 thread 续接，再验证工具和图片边界。现有会话历史、权限指令和现场配置未修改。

[Codex 手动压缩实现](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/compact.rs) · [现场 vLLM renderer](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/renderers/hf.py) · [vLLM 主线模板处理](https://github.com/vllm-project/vllm/blob/main/vllm/renderers/hf.py)

## 前台工具停止证据

- run `e05b8525931c4d1585cae79770c7be3d` 的目标调用 `call_b77a12758b95ee45` 设置 `yield_time_ms=30000`。原生 rollout 记录 `aborted by user`，随后记录同 turn 的 `turn_aborted`。Codex 源码表明这是工具调度任务中断的文本，未携带进程退出证据。公开 ledger 缺少 `item/completed`。只读复查有 `.started`、无 `.late`，测试目录下仅见对应 app-server 父子进程。既有 `unknown` 保留。
- 本机真实 Codex 可在 shell 写出 `started` 后约 0.24 秒才将该调用列入 `thread/backgroundTerminals/list`。立即中断复现 `unknown` 和无延迟写入。Codex 源码也显示 spawn 与进程登记之间存在异步步骤。
- 适配器在发出 `turn/interrupt` 前，最多用 0.5 秒核对本轮已开始、且已越过审批门的命令是否完成登记。随后仍使用原生终止确认和复查。超时继续发出 interrupt，工具终止无法核实时仍返回 `unknown`。原生回归使用前台 shell 写 `started` 后立即停止，检查 `cancelled` 和文件系统无延迟写入。后台、跨轮归属和未知恢复回归一并通过。

建议 A 在新 managed 聊天运行一个只写本轮临时标记的前台 sleep，捕获审批、开始、停止和单一终态，并在完整延时后只读检查 `.late`。本机模型替身测试不替代 .99/Linux 现场复验。

[Codex 工具调度中断](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/tools/parallel.rs) · [Codex 进程登记与终止](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/core/src/unified_exec/process_manager.rs)
