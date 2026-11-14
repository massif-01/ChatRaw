# A线最终交接

本轮所有部署、模型验收和备份核验的完整记录已提交9d40bfe；本文件只补最终归类，不增加现场操作。模型窗口已释放，之后未再推理、修改提示、尝试允许回合或操作服务。部署README最终兼容/浏览器描述归root维护，A未再修改。

## 原三项：通过

|项目|证据与边界|
|---|---|
|Codex原生compact与续接|76号核验：兼容配置的新绑定在同一native thread完成原生compacted、随机码续接、工具写读及PNG。旧用户绑定未回填。|
|Codex前台工具停止|62/63号：run26c25ba7d3604bd1baa6b6c2f0bda1d7，单一cancelled；完整32.08458秒观察后无late，原生中断及进程检查对应。旧unknown不作追溯清账。|
|DeepSeek前台工具停止|D提交e362252已由root集成为975ed11；run292b915f502f4f0f8d81a069624049a8。原生同callId结果ABORTED、turn aborted/disposed，32.14秒后无late，所属runtime/bash/sleep退出。该记录只证明工具停止，不证明当时公开审批完整。|

D记录位于root的 `docs/agent-platform/handoffs/D-field/evidence/deepseek-stop-verified/result.json`，本次只读核对其passed结果；文件SHA记录于summary.json，未重跑。

## 新增DeepSeek完整公开审批：NOT_VERIFIED

代码与原生SDK验证已通过独立审查并获root放行，已部署。指定.98模型下的真实公开审批未到达，归类为provider工具调用行为限制；不能声称用户明确拒绝或仅一次允许通过。

三次不同原因的现场结果均保留：

1. 首次长命令产生两个空bash参数，随后MALFORMED_RESPONSE。
2. 有根据地缩短命令并提供完整参数后，首调用有效但默认沙箱不可用；后续模型参数再次为空并MALFORMED_RESPONSE。
3. 获单独授权后使用官方首调用升级路径，完整JSON含sandbox_permissions和justification；模型将它作为普通文本返回，原生tool/call及公开approval均为0。

三轮均未创建目标文件。没有通过SSH补齐缺失公开审批后放行，没有伪造原生结果、改模型、改全局权限或增加DeepSeek协议修补。第三轮之后停止，不尝试允许回合。

## 软件缺陷与服务重启门槛

本轮未发现新的产品软件缺陷。上述DeepSeek实际限制发生在完整公开审批产生之前，不是“审批已被用户拒绝”的证据；它也不能作为所有模型上审批软件都无缺陷的证明。历史验证脚本的printf拼写比较、SQLite映射表列名检查问题已在证据中记录，未因此改产品逻辑或覆盖失败记录。

最后合并部署的必要服务重启前，真实排队、执行、待审批/待输入任务为0；唯一非终态是保留的旧Codex unknown。不是“全局所有任务都已终态”。69号快照与71号门槛脚本对应，维护窗口双库副本前后逻辑摘要一致、隔离integrity检查通过。原unknown始终保留。

原用户聊天12条消息的完整哈希、绑定与所有旧宿主快照均保持一致。最终采样仅原unknown，/ready正常，原生服务运行；源码全部匹配adeb279，镜像sha256:09bda4d9e7a59bbfc760160be861780baa4f9bdaf268576fe6624ccba8bc580f，六项前端及Hermes图标HTTP哈希匹配。见72、80、83号记录。

数据库、凭据与原生完整副本只保留在.99私密目录，仓库只有脱敏manifest和验证结果。静止双库观察不被称为跨库事务。没有生产恢复、恢复后任务启动、整机重启或手机实机验收。
