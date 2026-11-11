# Hermes canonical Gateway adapter

原HTTP Runs API没有本次所需的逐会话cwd合同，不能把ChatRaw保存的目录标签当作原生cwd。
本适配器采用官方`hermes-gateway-v1`，连接已存在的同账户Gateway；不并行启动第二个home写入者。

## 精确映射

|统一操作|原生操作及核对|
|---|---|
|probe|`hermes gateway attach --json`获取一次性ticket，WebSocket握手后`runtime.describe`；核对tui source与cwd/request_id字段。`model.options(include_unconfigured=false)`仅回传已配置provider的模型ID。模型请求未检查。|
|create|`session.create({request_id,source:"tui",cwd,model?,provider?,reasoning?})`；返回session_id及info.cwd必须匹配。|
|resume|`session.resume({session_id})`，核对profile、session与cwd；不新建替代会话。空闲时通过revision/generation限定的`session.mutate`应用新model/reasoning，原生要求额外确认时明确拒绝新run。|
|run|`prompt.submit({session_id,input_id,text,attachments?})`；只有非空附件才发送attachments。无ChatRaw历史/system/RAG/Skill。先保存run检查点，再保存原生admission_id。|
|events|只处理本session、匹配admission_id的原生事件；工具元数据不携带原始参数或结果，审批采用原生脱敏投影。|
|settlement|`prompt.receipt(include_result=true)`的terminal/outcome为依据；message.complete仅修正最终文本，EOF不算完成。|
|approval|保留原生choices，公开ID映射回原choice；`approval.respond`携prompt_id及execution_generation。|
|question|canonical clarify单选/多选/自由输入；`clarify.respond`回传原生标签和文本，取消为空answer。多个原生请求由公共Runner并存管理。|
|cancel|`prompt.cancel({session_id,admission_id})`，随后等待receipt确认结束；不调用process.stop。|
|compact|`session.mutate(operation:"compress")`带request_id/revision/generation；停止使用`session.interrupt`。未确认mutation结果时unknown。|
|recovery|重接原session，查询已保存admission的receipt；只恢复该执行generation仍在等待的交互，不重发原prompt。压缩或丢失admission检查点的情况保持unknown。|
|slash|交给原生command.dispatch；exec/plugin取原生输出，send/skill使用原生生成的输入；需要原生交互界面的其他directive明确报不支持。|

不提供secret/sudo/桌面操作回调UI；未支持的原生请求明确返回method-not-found，不自动答复或批准。
图片先用`image.attach_bytes`进入原生profile图片缓存，再将返回的path/mime用于prompt.submit；
不能直接提交Runner上传路径。单张最多5MiB、每轮最多4张，通用文件明确不支持。
所选模型的图片能力仍须实际验证。原生服务与Runner须位于同一主机。

## 迁移

旧baseUrl/apiMode/API key并不是Gateway原生身份，不能无声转换。ChatRaw保留资料，但新配置
只接受model/provider/reasoning三个可编辑字段；宿主executable/home只能由管理员配置。
旧聊天文本保留，不能用把旧历史重新提交给Agent的方法伪装原生session恢复。

## 验证证据与来源

`test_hermes_adapter.py` 使用真实loopback WebSocket和协议fixture；验证cwd确实进入原生
session.create、prompt没有附加上下文、generation审批、原生多选、停止、EOF/恢复、slash和压缩。
fixture对空attachments数组和未暂存的图片路径明确拒绝：约束来自D线真实Gateway验证及附件准入源码。
本机A环境未安装Hermes，实际Gateway验证由D/总控独立记录；不能把fixture算作真实模型通过。

源码核对日期2026-11-12：

- [官方接入协议与attach启动](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/programmatic-integration.md)
- [Gateway local sessions/cwd/admission](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/gateway-local-sessions.md)
- [canonical字段与方法](https://github.com/NousResearch/hermes-agent/blob/main/apps/shared/src/gateway-contract.generated.ts)
- [事件执行身份](https://github.com/NousResearch/hermes-agent/blob/main/gateway/session_events.py)
- [审批与clarify](https://github.com/NousResearch/hermes-agent/blob/main/gateway/session_pending_controls.py)
- [原生压缩](https://github.com/NousResearch/hermes-agent/blob/main/gateway/session_mutation_compress.py)
- [原生模型设置](https://github.com/NousResearch/hermes-agent/blob/main/gateway/session_mutation_model.py)
