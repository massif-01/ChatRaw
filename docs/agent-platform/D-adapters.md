# D 线交付 · Pi RPC 与 DeepSeek Harness

2026-11-12 · `codex/agent-platform-d-adapters` · 公共合同 v1

## Runner 接线

- 注册 `pi → agent_runner.adapters.pi.PiAdapter` 和 `deepseek → agent_runner.adapters.deepseek.DeepSeekAdapter`。两个工厂均无参，实例归属一个 Runner session。公共 base 无需修改。
- Pi 宿主配置需要 `executable` 和 `session_root`，均为绝对路径。使用 `@earendil-works/pi-coding-agent@1.5.2`，该发行包要求 Node ≥22.19。由管理员准备 Runner 账户可写的持久会话根目录。保留发行包目录结构及仓库中 `agent_runner/adapters/pi_extensions/chatraw.ts` 的相对位置。适配器用显式 `--extension` 装载配套扩展，启动时核对扩展实际注册。使用该运行账户的 Pi 认证和模型配置。
- DeepSeek 宿主配置需要 `dsh_home`，指向已存在、由 Runner 账户管理的绝对根目录。每个 ChatRaw session 在根目录下使用独立的原生 `DSH_HOME` 和 Python SDK runtime。给 Runner 的受控服务环境注入 `DEEPSEEK_API_KEY`，由官方 SDK 读取。可在相同服务环境设置可信的 `DEEPSEEK_BASE_URL`。SDK 通过匹配的官方 runtime wheel 自带程序，宿主无需为 DeepSeek 安装 Node。
- DeepSeek 依赖交 A 纳入 Runner 的 Python 环境。验证版本为 `deepseek-harness-sdk==0.2.2rc2`，其依赖固定 `deepseek-harness-runtime-bin==0.2.2rc2`，另要求 `pydantic>=2.12,<3`。SDK 要求 Python ≥3.10，Runner 合同要求 Python ≥3.11。RM-01 Python 3.12 落在声明范围内，实际 wheel、宿主沙箱与运行账户待现场验证。D 线未修改公共依赖与部署文件。
- 浏览器可编辑 Pi 的 `model`、`provider`、`thinking`。单独指定 `provider` 时，Pi CLI 要求同时指定 `model`。DeepSeek 可编辑 `model`、`reasoning_effort`，随官方 `sdk` profile 使用默认 DeepSeek provider。省略字段由原生程序决定；设置按 create/resume 边界取快照。两者均不接收浏览器提供的可执行路径、凭据或任意目录。
- `probe` 验证程序和协议。Pi 仅返回其 RPC 注册表提供的可用模型 ID 与 provider，DeepSeek 不合成模型列表。Pi 有可用当前模型、DeepSeek 有服务凭据配置时返回 `ready`，认证和模型请求仍为 `not_checked`。模型实际可用性需经独立测试。
- 为两个根目录准备持久挂载与备份。Pi 绑定原生 transcript 和 session ID，恢复前比对文件头 ID 和工作目录，再核对 Pi RPC 返回的同一身份。DeepSeek 保留原始 session ID 与独立 home，恢复只调用 `resume_session(id)`。两者都拒绝缺失的原会话，运行失联后使用公共 `recover_run` 的 `unknown`，没有重新发送原输入。

## 能力矩阵

|能力|Pi 1.5.2|DeepSeek Harness SDK 0.2.2rc2|
|---|---|---|
|文本、推理|RPC 实时文本及原生提供的推理增量|按已提交的 assistant 消息推送文本及推理。SDK 不发实时 token，`streaming_text=false`|
|工具|原生开始、更新、结束。省略原始参数和工具输出预览|原生工具调用和结果。省略原始参数和工具输出预览|
|问答|RPC 原生选择、确认、输入和编辑器。配套 `ask_user` 通过同一 RPC 传单选、多选、自定义文本和批次|原生 `ask_user_question` 支持批次和自由文本。计划审阅保留计划正文、选项和取消语义|
|工具审批|配套扩展在原生 `tool_call` 上审阅内置 `bash`、`write`、`edit`，仅允许一次或拒绝|启用原生审批请求，只映射该请求允许的一次授权、拒绝、取消。计划审阅使用原生问题通道|
|停止|清除待处理队列，调用 `abort`，用 `agent_settled.aborted` 或手动压缩的结束与命令响应确认|独占 runtime。等待原生 `shutdown` 确认其管理范围收敛，再由 SDK 释放并回收 runtime|
|压缩|原生 `compact` RPC|原生 `/compact`|
|图片|PNG/JPEG/GIF/WebP，所选模型需声明图片输入|PNG/JPEG/GIF/WebP，由原生 SDK 处理。直接视觉输入取决于所选模型|
|附件限制|单轮图片合计 8 MiB。普通文件返回能力错误|单轮图片合计 8 MiB。普通文件返回能力错误|
|队列、插话、产物|统一入口暂不开放原生队列、插话与产物登记|统一入口暂不开放原生队列、插话与产物登记|

