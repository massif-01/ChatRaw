# 部署 ChatRaw：先运行，再按需添加 Agent

你不需要先装齐五种 Agent。先安装 **Runner**，再启动 **ChatRaw**；以后想用哪个 Agent，再安装、配置哪个。

- **ChatRaw**：运行在 Docker 中，提供聊天网页。
- **Runner**：运行在同一台 Linux 机器上，负责调用 Agent、保存运行状态，由系统负责开机启动。
- **Agent 插件**：提供网页里的选择入口和设置。安装插件不会自动安装对应的 Agent 程序。

浏览器只访问 ChatRaw。Runner 只接受本机连接，不需要给它开放外网端口。

## 选择你的安装方式

|你的机器情况|从这里开始|
|---|---|
|新机器，还没有安装 Agent|[路径一：新机器](#new-machine)|
|已经在用 Codex、Pi、Hermes 等 Agent|[路径二：已有 Agent](#existing-agents)|
|已经装好 ChatRaw 和 Runner，想增加 Agent|[按需添加 Agent](#add-agent)|

以下命令适用于 Ubuntu Server，均从下载好的 ChatRaw 发布源码根目录执行。示例使用已有的普通账户 `rm01`；请换成你的实际账户。需要管理员权限的命令带有 `sudo`。本页不会让你切换现有模型。

<a id="new-machine"></a>
## 路径一：新机器

### 1. 准备 Docker 和 Python

安装 Docker Engine 和 Compose 插件，参照 [Docker 的 Ubuntu 安装说明](https://docs.docker.com/engine/install/ubuntu/)。Runner 需要 Python 3.11 或更新版本；Ubuntu 24.04 可使用系统自带的 Python。

```sh
sudo apt-get update
sudo apt-get install -y python3-venv
python3 --version
docker version
docker compose version
```

确认这些命令能显示版本信息。如果 Docker 提示权限不足，后面的 Docker 命令使用 `sudo`，或请管理员配置当前账户的 Docker 权限。此时不需要安装 Node.js 或任何 Agent。

### 2. 安装并启动 Runner

```sh
sudo bash deploy/install-runner.sh rm01
sudo systemctl enable --now chatraw-runner
systemctl is-active chatraw-runner
```

看到 `active`，说明 Runner 已启动，且已设置开机自启。安装脚本会准备独立 Python 环境、数据目录、连接凭据和服务配置，不会安装 Agent。

**没有安装 Agent 时，Runner 仍可运行。** 对应 Agent 暂时不可用是正常的，稍后按需添加即可。

如果没有看到 `active`，先查看错误，不要反复安装：

```sh
sudo journalctl -u chatraw-runner -n 50 --no-pager
```

### 3. 启动 ChatRaw

```sh
export CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token
docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml up -d --build chatraw
```

如果需要管理员权限，将最后一行改为：

```sh
sudo env CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml up -d --build chatraw
```

这会构建并启动 ChatRaw，将连接 Runner 的凭据只读挂载到容器中。无需复制或粘贴凭据内容。请确保 `51111` 端口没有被其他程序占用。

在浏览器打开 `http://你的服务器地址:51111`。能看到聊天页面，说明网页服务已运行。在设置中添加你自己的模型，发送一条普通聊天消息，确认回答正常。

**到这里，基础部署就完成了。** 需要 Agent 时，再看[按需添加 Agent](#add-agent)。

<a id="existing-agents"></a>
## 路径二：机器上已经有 Agent

你可以保留现有安装，不必把所有 Agent 重装一遍。先确定由哪个账户运行 Runner，以及这个账户能访问哪些 Agent。

### 1. 确认账户和已有程序

登录平时运行 Agent 的账户，查看已安装程序的位置。只检查你实际使用的 Agent：

```sh
whoami
command -v codex
command -v pi
command -v hermes
```

记下程序路径，以及现有模型配置和会话目录的位置。命令没有输出，通常表示该程序不在当前账户的 PATH 中，需找到实际安装位置。

**推荐让 Runner 使用已有 Agent 的普通账户。** 不要为了访问另一个用户的安装而改成 root 运行。若各 Agent 分属不同账户，先确定哪些程序和配置允许由 Runner 账户访问；不能假定一个账户自动拥有所有用户的登录状态和文件权限。

### 2. 安装 Runner 和 ChatRaw

按[新机器路径](#new-machine)检查 Docker/Python，然后执行第 2、3 步，把 `rm01` 换成刚确认的账户。

安装 Runner 使用自己的 `/opt/chatraw-runner`、`/etc/chatraw-runner` 和 `/var/lib/chatraw-runner`，不会自动改写已有 Agent 的配置，也不会替你启动或停止已有 Hermes Gateway。

如果这台机器已经有 ChatRaw Runner，应按[更新与备份说明](REFERENCE.md#maintenance)处理，不要当作首次安装重跑。

### 3. 接入已有 Agent

Runner 是后台服务，**不会自动读取你终端的 `.zshrc`、`.bashrc` 或临时 `export`**。所以“终端能运行”还不等于“Runner 能运行”。按下表配置：

|已有 Agent|接入方式|
|---|---|
|Codex CLI|在 `/etc/chatraw-runner/environment` 的 `PATH` 中加入 Codex 所在目录，并设置实际使用的 `CODEX_HOME`。|
|Pi|在 `/etc/chatraw-runner/config.json` 的 `agents.pi` 中填写程序绝对路径 `executable` 和会话目录 `session_root`；需要复用模型配置时，在 environment 中设置 `PI_CODING_AGENT_DIR`。|
|Hermes|在 config.json 的 `agents.hermes` 中填写程序绝对路径和 `home`，连接对应 home 的现有 Gateway。已有 Gateway 可用时，不另建一个抢占它。|
|Claude Code|当前通过 Claude Agent SDK 接入，需要在 Runner 的虚拟环境安装 SDK；不会仅凭已有 `claude` 命令自动复用它。此接入使用 API key，不会自动复用订阅登录。|
|DeepSeek Harness|当前需要在 Runner 的虚拟环境安装匹配的 SDK/runtime；仅在另一个 Python 环境安装过 Harness 还不够。已有配置需按当前适配器要求核对。|

环境文件可用 `sudoedit /etc/chatraw-runner/environment` 编辑，保存后限制访问权限：

```sh
sudo chown root:"$(id -gn rm01)" /etc/chatraw-runner/environment
sudo chmod 0640 /etc/chatraw-runner/environment
```

将命令里的 `rm01` 替换为 Runner 账户。PATH 要保留系统目录；如果程序依赖 Node.js，还要包含实际的 Node.js 所在目录。不要直接复制其他机器的模型地址和 key。配置格式见 [环境文件示例](runner-environment.example) 和 [Runner 配置示例](runner-config.example.json)；其中 RM-01 地址只是示例。

确认 Runner 账户对程序有执行权限、对配置有读取权限、对会话和工作目录有写入权限。复用已有 home 意味着会使用其中的设置和凭据；需要独立配置时，给 ChatRaw 单独准备一个 home。

完成后按[添加后的检查](#verify-agent)确认连接。

<a id="add-agent"></a>
## 按需添加 Agent

只安装你想使用的 Agent，不需要把下面每项都执行一遍。

|想使用的 Agent|需要安装什么|具体步骤|
|---|---|---|
|Codex CLI|Node.js 和 Codex CLI，或接入已有安装|[Codex 安装](REFERENCE.md#install-codex)|
|Pi|Node.js 和 Pi，或接入已有安装|[Pi 安装](REFERENCE.md#install-pi)|
|Hermes|Hermes 及其独立 Python 环境，还需要原生 Gateway|[Hermes 安装](REFERENCE.md#install-hermes)、[启动 Gateway](REFERENCE.md#start-services)|
|Claude Code|Runner 虚拟环境中的 Claude Agent SDK，包含配套 Claude Code|见下方命令|
|DeepSeek Harness|Runner 虚拟环境中的 SDK 和 runtime|见下方命令|

只使用 Claude 时，执行：

```sh
sudo /opt/chatraw-runner/venv/bin/python -m pip install -r /opt/chatraw-runner/agent_runner/requirements-claude.txt
```

只使用 DeepSeek 时，执行：

```sh
sudo /opt/chatraw-runner/venv/bin/python -m pip install -r /opt/chatraw-runner/agent_runner/requirements-deepseek.txt
```

安装完成后，还要配置该 Agent 使用的模型、凭据和数据目录。用官方 API 时填写自己的凭据；用本地模型时，核对它支持的接口。具体文件位置和示例见 [模型配置参考](REFERENCE.md#models)。其中的 RM-01 地址不是通用默认值，请勿直接照搬。

<a id="verify-agent"></a>
### 添加后的检查

1. 确认没有正在执行或等待审批的 Agent 任务，再重启 Runner，让新配置生效：

   ```sh
   sudo systemctl restart chatraw-runner
   systemctl is-active chatraw-runner
   ```

2. 在 ChatRaw 的插件页面安装并启用对应插件，保存该 Agent 的设置。
3. 查看可用性检查。如果提示找不到程序，检查服务账户和路径；如果缺少 SDK，检查是否装进 `/opt/chatraw-runner/venv`。
4. 新建聊天，在输入框旁选择该 Agent，发送一条简短消息。再让它报告工作目录，确认原生工具能运行；遇到审批时核对内容后再决定是否允许。

能看到 Agent 返回回答，才算模型链路接通。仅显示程序已安装，不代表模型地址和凭据一定正确。新增 Agent 通常不需要重建 ChatRaw 容器，也不需要重装 Runner。

## 重启和备份：记住这三处

|保存位置|里面有什么|
|---|---|
|Docker 卷 `chatraw_chatraw_data`|ChatRaw 聊天、附件、插件和网页设置|
|`/var/lib/chatraw-runner`|Runner 状态、默认工作目录和原生 Agent 会话|
|`/etc/chatraw-runner`|连接凭据、环境变量和服务配置|

如果接入了其他位置的 Agent home 或项目目录，也要一起备份。**只备份 Docker 卷，不能完整恢复 Agent 会话。**

正常重启机器后，已启用的服务会自动启动，磁盘中的聊天和工作文件会保留；正在执行的任务不保证无缝继续。完整备份、升级和恢复时按[维护步骤](REFERENCE.md#maintenance)操作，不要直接复制正在写入的数据库文件。

## 遇到问题先看哪里

|现象|下一步|
|---|---|
|网页打不开|运行 `docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml logs --tail=50 chatraw`；需要在当前终端保留前面设置的 `CHATRAW_RUNNER_TOKEN_FILE`。同时检查服务器的 51111 端口和访问规则。|
|普通聊天正常，但所有 Agent 都连接失败|运行 `systemctl is-active chatraw-runner`，再查看 `sudo journalctl -u chatraw-runner -n 50 --no-pager`。|
|只有一个 Agent 不可用|查看该插件的具体错误，检查程序路径、SDK、模型和凭据，不必重装所有组件。|
|终端能使用 Agent，网页却找不到|核对 Runner 运行账户及 environment 中的 PATH；后台服务不会继承终端临时设置。|
|出现 `unknown` 状态|表示尚不能确认原任务是否结束。保留记录并检查原生进程，不要删除记录后重新执行同一任务。|

更多版本、模型示例和维护细节放在[安装与维护参考](REFERENCE.md)，需要时再查。
