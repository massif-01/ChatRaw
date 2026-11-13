# RM-01 整机重启验收

2026-11-14（Asia/Shanghai）。用户明确确认“现在重启并验收”后，执行一次正常整机重启。运行代码未更改。该验收覆盖空闲时重启后的自动启动、数据保持和五Agent实际会话续接，不包含运行中强制断电。

## 结果

- boot_id从7b402537-ac56-4957-b4ad-fc8632d148db变为24e4247d-cfe9-4001-a26a-35268e37bf8c，uptime归零。
- 从重启指令发出算起约57秒ChatRaw就绪、约59秒全部目标端口恢复；观察器自身计时分别为16.85/18.86秒（不等于指令发出后的时长）；Docker/Runner/Hermes、TTO两服务、NFS/SMB自动恢复，手动启动次数为0。
- 容器、镜像、卷、启动策略、配置、插件配置、全部宿主快照和工作目录文件保持。NFS导出、SMB有效配置及service unit文件不变。
- Codex、Claude、Pi、DeepSeek、Hermes五次原会话续接均返回既有随机标记，tool调用为0。总控另从前后绑定表逐项复核五个原生thread/session ID一致；Codex/Hermes本轮run引用正常更新，不将run ID误称为原生会话ID。
- 只增加这五次授权提交的run；原消息/映射保留，两库integrity_check为ok。旧Codex unknown继续隔离，其原生记录没有重放。
- 总控独立HTTP验证：原用户聊天12条消息整体SHA256不变，六个线上前端资源匹配交付版本。见[root-before.json](root-before.json)、[root-after.json](root-after.json)。

## 原始证据

[A前后自动恢复比对](../../../../handoff/rm01-deployment-20261113/87-auto-recovery-verification.json)、[端口观察](../../../../handoff/rm01-deployment-20261113/86-reboot-network-observations.json)、[五续接及最终比对](../../../../handoff/rm01-deployment-20261113/90-reboot-acceptance.json)。

A发出唯一实际重启命令；协调交错时总控的SSH门槛命令在连接前得到Host is down，未在远端执行，未造成第二次重启。密码认证仅交互使用，未写入本报告或现场脚本。重连后没有手动补启动掩盖自动恢复结果。

G07更新为本次正常重启范围通过。DeepSeek当前模型的完整公开审批现场验证G05没有在本轮重试，仍为NOT_VERIFIED；G10手机实机按用户要求暂缓。