Pi 扩展是工具级人工审批。进程权限由运行账户和操作系统约束。显式可选宿主字段 `extensions` 仅用于管理员核准的扩展路径。默认关闭 Pi 的扩展自动发现。外部扩展自身的执行、已授权命令派生的外部操作和项目文件读取仍遵循 Pi 原生权限。配套扩展保留 `bash` 完整命令及文件工具操作路径用于审批，超长命令直接拒绝。普通 RPC 确认问题按是/否问答呈现。原生编辑器预填内容显示在问题详情中。

## DeepSeek 停止和恢复证据

官方 Python SDK 暴露 `session/query`、`session/resume`、`session/wait` 和 `shutdown`，没有 SDK 的 `session/cancel`。ACP 有会话级取消，但 SDK 的原生问答、批次及计划审阅走 `user-question/ask`。采用 SDK 加每会话独占进程及独立 home，保留这些原生交互。问答回调和审批请求均在 SDK 读线程之外等待用户。

正常结束先按原生 query receipt 和对应活动判断，随后调用 `session/wait`，等待所属子 Agent 和汇总活动结束。显式停止时，原生 `shutdown` 确认服务已排空受管理的子 Agent，并释放原生 Agent 和工具作用域。SDK 回收该 runtime 后，适配器才用这条证据确认取消。如果 `shutdown` 未确认而 SDK 最终需要终止进程，单凭 PID 退出无法确认工具作用域已清理，运行返回 `unknown` 并保留隔离。已提交到独立外部服务的操作及主动脱离管理的进程，需要单独核实结果。恢复同一会话使用原生持久历史，工具外部状态由原生能力决定。

来源：[DeepSeek SDK 服务源码](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/sdk/server/src/server.ts) · [Python SDK](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/python/sdk/README.md) · [ACP 会话取消](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/acp/acp/src/session.ts) · [Pi RPC](https://github.com/earendil-works/pi/blob/0f57b314e10215cddc7a5d28edbbbac3993f5385/packages/coding-agent/docs/rpc.md)

## 复现与验收边界

```sh
python3 -m unittest -v agent_runner.tests.test_adapter_base agent_runner.tests.test_d_adapter_protocol

# 通过上述隔离安装准备真实程序后，运行原生集成测试。
# 将 CHATRAW_TEST_PI 替换为隔离安装的绝对路径。
CHATRAW_TEST_PI=/absolute/path/to/pi CHATRAW_TEST_DEEPSEEK=1 \
  python -m unittest -v agent_runner.tests.test_d_native_adapters
```

- 协议模拟验证 EOF、重试与最终文本替换，交互过期和迟到回复，手动压缩取消证据，未支持附件拒绝及 DeepSeek 失联后有无原生 shutdown 证据的分流。
- 本机原生集成环境为 macOS arm64、Python 3.12、Node 24.10.0。真实 Pi CLI 与 DeepSeek SDK/runtime 使用 loopback 模型替身，覆盖原生进程启动、批次问答、审批拒绝与一次授权、停止时拒收旧交互、跨会话隔离、恢复原生历史和缺失会话拒绝。两个程序都验证了正在运行的 shell 在停止后未写入延迟标记。图片验证到 Pi 的模型请求和 DeepSeek 的原生附件存储。压缩验证到 Pi transcript 的原生压缩记录和 DeepSeek 的空历史原生响应。另验证了 DeepSeek 原生计划审阅取消。
- DeepSeek SDK 0.2.2rc2 的关闭路径在 Python 3.12 和 3.14 的 unittest 下报告上游 stdout/stderr 文件对象的 `ResourceWarning`。原生进程退出、工具停止及原会话恢复通过。
- RM-01 和真实模型服务的身份认证、模型请求、图片与压缩质量、Linux 实际工具作用域及主机重启仍待总控现场验收。以本机原生协议证据和现场证据分别登记 G02、G05–G08。
