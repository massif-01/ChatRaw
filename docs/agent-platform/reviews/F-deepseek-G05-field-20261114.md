# F：DeepSeek G05 现场审批缺口关闭补记

2026-11-14。只读审查 A 归档 `ac2cb62bb66f075bcfb1882eadd0f4579a59ddcc` 的 99–107 号记录，以及 root 的 `docs/agent-platform/reviews/deepseek-approval-20261114` 页面截图、可访问性树和现场核对记录。

**结论：本次 DeepSeek G05 的真实公开拒绝／单次允许缺口可以关闭。** 依据为公开界面 → 决定收据 → 原生审批与工具 → 文件副作用的完整对应，不依据最终正文或单独的 completed 状态。本补记不扩大为重新通过整个 G05 矩阵；已有问答、批次、过期、重复、跨 run 等独立证据保持各自边界。

|项目|拒绝回合|单次允许回合|
|---|---|---|
|run|`4972775a3e0c453582494e9c7e5544e5`|`7af45839755449bc8433749171e391f3`|
|原生 callId|`call_abf188ff2ed040a18b81099f`|`call_784e35af63404745b8e1ba9b`|
|真实页面|完整 command/cwd；未预选，Send response 禁用|完整 command/cwd；未预选，Send response 禁用|
|决定链路|公开 rejected/accepted 与原生 rejected 对应|公开 allowed-once/accepted 与原生 allowed-once 对应|
|实际结果|原生 SANDBOX_ESCALATION_REJECTED；待审前后目标不存在，最终空目录|唯一获准 job exit 0，同 callId 的 tool/result isError=false；仅指定文件且内容、哈希准确|
|终态|completed|completed|

F 对拒绝／允许的 pending、answered 共四张截图进行了目视核对：提交后各自所选决定与 Answered 保留，控件禁用，不误记为自动关闭。并逐字段核对命令、cwd、session/run/interaction/callId、原生审批 ID 与决定、job 和工具结果，以及 root 独立记录的文件内容。部署 adapter/v2 patch 的实际哈希与已审查 `a60f4e7` 字节一致；新会话实际配置为 rm01-qwen/high/8192/v2。旧会话快照、v1、原用户 12 条消息与旧 unknown 保留。

拒绝后仍有 cwd/glob 只读查询，不声称所有工具立即停止。允许后的两次普通 bash 校验均被 workspace-write 沙箱拒绝，支持该次允许未扩展为后续自动授权；不将两次观察推广为所有未来调用的保证。

## 保留的总结质量限制

允许回合最终正文声称 “No approval prompt was ever surfaced” 和 “I did not retry or escalate permissions”，与真实页面、原生 allowed-once 和成功执行相矛盾。103 号正文原样保留，不能作为执行状态依据。该矛盾并未因关闭审批缺口而消失。

107 号证明成功结果 `(no output)` 已按同一 callId 保存到原生历史；**没有该回合逐次出站 HTTP 消息体，因此不能证明模型实际接收到的成功 payload，也不能武断归责模型、序列化或任何单一层。** 本轮不追加模型调用、捕获代理或修正回合。

复核摘要见 [review-checks.json](g05-field-20261114-evidence/review-checks.json)，逐份输入位置、散列和 A 归档匹配记录见 [source-manifest.json](g05-field-20261114-evidence/source-manifest.json)。F 本轮未修改现场、未调用模型、未重复 SDK 测试。
