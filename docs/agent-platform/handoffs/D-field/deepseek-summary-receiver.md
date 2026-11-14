# DeepSeek 审批后总结 · 离线接收端证据

2026-11-14。对应 RM-01 原生验收记录 103、107 及集成基线 `836822c`。归档只包含哈希、结果配对和断言，原始请求与会话副本保留在受限目录。

|边界|实际接收|断言|
|---|---|---|
|合成历史，真实 SDK 和本地 Bash|初次沙箱失败、同一命令单次获准且无输出地完成、后续只读 Bash 沙箱失败|4 个请求逐步保留 3 对调用与结果。调用顺序、ID、完整命令和升级参数匹配。标记文件写入，批准调用的结果文本为 `(no output)`。|
|原会话 seq28 后|2 对调用与结果|获准调用的命令、`sandbox_permissions`、`justification` 和 `(no output)` 完整保留。|
|原会话 seq54 后、最终总结前|7 对调用与结果、6 段历史 reasoning|调用参数、ID、结果文本和顺序逐项一致。获准成功、后续 Bash 失败和成功的 read/glob 各自保留。|

重建使用与现场同 SHA-256 的 Linux `0.2.2rc2` runtime。离线恢复会话副本，从原生 `deriveMessages()` 取两个历史前缀，用保存的同一 request header 与 tool history 通过原生 LLM 路由发给回环接收端。两个前缀都保留 31 个工具、8192 输出预算及 `enable_thinking=true`。重建没有新增模型可见问句，也没有执行原会话工具。它验证了原生序列化行为，历史现场 HTTP 字节没有录制。[接收端哈希与配对断言](evidence/deepseek-summary-receiver.json)

原生 seq25 是该调用的 `allowed-once`，seq27 是进程退出码 0，seq28 是 `isError:false` 和 `(no output)`。Bash 渲染只追加非零退出码或异常标记，Chat Completions 工具消息保留 `tool_call_id` 和文本，未序列化 `isError` 或独立审批审计。模型在 seq31 和 seq38 已正确识别成功，到 seq43 才把较早的失败与成功写入混淆。成功状态的表达差异是待检验因素。[Bash 渲染](https://github.com/deepseek-ai/deepseek-harness/blob/ddac96760b6edf8fa0fe17cbdcf0b512f4c12b2c/packages/shell/tool-bash/src/render.ts#L28-L64) · [Harness 历史转换](https://github.com/deepseek-ai/deepseek-harness/blob/ddac96760b6edf8fa0fe17cbdcf0b512f4c12b2c/packages/llm/llm-pi-ai/src/context.ts#L32-L46)

## 单变量对照与候选接口

总结前的两个请求均固定 `temperature=0`，只在获准调用的原工具结果文本末尾追加一行 `[exit code: 0]`。其余模型参数、历史、工具及权限均相同。对照由现场负责人执行，离线结果不作为模型因果结论。

若对照支持显式成功状态，最小落点是宿主版本化 native patch 装载官方 `tools/post-execute` 扩展。Bash 原生配置只有后台与超时选项。扩展先获取 `next()` 的决定，只在其接受且未替换 canonical value、调用为目标路由的原生 Bash、真实结果 `isError:false` 且 `value.kind === "foreground"`、`exitCode === 0`、`signal === null`，并确认未超时、中止、停止或被沙箱拒绝时，在原工具结果附上退出码。成功由原生执行值判定，包括无 stdout 的命令。拒绝、非零、异常、取消、仍运行或转后台的任务均不附成功标记。是否把规则进一步限于原生审计确认的单次获准 Bash，以对照支持的变更范围为准。[Bash 原生配置](https://github.com/deepseek-ai/deepseek-harness/blob/ddac96760b6edf8fa0fe17cbdcf0b512f4c12b2c/packages/shell/tool-bash/src/index.ts#L40-L61) · [原生后处理接口](https://github.com/deepseek-ai/deepseek-harness/blob/ddac96760b6edf8fa0fe17cbdcf0b512f4c12b2c/packages/core/tools/src/pipeline.ts#L484-L532)

扩展只替换原工具结果的模型可读内容，保持同一 `toolCallId`、命令、原生执行值、错误标志及审批/进程审计。追加文本会随原生 `tool/result` 持久化，续接会看到同一份结果。验证应覆盖实际接收端的退出码 0、非零、拒绝、异常、取消和后台任务，并核对单次批准和未批准时的文件副作用。方案尚未实现。
