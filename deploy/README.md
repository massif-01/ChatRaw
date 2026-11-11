# ChatRaw Docker + 宿主 Runner

普通聊天可以独立使用根目录 `docker-compose.yml`，不要求 Runner 或凭据。
Agent 的正式拓扑为浏览器 → ChatRaw Docker 同源 API → 宿主 loopback Runner → 原生 Agent。
不把五种 Agent 安装进主镜像。

## 宿主准备

由管理员在批准的部署窗口操作。`install-runner.sh` 只安装 Runner 与基础 Python 依赖，
不会启动服务、安装/升级原生 Agent、修改已有 Agent home 或停止已有 Hermes Gateway。

```sh
sudo bash deploy/install-runner.sh EXISTING_AGENT_ACCOUNT
```

选择实际持有原生认证和会话状态的现有账户。脚本准备：

- `/opt/chatraw-runner`：服务代码与独立 venv；
- `/etc/chatraw-runner/config.json`：首次安装复制示例，后续不覆盖；
- `/etc/chatraw-runner/token`：首次生成专用随机凭据，不打印；
- `/var/lib/chatraw-runner`：该账户所有，含独立 SQLite、工作目录、文件副本、Pi/DeepSeek持久根目录；
- `/etc/systemd/system/chatraw-runner.service`：服务用户固定为指定账户，尚未启动。

审核示例里的绝对路径并填入真实安装位置。`agents` 只放宿主配置；网页中的 model、provider、
reasoning 等按 adapter schema 保存，正在运行的任务保留原快照，下一次执行在空闲会话的
close/resume边界应用新设置，原生session不变。可执行程序、home及宿主目录变更用于新会话，
不会静默重定向已绑定聊天。

`workspaces` 例如 `{"project-a":{"path":"/srv/projects/a","label":"Project A"}}`。
浏览器只看到项目ID/label。普通任务的managed目录按session隔离。cwd不是权限沙箱。

## 原生程序与认证

|Agent|管理员准备项|
|---|---|
|Hermes|在该账户安装并配置支持canonical Gateway的Hermes，原生Gateway事先启动；`agents.hermes.executable`可为绝对路径，`home`可指定现有home。Runner仅运行`gateway attach --json`，不带start/recover，且只连接loopback。|
|Codex|服务账户PATH中的Codex CLI和原生认证。保持该账户原生配置/会话目录。当前C线验证0.153.4。|
|Claude|Runner venv可选安装`agent_runner/requirements-claude.txt`，锁SDK0.2.180。服务环境提供`ANTHROPIC_API_KEY`；不把订阅CLI OAuth当第三方SDK授权。|
|Pi|`executable`与`session_root`必须绝对路径，保留配套`pi_extensions`目录；当前D线验证1.5.2，需要Node≥22.19。使用服务账户原生认证。|
|DeepSeek|Runner venv可选安装`agent_runner/requirements-deepseek.txt`，SDK/runtime锁0.2.2rc2；`dsh_home`为已存在持久根目录，服务环境提供`DEEPSEEK_API_KEY`，可按需要提供`DEEPSEEK_BASE_URL`。每session独占runtime/home。|

可选SDK安装由管理员显式选择，在Runner venv内完成，不升级用户全局Agent。
`/etc/chatraw-runner/environment` 为 systemd 的私密 EnvironmentFile；需要时配置PATH与API key，
权限限制为root和服务账户可读，不提交到仓库、不通过网页普通settings发送。
服务本身按对应用户运行，认证文件由该账户的原生程序发现；不复制其他账户的凭据。

确认路径、程序、目录权限后才启动：

```sh
sudo systemctl enable --now chatraw-runner
sudo systemctl status chatraw-runner
```

这些命令在本次本地交付中未执行。RM-01的Docker Engine/Podman与原生安装由总控统一安排，
此脚本不安装Docker Engine、不卸载Podman。

## Agent Docker 部署

Linux host networking使主容器可访问宿主127.0.0.1；基础Compose不挂载秘密。
启用Agent使用专用overlay：

```sh
export CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token
docker compose -f docker-compose.yml -f deploy/docker-compose.agent.yml up -d --build
```

token以只读文件挂载进容器，容器内路径为`/run/secrets/chatraw-runner-token`。
不把token放进浏览器、镜像层、启动命令参数或日志。Runner协议入口要求Bearer凭据，
资源请求另核对chat归属；ChatRaw同时检查同源、限流、安装启用状态和绑定。

## 迁移、备份与回退

ChatRaw首次Agent schema迁移在有旧聊天时自动生成`chatraw.db.pre-agent-v1.bak`，新增绑定、
准入/显示投影表，不改写旧messages/model/settings。原Hermes key服务名与插件配置资料保留。
旧聊天没有可靠Agent身份字段，因此不猜测或自动重传历史；新建Agent聊天后绑定。
旧Hermes执行入口返回410，生产模块已移除旧执行循环/活动状态机。详见`docs/hermes.md`。

Runner schema2为M1数据增加宿主基础配置快照；从schema1迁移前生成`runner.pre-v2.bak`。
M1旧会话原完整快照作为其迁移基线保存；新公共设置从下一轮起覆盖可编辑字段。
数据库使用WAL，不能只复制正在运行的`.db`而丢弃WAL；用SQLite backup：

```sh
python script/agent_db_backup.py /path/chatraw.db /backup/chatraw-20261112.db
python script/agent_db_backup.py /var/lib/chatraw-runner/runner.db /backup/runner-20261112.db
```

工具拒绝覆盖现有目标，并运行integrity_check。ChatRaw与Runner的SQLite均使用FULL同步；
不同数据库之间没有分布式事务，需要一致回退点时先停止新准入并核实活动run，再在同一窗口备份。
备份还要覆盖Runner工作目录/文件副本、
Pi与DeepSeek根目录和各原生程序的会话存储；凭据按现有私密备份规则管理。

回退先显式停止并核实活动run；unknown不能当成已停。停ChatRaw/Runner后保留当前数据库和
文件树，恢复对应版本的备份到新位置再切换；不要对新schema做破坏性反向改写。
恢复旧ChatRaw版本时只恢复匹配旧schema的备份，较新记录保留供导出，不静默删除。
本地测试已验证加表后旧记录不变、备份可恢复为旧schema；现场停机/断电演练仍待验收。

## 重启语义

网页关闭或ChatRaw重启不取消宿主运行。ChatRaw后台按持久准入键找回run并按run_id幂等保存
最终显示记录。Runner重启先使旧交互失效；已派发任务核对原生状态，不重发prompt。
无可靠证据保持unknown并继续占session及总并发位。只有原生结束证据才能释放活动位。
不承诺断电无缝续跑；工具提交给外部服务的动作需要各Agent原生证据核实。

验收时分别测试网页、ChatRaw、Runner、整机四层重启，不能用本地进程测试替代宿主断电证据。
