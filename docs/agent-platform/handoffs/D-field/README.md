# RM-01 D 线现场补测

每次运行只选一个 Agent 和一个场景，独立创建 managed 聊天。首条消息以 `D验收` 开头，供 ChatRaw 标题和日志识别。结果保存在新建本地目录中，既有聊天及用户请求不进入测试。

```sh
# 只打印计划
python3 verify.py pi stop

# 收到推理窗口移交后，逐项串行执行
python3 verify.py pi stop --execute --output /absolute/evidence/pi-stop
python3 verify.py pi image --execute --output /absolute/evidence/pi-image
python3 verify.py pi compact --execute --output /absolute/evidence/pi-compact
```

默认 ChatRaw 入口为 `http://10.10.99.99:51111`。所有聊天、附件、提交、回复、停止与事件读取使用公开 API。提交异常时按原 client request ID 核对一次。存在未收敛的运行时，先核实该运行，再提交下一项。

## 判定

|场景|通过所需证据|
|---|---|
|工具停止|公开绑定确认本批 managed 目录。停止前经现有 SSH socket 只读看到该轮唯一 `started` 标记及匹配内容。公开 run 产生工具开始事件与一个确认停止的终态。在初次看到 `started` 之后至少再经过命令的完整 30 秒延时，并确认 `late` 仍不存在。|
|PNG|上传记录、PNG SHA-256、真实模型回复匹配只编码在像素中的随机六位数，并确认无工具调用。用 A 提取的原生输入或模型请求记录核对媒体类型与内容关联。|
|原生压缩|公开 compact 回合收敛，后续回合的同一 ChatRaw session 能复述早期随机识别码。还需在绑定的原生 session 查到本次操作对应的已提交压缩边界或摘要，复核压缩前后原生身份。空压缩、预览或模型自述成功不算。|

工具停止仅批准当前 run 的预期前台 shell 命令。公开审批须显示完整的精确命令，且只选择一次允许。命令中两个绝对路径均指向该 run 所属 managed 工作目录。预期命令之外的操作、只给理由而无完整命令的审批、以及要求扩展权限范围的其他请求会停止该次测试。SSH 只检查本次两个标记，先按公开绑定的 session ID 校验路径，再校验工作目录归属和标记类型。

原生取证由 A 或总控负责，按结果中的 chat/session/run ID 关联。Codex 查看该 thread 的已提交压缩记录，Claude 查看 `compact_boundary`，Pi 查看 transcript 的 `compaction`，DeepSeek 查看 `compaction/summary` 和关联的 `command/done`，Hermes 核对逻辑会话 ID、压缩 mutation 结果和真实摘要边界。Hermes 可产生原生物理分段，以同一逻辑会话的受控连续性为准。

## 2026-11-13 第一轮现场结果

使用 .99 的公开 ChatRaw API 和 .98 的 `RM-01 VLM`。本批新建 16 个独立验收聊天，所有提交串行。公开事件与结果位于 [evidence](evidence/)；各子目录的 `result.json` 保存聊天、session 与 run ID。脚本和证据由 D 交付，原生记录的只读核对交 A。

|Agent|PNG 挑战|工具中途停止|原生压缩与后续|
|---|---|---|---|
|Codex|答对像素随机码|看到了 `started`，超时观察无 `late`，但公开 run 保持 `unknown`|compact `completed`，同一会话下一轮 `codex_native_failed`|
|Claude|答对像素随机码|通过，终态 `cancelled`，观察期内无 `late`|compact `completed`，同一 ChatRaw session 答对早期码|
|Pi|答对像素随机码|通过，终态 `cancelled`，观察期内无 `late`|compact `completed`，同一 ChatRaw session 答对早期码|
|DeepSeek|公开回合完成，但模型收到仅文本占位，未答出数字|两轮均无工具启动事件或 `started`，未到达停止检查点|SDK 返回 `Compacted 8 history items (~686 tokens).`，同一 ChatRaw session 答对早期码|
|Hermes|答对像素随机码|通过，终态 `cancelled`，观察期内无 `late`|compact `completed`，同一 ChatRaw session 答对早期码|

- Codex 停止 run `e05b8525931c4d1585cae79770c7be3d` 有已接收的单次命令审批和原生工具开始事件。末条状态为 `unknown`，错误 `codex_tool_stop_unverified`，公开事件没有 `tool_completed`。只读复查同时记录了终态缺失与无 `late`，不能据文件结果给 Runner 的停止确认补写通过。
- Codex compact `b892d61229604a969fadde19a3d9bef4` 后，continuity run `cb7fea5232db43f093a71b0be18bef57` 失败。其余四个 Agent 有公开 API 连续性证据，原生压缩边界和原生身份仍需对应的原生记录。
- DeepSeek 失败的同一张 PNG 经一次 .98 Anthropic Messages 直连对照返回 `525877`，与像素随机码一致。A 已在原 native session 找到图片引用，同时确认 profile 无模型模态声明。宿主原生 patch 接线由 `1cdc681` 提供；本轮现场使用的是变更前配置。四个答对的 Agent 已证明端到端像素挑战通过，逐条原生请求核对仍待 A。
- DeepSeek 第二次停止加上 cwd 自校验，模型只输出将调用 bash 的文字。两次均无公开工具开始事件，无审批被允许。Codex、Claude、Pi、Hermes 的停止使用脚本较早的同一前台命令版本，两个绝对标记路径均经过 session 归属校验，后来增加了命令内的 cwd 断言。

## DeepSeek 工具执行中停止复验

在 .98 推理窗口移交后只提交一次。新建 ChatRaw managed 聊天 `779797c9-be32-4ac0-bdae-483106622be6`，run `292b915f502f4f0f8d81a069624049a8`。提示要求在当前目录通过原生 bash 执行精确命令，使用相对文件名并在写入前检查实际工作目录。模型补齐必填的工具描述后，默认沙箱返回 `SANDBOX_UNAVAILABLE`，模型在同一 run 内请求单次授权。公开审批只显示工具名，复验时只读核对了唯一未完成的原生调用、完整命令、前台模式和工作目录，再通过该 run 的公开审批 API 允许一次。这个现场结果只证明停止行为，公开审批完整性需部署修复后另验。

停止前确认 `started` 内容匹配，`late` 缺失，并观察到归属该运行的原生 runtime、bash 和 sleep 进程。公开 run 到达 `cancelled`，原生同一 callId 的工具结果为 `ABORTED`，同一 turn 以 `aborted/disposed` 结束。首次观察到启动后 32.14 秒再次核对，`late` 仍缺失，三个所属进程均已退出。[原生和公开证据](evidence/deepseek-stop-verified/result.json)
