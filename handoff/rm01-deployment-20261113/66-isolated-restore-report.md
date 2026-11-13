# 现场私密备份与隔离副本核验

2026-11-13。数据库和凭据只保存在 .99 管理员私密目录，未下载到本机或提交仓库。原始数据未删除，生产没有切换到备份，恢复副本未启动应用或任何原生Agent，没有重放提示或整机重启。

## 在线快照与边界

私密目录：`/var/backups/chatraw/20261113T151205Z-isolated-265c378f`，root拥有、0700；数据库、配置与结果文件为0600。使用仓库已有script/agent_db_backup.py对SQLite执行backup，复制ChatRaw卷、Runner原生状态/工作目录/附件、宿主配置与服务/Compose控制文件中的普通文件。SQLite的WAL/SHM由backup处理，不把侧文件配到已生成的数据库副本；4个临时启动器symlink和2个活socket未恢复。

首次严格全表检查发现ChatRaw的chats表一条updated_at发生刷新，对应旧unknown测试聊天2ed4de0d-ef0f-4dbf-9f97-7ec9d0eaab8a。没有新增/删除聊天，消息、绑定、配置与所有Runner表不变，普通文件哈希不变。因而未把该在线窗口称为全状态稳定或跨库事务一致，也没有循环重做全量备份。

在已生成备份的私密restore目录内完成只读核验：12个SQLite均integrity_check=ok且与备份字节相同；6156个普通文件哈希相同；25组ChatRaw/Runner绑定、25个managed目录可对应。验证了代表性started标记及五Agent的原生状态文件存在。用户原Codex聊天12条消息及12条显示映射可对应，旧unknown保留。

一次验证脚本误将agent_messages映射表按chat_id查询，报列不存在；按真实schema改为通过message_id关联messages后，只重新检查已有隔离副本，没有重备份或改源库。65号结果是最终只读核验结果，不隐去最初边界和检查错误。

## 复用部署维护窗口的静止双库快照

为关闭上述更新时间刷新边界，复用了已授权合并部署的必要停机窗口：ChatRaw容器及Runner已经停止，没有真实用户活动任务，Hermes服务未额外停止。没有为此新增一次整机或服务重启轮次。

在 `/var/backups/chatraw/20261113T151205Z-isolated-265c378f/maintenance-primary-152247` 分别用已有SQLite backup工具生成ChatRaw/Runner副本，再复制到该目录的restored子目录，仅只读检查。两库在备份前、备份文件、隔离副本及备份后的逻辑内容摘要完全一致，integrity_check均ok，unknown状态保留。两个快照于北京时间2026-11-13 23:22:47顺序取得，具体UTC起止和摘要见70号结果；没有声称它们来自一个跨库事务。

相应原生状态/文件集合仍为上面的已验证私密快照；本轮之前没有新的模型任务。该证据证明限定集合能够还原并只读对应，不等同于启动全部原生程序后的功能恢复。整机重启、断电和手机实机验证继续暂缓。

## 证据

- 64：首次现场备份脚本及全状态变化诊断；这是一次性现场核验，不是新增产品备份框架。
- 65-isolated-restore-result.json：脱敏的关键集合与完整性结果；完整文件manifest保存在现场私密目录。
- 70-maintenance-backup-result.json：必要维护窗口内的双库静止观察与隔离验证。

后续真正恢复生产前，仍需保护当前数据、匹配软件版本和原生状态、核实任务与unknown，并另行安排维护窗口。这里没有替管理员执行生产恢复。
