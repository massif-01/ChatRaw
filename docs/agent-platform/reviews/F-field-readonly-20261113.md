# F：RM-01 现场独立只读核验

**结论：本轮未发现新增 P0/P1。Docker 主程序／宿主 Runner 边界、有效账户、loopback、凭据文件权限、持久目录和已完成记录符合当前交付约定。DeepSeek 已知输出预算缺口已部署修复，现场请求头、工具完成和同会话恢复证据已核对。**

本轮按用户选择的真实本地模型 `.98` 验收。现场动作全部由 A 执行；F 只读核对，不把证据审查描述为 F 亲自执行重启或推理。整机重启、手机实机等剩余边界维持，不能据此宣布全项目交付完成。

## 核验方式与时间

- 现场入口：[ChatRaw](http://10.10.99.99:51111)。只读 HEAD 返回 200；未带 token 的宿主 Runner `/v1/health` 返回 401。
- SSH 使用已授权控制连接，以 `rm01` 登录；必要时 sudo 只读 inspect/stat/进程及数据库资料。
- 两次结构化快照：**2026-11-13 21:39:56、21:46:25（Asia/Shanghai）**。A 在两次之间完成宿主 DeepSeek 更新和复验，故 Runner PID 变化是已授权现场动作，不是异常。
- SQLite 均以 `mode=ro` 打开并启用 `query_only`，只选身份、状态、时间、计数等非秘密字段。没有读取 token 内容，没有输出完整环境、模型凭据或原生请求正文。
- 没有安装、配置变更、重启、聊天写入或模型请求。DeepSeek 增量的本地检查仅调用参数验证和 SDK 构造器，未启动原生 runtime。

原始筛选证据：[首次快照](field-20261113-evidence/readonly-snapshot.json)、[修复后快照](field-20261113-evidence/readonly-after-budget.json)、[采集脚本](field-20261113-evidence/collect_rm01_readonly.py.txt)。

## 部署与持久化事实

|项目|独立只读观察|
|---|---|
|ChatRaw 主程序|Docker 容器 `chatraw`，host network，`0.0.0.0:51111`；restart=unless-stopped，privileged=false。容器进程表仅见 Python Web 进程。|
|镜像|`chatraw-agent-integration:e91d32f-amd64`，image ID `sha256:2baa5f343ed1e2069caa04de4aafb9b499548f388b41702aa41cc06323e0e724`，前后快照一致。A 的归档 config/layer 校验也与其一致。|
|Runner|宿主 `chatraw-runner.service` active/enabled，cgroup `/system.slice/chatraw-runner.service`，实际 UID/GID 均为1000（rm01），工作目录 `/opt/chatraw-runner`，仅监听 `127.0.0.1:51112`。|
|Hermes Gateway|独立宿主 `chatraw-hermes.service` active/enabled，实际 UID/GID1000，独立 cgroup，`127.0.0.1:46761`。PID34685 在两次快照保持不变，未随 Runner 更新重启。|
|token|`/etc/chatraw-runner/token` 为0600、UID/GID1000，非符号链接；挂载到容器 `/run/secrets/chatraw-runner-token` 且 RW=false。|
|配置目录|`/etc/chatraw-runner` 为0750、root:rm01；environment/config.json 为0640、rm01:rm01。仅核对许可字段及文件元数据。|
|ChatRaw 数据|命名卷 `chatraw_chatraw_data` → `/app/data`；源目录 `/var/lib/docker/volumes/chatraw_chatraw_data/_data`。实际数据库 integrity_check=ok。|
|Runner 数据|`/var/lib/chatraw-runner` 为0700；runner.db 为0600、UID/GID1000；所有已登记 workspace 为0700、UID/GID1000。数据库 schema2，integrity_check=ok。|
|原生状态目录|Codex/Claude/Pi 的 home 覆盖分别位于 `/var/lib/chatraw-runner/{codex-home,claude-home,pi-home}`；Pi sessions、DeepSeek 独立 home、Hermes home 和 managed workspaces 都在宿主持久目录。服务实际 HOME 为 `/home/rm01`，没有借用其他运行账户。|
|既有服务|TTO `59090/PID31977` 与 `59009/PID1956` 和 A 部署前记录一致；2049、445、139 共享端口仍监听；docker/containerd active。这里只证明进程/监听持续存在，不冒充额外业务功能测试。|

Docker Engine 当前29.9.3；宿主 Linux6.8.0-147-generic x86_64。Runner Python3.12.3，Hermes 使用项目内 Python3.14.10。

## Agent 版本与执行记录

F 读取实际 PATH 解析目标/package metadata、Runner venv distribution metadata及 Hermes 源码提交：Codex0.153.4，Pi1.5.2，Claude SDK0.2.180，DeepSeek SDK/runtime0.2.2rc2，Hermes `6a0d2d12815c0546b0bcaf05046e2fe3293f60aa`。Claude 内置 CLI2.1.321 为 A 已记录的原生握手版本，本轮没有额外启动 CLI 探测。

第一次快照的 Runtime、Store、五 adapter 内容均与 `e91d32f` 相符：[源码比较](field-20261113-evidence/source-comparison.json)。第二次仅 DeepSeek adapter 改变，其 SHA256 精确匹配 D 的 `bec078b`；主镜像保持原样。

|Agent|A 执行／F 核对的真实本地模型证据|停止边界|
|---|---|---|
|Codex|工具回合 completed，tool_started/tool_completed 均存在；Runner 重启后同 thread 恢复 completed|A 首段 text_delta 后取消，现场记录 cancelled|
|Claude|工具回合 completed；Runner 重启后同 session 恢复 completed|A 首段 text_delta 后取消，现场记录 cancelled|
|Pi|工具回合 completed；ChatRaw 在待审批期间重启后原交互继续；Runner 重启后同 session 恢复 completed|A 首段 text_delta 后取消，现场记录 cancelled|
|Hermes|工具回合 completed；Runner 重启后同 session 恢复 completed，Gateway进程不变|A 首段 text_delta 后取消，现场记录 cancelled|
|DeepSeek|修复后工具回合 completed；同一原生 session、同 cwd，Runner 再重启后续接 completed|A 记录 running＋到.98:58000的出站连接，process_stop 后独占 runtime 退出并 cancelled；first_content_observed=false|

四种原有成功 Agent 的首轮 tool run、resume run、cancel run 与现场 ledger 一一对上；每个首轮均有一份 user/assistant 显示投影。Pi 的 ChatRaw 重启前后 run_id、session_id、interaction_id、last_seq 保持不变。Runner 重启记录中原生 session 身份与 cwd 均保持不变；后续 turn/run/admission ID 正常变化，不误判为换会话。[交接交叉核对](field-20261113-evidence/handoff-crosscheck.json)

第二次快照共19个 run，全部终态、每个恰一条 done；DeepSeek 首次预算失败仍保留为 failed，没有改写成成功。两个数据库均完整，未发现重复角色投影。此为该时点观察，A/E 后续获授权新任务不受此快照限制。

## DeepSeek 增量定向审查与现场证据

D 提交 `bec078ba0d8db6b330c5721ff22a71142e4ea9fb`、`77a123d788288ff89f96eb87fd5685b20822c833`：

- `max_tokens` 是可选正整数 public setting；schema 与 validate_config 拒绝 bool、0、负数、float、字符串和超出 JS 安全整数的值。
- 仅显式提供时向 HarnessConfig 透传；省略时仍为原生默认，不硬编码模型名或8192。
- F 参数单测通过；实际 SDK 构造器检查得到 omitted→None、provided8192→8192，均未 start。D 的模型替身测试源码还核对同 session 默认256000→8192和历史保留，本轮未另发模型调用重跑。
- F 直接只读解析 `.99` 原生压缩记录：同一个 `session-2c63be8b22744b3cb0c81413a51f6aad`，request/header 的预算依次为 **256000、256000、8192、8192**；模型均为 `RM-01 VLM`。修复后原生 bash 存在成功 tool/result，turn/end=completed，后续续接亦 completed。
- 修复后工具 run `b5471970bbb24e639605d3c963d09907`、续接 run `e7904316aa7d49879368966daa641ca0`、停止 run `2ccbcb8956b841e2a6af805f0790e977` 在现场 ledger 分别为 completed/completed/cancelled。停止证据记录独占 runtime 已退出，耗时1.26秒。

证据：[原生记录筛选](field-20261113-evidence/deepseek-native-readonly.json)、[原生header预算](field-20261113-evidence/deepseek-header-budgets.json)、[停止交叉核对](field-20261113-evidence/deepseek-cancel-crosscheck.json)、[参数验证](field-20261113-evidence/budget-validation.log)。本项是已知缺口的闭环，不重复计新问题。

## 仍保留的验收边界

本轮验证的是已获授权的 `.99` Docker/Agent 与 `.98` 真实本地模型路线。现场重启证据分别是：ChatRaw 待审批重启、Runner 在任务收敛后的重启与原会话续接；不等于活动 Runner 被强杀或整机断电。SDK 的 process_stop 证据也不能改写成首段输出后的流式停止。

整机重启、手机真实软键盘/设备、现场工具子进程中途停止、原生压缩及图片完整流程仍不能由这批记录替代。E 已报告真实109界面/资源通过，本轮未重复操作页面或占用推理窗口。可以继续剩余验收，不增加新的商业账号或多租户门槛。

A 原始证据目录：`/Users/massif/.codex/worktrees/04ec/ChatRaw/handoff/rm01-deployment-20261113/`；模型接线说明：`/Users/massif/ChatRaw/docs/agent-platform/handoffs/C-local-model-98/README.md`。

归档说明：采集器源代码按 `.py.txt` 文本保存，哈希与当次脚本一致；该脚本本轮未重新执行，报告时间点不代表当前实时状态。
