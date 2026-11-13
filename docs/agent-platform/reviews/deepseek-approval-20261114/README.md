# DeepSeek 审批现场收尾

2026-11-14，RM-01 `10.10.99.99:51111` → 原生 DeepSeek Harness SDK/runtime `0.2.2rc2` → `.98` 的 `RM-01 VLM`。

**G05 的 DeepSeek 现场补项通过：真实页面拒绝阻止写入，单次允许后才发生写入。两回合自然到达 completed。** [F 独立现场复核](../F-deepseek-G05-field-20261114.md)同意关闭此项。允许回合最终正文存在与实际执行矛盾的总结，单列如下，不以模型自述证明审批或命令成功。

## 根因与修复

原始 SDK 请求和原始响应定位到审批之前：模型有时只输出文字形式的调用，固定请求也复现了错误参数语法并被解析为 `{}`。SDK 没有从这份原始响应中丢掉有效参数。Harness 的原生 `thinking` / `output_config` 未被该版本 vLLM 的 Messages 转换处理，实际落到了关闭思考的模板。保持请求、31 个工具、8192 预算和温度不变，仅启用 `chat_template_kwargs.enable_thinking=true` 后，Messages 和等价 Chat Completions 都返回了完整参数。该对照支持固定案例的接入配置归因，不能外推所有模型调用都可靠。

修复使用 Harness 自带 `llm-pi-ai` 注册独立 `rm01-qwen` 路由，原生配置传递 high/off；ChatRaw 只新增宿主 `provider` 透传及准确的健康检查说明。没有新建代理、修改共享模型服务、解释执行普通文本 JSON、修改 SDK 或审批/权限回调。新会话采用 v2 patch；旧快照及 v1 文件不变。来源：[A 的原始诊断](../../../../handoff/rm01-deployment-20261113/98-deepseek-thinking-causal-evidence.md)、[固定版本协议分析](../../handoffs/C-local-model-98/deepseek-messages-thinking.md)、[F 独立审查](../F-deepseek-provider-a60f4e7-20261114.md)。

## 真实页面与执行结果

总控使用 Playwright CLI 控制实际浏览器，打开 `.99:51111` 的两个独立验收聊天。没有模拟请求、修改页面状态或代替模型构造工具调用。A 提交任务并只读观察；两次审批决定都由总控点击实际单选项与 **Send response** 提交。

|回合|拒绝|单次允许|
|---|---|---|
|chatId|`7f614811-44d8-406a-8795-906588c48133`|`42cf0a44-0585-418a-b3fb-58fef9977726`|
|runId|`4972775a3e0c453582494e9c7e5544e5`|`7af45839755449bc8433749171e391f3`|
|interactionId|`e4edc52ce3ee4062acea599096ae14d1`|`5f12c76ce95743f2b83af4ddfd5c8d18`|
|页面操作|Deny → Send response|Allow once → Send response|
|账本|answered / accepted / rejected|answered / accepted / allowed-once|
|文件结果|工作目录仍空，目标不存在|仅目标文件存在，内容 `A_NATIVE_e253fd617ca8` 准确|
|原生结果|SANDBOX_ESCALATION_REJECTED|获准命令 exit code 0|
|最终状态|completed|completed|

审批前目标文件均不存在，页面显示完整命令、工作目录和单次 `danger-full-access` 说明，两选项均未预选，未选择时不能提交。点击后卡片保留只读 Answered，选项与提交按钮禁用；随后手动关闭弹窗。截图：[拒绝前](deny-pending.png)、[拒绝已回答](deny-answered.png)、[允许前](allow-pending.png)、[允许已回答](allow-answered.png)。对应无删节命令与目录见 [deny DOM](deny-pending.yml)、[allow DOM](allow-pending.yml)。

拒绝后有 cwd/glob 两次只读查询，但没有再次写入或再次申请审批。允许后另两次只读 Bash 校验仍被默认 workspace-write 沙箱拒绝，随后使用 read/glob；没有新增审批或自动授权，也没有额外写入。不能把这些记录写成“拒绝后所有工具立即停止”或“允许后整个会话无需审批”。

总控另行只读核对了两个运行、各自唯一决定、实际文件、线上适配器/v2 patch 散列及原 unknown 状态：[root-site-check.json](root-site-check.json)。现场字节与已审查源代码相同，Runner active；既有 unknown 仍隔离。A 的 [拒绝原生记录](../../../../handoff/rm01-deployment-20261113/100-deepseek-v2-deny-native.json)和[允许原生记录](../../../../handoff/rm01-deployment-20261113/103-deepseek-v2-allow-native.json)提供 callId / 原生决定 / 工具结果关联。

## 最终总结的质量限制

允许回合最终正文错误声称没有出现审批、没有请求更宽权限，与此前页面、原生批准记录和实际文件相矛盾；[原样截图](allow-completed.png)保留该输出。已核对获准 callId 与批准决定、job exit 0 和成功 tool/result 正确配对，原生历史保存成功结果 `(no output)`。但现有 request/context、header 和 projection 没有逐次模型 HTTP 消息体，不能独立证明成功回执的最终出站内容，也不能据此把该总结错误明确归责于某一层。

这不改变两条真实审批路径的验收结果，但不构成“模型对工具结果的总结始终可靠”的保证。没有追加纠正提示或重复成功测试来替换错误总结，未篡改正文、账本或终态。手机实机仍按用户要求暂缓；没有再次整机重启。
