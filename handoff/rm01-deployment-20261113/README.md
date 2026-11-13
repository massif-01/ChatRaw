# RM-01 .99 部署与真实模型验收

2026-11-13，A 线独占现场变更。入口：<http://10.10.99.99:51111>。本轮没有推送 Git、整机重启或修改 .98。

A 的基础现场验收中，安装与配置、真实工具执行、Runner 重启后原会话恢复、生成中停止均为 5/5。DeepSeek 的输出预算阻塞已由 D 线修复，原失败聊天与原 native session 均保留，8192 预算已在真实原生记录中确认。首次失败证据保留于 [根因记录](DEEPSEEK-BLOCKER.md)。普通聊天 default-chat 也已接通真实本地模型。

| Agent | 安装版本 | 真实工具回合 | Runner 重启后原会话 | 输出中停止 |
|---|---|---|---|---|
| Codex | CLI 0.153.4 | completed，审批后执行 pwd | completed，原 thread ID | cancelled |
| Claude | SDK 0.2.180 / CLI 2.1.321 | completed，Bash pwd | completed，原 session ID | cancelled |
| Pi | 1.5.2 | completed，审批后 bash pwd | completed，原 session ID | cancelled |
| Hermes | 6a0d2d12815c0546b0bcaf05046e2fe3293f60aa | completed，terminal pwd | completed，原 session ID | cancelled |
| DeepSeek | SDK/runtime 0.2.2rc2 | 修复后 completed，审批后 bash pwd | completed，原 session ID | cancelled，原生进程退出 |

所有成功工具回合都有 tool_started/tool_completed 事件，返回对应托管工作目录和 RM99_NATIVE_OK。Codex/Claude/Pi/Hermes 停止测试在真实 text_delta 到达后发取消；DeepSeek 是整条消息交付，在运行态及对应原生进程到 .98 的连接持续接收数据时发取消，验证该进程退出。五项均收敛到 cancelled，未以断开网页冒充停止。这里未验工具子进程在中途停止、原生压缩、图片或整机断电恢复。

ChatRaw 在 Pi 等待审批期间重启，run ID、session ID、待批 interaction ID 和 last_seq 均保持不变；重启后经原审批接口允许 pwd，随后完成。Runner 在全部任务终态后重启；五种 Agent 均在各自 Runner 重启验收后，于原聊天准确回忆上轮标记和工作目录，原生身份保持不变。最终 Runner SQLite integrity_check=ok，非终态 run 数为零。Hermes Gateway 未随 Runner 重启。

## 现场拓扑与持久目录

- Docker Engine 29.9.3、Compose 5.7.1 为现场已有安装，复用；docker/containerd 保持 active。
- ChatRaw 容器 `chatraw`，Compose 项目 `chatraw`，host network，端口 51111；volume `chatraw_chatraw_data` 挂载 `/app/data`，restart=unless-stopped。
- Runner systemd `chatraw-runner`，用户 rm01，监听 127.0.0.1:51112，代码 `/opt/chatraw-runner/agent_runner`，venv `/opt/chatraw-runner/venv`，配置 `/etc/chatraw-runner`，状态 `/var/lib/chatraw-runner`。服务已 enable。
- 独立 Hermes systemd `chatraw-hermes`，同用户，原生 `gateway run`，代码 `/opt/chatraw-agents/hermes/source`，home `/var/lib/chatraw-runner/hermes-home`。服务已 enable。
- Codex/Pi 安装于 `/opt/chatraw-agents/{codex,pi}`；Codex/Claude/Pi 原生 home 和 Pi/DeepSeek 会话根目录均在 `/var/lib/chatraw-runner`。
- Runner token 只保存在宿主文件并只读挂载容器；证据和控制脚本不含其值。token 模式0600，状态目录0700。
- 系统 Python 3.12.3 保留；因系统缺 ensurepip，项目内 uv 创建 Runner venv。Hermes 锁文件要求 >=3.14，使用项目内 CPython 3.14.10。未升级系统 Python。
- TTO 59090/59009 的 PID 31977/1956 与部署前一致；2049/445/139 共享端口仍监听。

## 模型接线

唯一实际模型 `RM-01 VLM`，服务根 `http://10.10.99.98:58000`，无鉴权。占位 key 仅满足 SDK 格式检查。Codex Responses、Pi/Hermes Chat Completions、Claude/DeepSeek Messages 均直接接本地服务，没有新增协议代理。Claude base 不带 /v1，其他带 /v1。服务级 NO_PROXY/no_proxy 覆盖本地及 .98/.99。精确配置见 `04-configure.sh`；另补充了 Claude 默认三档模型均为 RM-01 VLM。

Codex 的首次 sandbox pwd 被宿主 AppArmor unprivileged_userns 的 net_admin/setpcap 限制拒绝，原生记录为 `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`。允许单次原生审批后 pwd 成功。DeepSeek 默认 workspace-write 也返回 SANDBOX_UNAVAILABLE，本次仅对已核实的 pwd 批准单次原生升级。没有关闭 AppArmor、修改全局 sysctl 或将默认执行改成无沙箱；这些仍是现有宿主上的使用边界。

## 版本与证据

