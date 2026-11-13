# RM-01 .99 部署与真实模型验收

2026-11-13，A 线独占现场变更。入口：<http://10.10.99.99:51111>。本轮没有推送 Git、整机重启或修改 .98。

当前安装与配置 5/5；真实工具、Runner 重启后原会话恢复、首段输出后停止各 4/5。DeepSeek 被原生默认输出预算阻塞，见 [根因与 D 线修复要求](DEEPSEEK-BLOCKER.md)。不能据五项 health ready 宣称五项模型执行都通过。

| Agent | 安装版本 | 真实工具回合 | Runner 重启后原会话 | 输出中停止 |
|---|---|---|---|---|
| Codex | CLI 0.153.4 | completed，审批后执行 pwd | completed，原 thread ID | cancelled |
| Claude | SDK 0.2.180 / CLI 2.1.321 | completed，Bash pwd | completed，原 session ID | cancelled |
| Pi | 1.5.2 | completed，审批后 bash pwd | completed，原 session ID | cancelled |
| Hermes | 6a0d2d12815c0546b0bcaf05046e2fe3293f60aa | completed，terminal pwd | completed，原 session ID | cancelled |
| DeepSeek | SDK/runtime 0.2.2rc2 | failed，上下文预算超限 | 未执行 | 未执行 |

所有成功工具回合都有 tool_started/tool_completed 事件，返回对应托管工作目录和 RM99_NATIVE_OK。停止测试在真实 text_delta 到达后发取消，四项均收敛到 cancelled，未以断开网页冒充停止。这里未验工具子进程在中途停止、原生压缩、图片或整机断电恢复。

ChatRaw 在 Pi 等待审批期间重启，run ID、session ID、待批 interaction ID 和 last_seq 均保持不变；重启后经原审批接口允许 pwd，随后完成。Runner 在全部任务终态后重启；四种成功 Agent 在原聊天准确回忆上轮标记和工作目录，原生身份保持不变。最终 Runner SQLite integrity_check=ok，非终态 run 数为零。Hermes Gateway 未随 Runner 重启。

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

Codex 的首次 sandbox pwd 被宿主 AppArmor unprivileged_userns 的 net_admin/setpcap 限制拒绝，原生记录为 `bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted`。允许单次原生审批后 pwd 成功。没有关闭 AppArmor、修改全局 sysctl 或将默认执行改成无沙箱；这仍是现有宿主上的使用边界。

## 版本与证据

部署源码是 `e91d32f3674389be2c94c3a939c6a4179246e4c2`，与总控交付时主目录309efa3运行模块相同。源码包和镜像包位于宿主 `/home/rm01/chatraw/deployment-e91d32f`，四项交付文件 SHA256 校验通过。

- 源码包 SHA256：9f86e7d2c8920d36577778171d723d38fe8e9bf46a9480f27b9ff0d36a412d2c。
- 镜像包 SHA256：7a15b08f4baa40339e6dbdd98215bdb1e5f6f791980a8e748c7add1427bc6450。
- 镜像 tag：chatraw-agent-integration:e91d32f-amd64。
- 归档 config digest：sha256:faeb75dc86eb10583fa0af6a800e3c630247e2a193d7c7f2cd232d48162a45a9。
- Docker29/containerd 导入后 OCI manifest/image ID：sha256:2baa5f343ed1e2069caa04de4aafb9b499548f388b41702aa41cc06323e0e724。
- 两个 ID 表示不同对象；已校验归档 config 哈希、镜像 Config 和全部12层 diff ID 完全一致，见 `18-image-content-proof.json`。

[机器可读汇总](summary.json) 给出各 chat/run ID。`07-*.json` 为首轮快照，`08-*-events.ndjson` 为实际事件，`10-chatraw-active-restart.json` 为重启两侧状态，`13/17` 为原生身份对比，`14-*` 为恢复结果，`16-*` 为停止请求和结果，`15-deepseek-native-failure.ndjson` 为筛选后的原生错误证据，`19-storage-state.json` 为空闲状态、持久目录权限与数据库完整性。

安装脚本/日志按实际执行历史保留，包含初次镜像ID比较退出、ensurepip缺失、Hermes Python版本约束等诊断。这些文件不是幂等的一键安装器，不应盲目重放。

归档日志仅规范化行尾空白与末尾空行；事件、错误和状态内容保持原样。
