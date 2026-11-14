# 最终总结前的单字段对照

2026-11-14。仅进行两次有效HTTP生成，没有执行响应工具，没有改写或重放原ChatRaw聊天/run，没有修改生产配置或.98。本组不能证明修复已成立。

## 输入与边界

使用D通过真实SDK、原native日志截断到seq54重建的最终回答前body。两臂保留18条消息、31个工具、完整调用/结果、历史reasoning与原有“The approved run completed”正文。温度均0、预算8192、thinking开启。

两臂唯一文本差异是成功`call_784e35af63404745b8e1ba9b`对应`messages[8].content`由`(no output)`变为`(no output)\n[exit code: 0]`。没有新增用户询问、审批或completed文案。

共同设stream=false、return_token_ids=true。首次baseline因残留stream_options在校验阶段收到400，没有生成；保留其原始响应，经总控放行后两臂共同删除stream_options，再各完成一次有效生成。总计3次HTTP请求，其中1次格式校验失败、2次真实生成。

## 实际结果

|观测|baseline|仅追加exit code: 0|
|---|---|---|
|HTTP|200|200|
|输入tokens|14454|14462|
|输出tokens|1157|8192|
|耗时|59.995秒|294.404秒|
|finish_reason|stop|length|
|返回工具调用|0|0|
|最终正文|1564字符|空|
|是否正确承认获准执行|否|无法评估：没有最终正文|

baseline明确再次声称没有重试、没有请求danger-full-access审批，把实际结果描述为沙箱拒绝；错误总结已复现。第二臂生成了reasoning但耗尽输出预算，未产生最终正文，不能判为修复成功，也不能把reasoning中的局部表述当最终答案。

## 结论与证据

仅在这份固定历史中，exit0补充没有带来可验收的正确最终总结。不能外推该字段普遍无效或该模型普遍不可靠；也不将原生序列化正确等同于所有执行语义都已充分表达。本轮不继续追加采样。

109号JSON保存源body/实际请求/原始响应哈希、精确共同控制项、唯一差异、usage、终止原因与耗时。原始body、HTTP响应及完整生成内容留在0700私密目录`/tmp/chatraw-deepseek-summary-bqs7enr3/http-final-seq54-nonstream`，文件0600；首次400在同级`http-final-seq54`中。108号记录原native副本的源文件复制前后哈希。
