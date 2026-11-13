# 最终组合部署与现场验收（当前记录）

2026-11-13。已部署root adeb279的Runner运行源码及menu-final-ui六个前端资产。只更新codex.py、codex_responses.py、deepseek.py；其余运行源码逐文件与root核对一致。ChatRaw镜像为chatraw-agent-integration:adeb279-final-ui，ID sha256:09bda4d9e7a59bbfc760160be861780baa4f9bdaf268576fe6624ccba8bc580f。

首页、agents.js、app.js/app.min.js、styles.css/styles.min.css六项实际HTTP SHA256均匹配交付包；Hermes已安装与市场图标仍匹配b5cafcd资产。/ready正常。新增宿主codex.responses_compat_upstream固定为http://10.10.99.98:58000/v1/responses，仅新绑定应用；全部原有binding/base_config逐项保持一致。用户原聊天12条消息和绑定未变。只在无真实活动任务时进行一次必要的ChatRaw/Runner维护操作，未改.98或重启整机。

## Codex：真实模型全链路通过

新聊天cbfa4dc9-3be6-4d11-afea-33867e0353cf，Runner session dc93d52367cb49f8a4909e297c214a3f，native thread01a1d581-d366-7db1-a194-a75060d24e47。

- 随机标记D-54B28E292E经原生compacted事件写入替换历史；同thread下一轮准确返回，未再出现模板400。
- 同聊天的工具回合经过公开单次审批，实际写入并读回自有目录文件，文件内容为A_CODEX_5deff5bc5bde。初始测试脚本用字面换行表示printf格式，模型公开命令采用等价反斜杠n；首次精确字符串检查未发批准，随后只读审查公开命令，确认唯一差异是printf换行拼写、路径/guard/令牌/操作完全相同后才批准。未通过SSH补齐审批信息。
- 同聊天PNG随机像素为182809，模型准确返回。原生input_image解码后的PNG SHA256与上传文件一致。没有创建另一个thread冒充续接。

原始步骤在73/74，原生compacted和图片/工具记录在73/76，76-codex-final-verification.json为交叉核验。

## DeepSeek：公开审批验收尚未形成

首次长命令回合fafcabb8c61c4e8780b592a7200f6d96收到两个bash空参数，缺description/command，随后MALFORMED_RESPONSE。没有公开审批、没有目标文件。

按有根据的简化，第二个专属managed测试会话使用短相对路径命令，并在提示中明确完整description/command/workdir。回合e36a20cbd531425db3ba895dc20ff678首次原生参数有效，但默认workspace-write沙箱不可用；模型下一次又返回空参数，最终MALFORMED_RESPONSE。仍没有公开审批，文件不存在。第二次使用明确的新测试会话，不声称旧会话恢复。

因此不能把这两轮算作“用户明确拒绝”或“仅一次允许”通过。没有依据SSH原生记录给缺失的公开审批补字段，没有批准任何DeepSeek操作，没有改模型、全局沙箱或增加DeepSeek协议修补。74/77与78/79分别保留两次公开与原生证据。

随后总控依据D核实的官方路径单独授权一次首调用显式升级验收：完整JSON含description、command、sandbox_permissions=danger-full-access、非空justification，短相对唯一文件，避免先触发默认沙箱。新专属聊天bb09da12-2161-4b51-b98c-3fe343171ba9的回合d784beb1261b490a83ea823fee0809a9只把tool_name/params JSON作为普通assistant文字返回，原生tool/call数量为0，公开审批为0，目标文件不存在。它虽然completed，也不是工具执行或拒绝通过。按授权边界停止，没有继续允许回合或普通重试。82/83保留公开与原生证据。

当前结论：新的审批适配器已部署，但在指定本地模型上的“先拒绝、再仅一次允许”实际接收验收未到达。三轮的不同失败事实完整保留；不能据这些模型输出判断审批UI已通过，也不能据此断言所有模型上的SDK审批均不可用。推理窗口已释放。

## 备份与保留边界

受限私密备份及隔离验证见66号报告：12个SQLite、6156个文件、25组绑定/工作目录核验；在线仅旧unknown聊天updated_at刷新，随后在必要维护窗口内取得两库逻辑稳定的只读副本。没有将两库顺序快照称为事务一致，也没有恢复到生产或启动恢复出来的任务。

旧Codex unknown e05b8525931c4d1585cae79770c7be3d继续隔离；当前无其它非终态。维护后的原用户数据与服务状态见80号记录，三轮DeepSeek验收结束后的最终复核见83号记录。旧Codex绑定没有被回填兼容字段，其原直连恢复限制不应由新会话通过结果覆盖。
