# 最终总结三臂结果：补充执行状态与审批事实未证明有效

2026-11-14。按总控分次授权完成3次有效生成，均为最终回答前seq54的同一原生历史；另外保留1次未生成的stream_options格式校验400。此后停止，没有进一步变体、工具执行或生产变更。

|条件|最终正文是否正确承认获准执行|finish_reason|输出tokens|耗时|返回工具调用|
|---|---|---|---|---|---|
|原成功tool内容`(no output)`|否，仍否认申请提权|stop|1157|59.995秒|0|
|只追加`[exit code: 0]`|无法评估：无最终正文|length|8192|294.404秒|0|
|在上一臂只追加`[approval: allowed-once]`|否，仍声称没有permission escalation|stop|809|41.967秒|0|

最后一行审批事实由原生审计`dbb3fc40-8fb9-40e0-b6ae-f8ff41f1fe90`确证，与成功callId `call_784e35af63404745b8e1ba9b`配对；不是让模型迎合结论的指令。最后一臂与上一臂逐字段比较，唯一差异就是该tool content新增此行。温度0、8192预算、18条消息、31个工具、thinking、历史顺序均不变。

最后一臂最终正文仍说“No retry with a different method, no permission escalation...”，并将获准命令的实际结果表述为沙箱错误。输出有最终正文但事实不正确，不能作为修复通过。第二臂的length失败也保留，不能用其reasoning代替最终答案。

本组说明，在这份固定最终历史中，仅补成功退出码或再补真实审批事实都未得到可验收的正确总结；不能据此外推所有历史/提示或模型的普遍行为，也尚未定位造成错误归纳的具体责任层。原G05真实审批与文件副作用证据不变，本问题仍是待解决的最终总结事实准确性。

109记录前两臂与格式校验失败；111记录第三臂字段不变量、哈希、usage、耗时和短片段。完整body、原始HTTP/响应实体和生成token IDs保存在`/tmp/chatraw-deepseek-summary-bqs7enr3/http-final-seq54-nonstream`受限目录，原失败ChatRaw聊天/run未被改写或重放。