基础验收时 ChatRaw 使用 `e91d32f3674389be2c94c3a939c6a4179246e4c2` 交付镜像；随后已部署仅覆盖两个前端文件的 `2ba163e-ui` 派生镜像，详见 [UI 更新记录](38-ui-deployment.md)。Runner 以该版本为基线，仅 `agent_runner/adapters/deepseek.py` 更新为 D 提交 `bec078ba0d8db6b330c5721ff22a71142e4ea9fb` 的文件；其 SHA256 为 `96e02e6e9ed421297fd5e90d32868831a625892e8874f923ca93932217905108`。更新前确认无活动任务，保留配置和数据库，未重建或更换主容器镜像。源码包和镜像包位于宿主 `/home/rm01/chatraw/deployment-e91d32f`，四项交付文件 SHA256 校验通过。

- 源码包 SHA256：9f86e7d2c8920d36577778171d723d38fe8e9bf46a9480f27b9ff0d36a412d2c。
- 镜像包 SHA256：7a15b08f4baa40339e6dbdd98215bdb1e5f6f791980a8e748c7add1427bc6450。
- 镜像 tag：chatraw-agent-integration:e91d32f-amd64。
- 归档 config digest：sha256:faeb75dc86eb10583fa0af6a800e3c630247e2a193d7c7f2cd232d48162a45a9。
- Docker29/containerd 导入后 OCI manifest/image ID：sha256:2baa5f343ed1e2069caa04de4aafb9b499548f388b41702aa41cc06323e0e724。
- 两个 ID 表示不同对象；已校验归档 config 哈希、镜像 Config 和全部12层 diff ID 完全一致，见 `18-image-content-proof.json`。

[机器可读汇总](summary.json) 给出各 chat/run ID。`07-*.json` 为首轮快照，`08-*-events.ndjson` 为实际事件，`10-chatraw-active-restart.json` 为重启两侧状态，`13/17` 为原生身份对比，`14-*` 为恢复结果，`16-*` 为停止请求和结果，`15-deepseek-native-failure.ndjson` 为筛选后的原生错误证据，`19-storage-state.json` 为空闲状态、持久目录权限与数据库完整性。

安装脚本/日志按实际执行历史保留，包含初次镜像ID比较退出、ensurepip缺失、Hermes Python版本约束等诊断。这些文件不是幂等的一键安装器，不应盲目重放。

归档日志仅规范化行尾空白与末尾空行；事件、错误和状态内容保持原样。

## DeepSeek 修复后的现场闭环

`20/21` 记录单文件版本、校验和部署。通过原有插件 settings API 设置 model=RM-01 VLM、max_tokens=8192。`22/23` 为原失败聊天的新工具回合及事件；`24` 保留同一原生记录内 256000 → 8192 的 request/header，以及真实 bash pwd 的调用和 exit code 0 结果。原失败 run 保留为 failed，没有重写历史。

原聊天 `7660ee73-a125-49ed-9680-c9ab1b153b29`、Runner session `14d1c7a3dbda4f3fad1a20a4b35d523f`、native session `session-2c63be8b22744b3cb0c81413a51f6aad` 均未更换。`25` 与 `14-deepseek-resume.json` 记录再次重启 Runner 后恢复；`16-deepseek-cancel.json` 与事件记录验证 generation 中 cancel、原生 PID 58389 退出和最终 cancelled。

停止测量最初尝试等待新 request/header，但运行中记录未及时提供该事件，脚本超时退出。随后针对同一个仍在运行的 run 观察原生进程连接和接收字节，再发取消；没有新建或重发该生成任务。该测量过程完整保留于 `27/28`，不能把它描述成收到了逐 token 文本。DeepSeek 未提交部分生成文本，cancel 后 final_text 为空，符合其整条消息交付模式。

## 普通聊天配置与验证

`default-chat` ID 保持不变，名称/model_id 为 RM-01 VLM；api_url 为 `http://10.10.99.98:58000/v1`，后端实际请求 `/v1/chat/completions`，API key 为空。context_length=262144、max_output=8192。未改已有 capability 开关；embedding/rerank 两项原样保持未配置。

`29-ordinary-chat.json` 与事件记录确认独立普通聊天返回 RM99_NORMAL_OK，首内容约0.413秒，总耗时约0.780秒，数据库中用户与助手消息各一条，agent_id/session_id 均为空。`30-final-state.json` 确认最终非终态 run 为零、Runner 数据库 integrity_check=ok、四项项目相关服务 active、镜像ID未变，TTO与共享端口仍监听。

后续 DeepSeek PNG 模态调查见 [31号报告](31-deepseek-image-investigation.md) 与 [32号宿主 patch 交接](32-deepseek-native-patch-handoff.md)。D 的 Codex 工具执行中停止验收另留下 unknown，UI部署保留该状态；基础生成停止通过不代表工具执行中停止已通过。

后续已部署99616b9的DeepSeek宿主patch支持，新会话真实PNG挑战通过；四种Agent原生压缩已只读核实。最新版本、原unknown恢复状态及残余限制见 [49号报告](49-deepseek-patches-and-compact-verification.md)。此前各阶段记录和失败证据保留。

Hermes图标已按B单文件资产同时更新镜像市场源和持久安装副本，当前主镜像为b5cafcd-icon；原生服务与会话不变，详见 [56号上线记录](56-hermes-icon-rollout.md)。

Codex e889688前台工具停止修复已部署，新会话单轮现场验收通过，完整延时后无late；旧unknown保持隔离。见 [63号报告](63-codex-foreground-stop.md)。

最终组合已部署adeb279 Runner及六项菜单资产，Codex新会话压缩/续接/工具/图片通过；隔离恢复已核验，DeepSeek公开审批回合状态单列。见 [66号备份报告](66-isolated-restore-report.md) 与 [81号组合报告](81-final-combined-field-report.md)。
