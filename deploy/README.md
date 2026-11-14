# 安装 ChatRaw

先安装 **Runner 和 ChatRaw**，再按需添加 Agent。不需要先装齐五种 Agent。

- **ChatRaw** 提供聊天网页，运行在 Docker 中。
- **Runner** 在同一台服务器上调用 Agent，保存任务和原生会话，由系统负责开机启动。

安装后，用户仍然只打开 ChatRaw 网页。Runner 不需要对外开放端口。

## 开始前准备

在 Ubuntu Server 上准备好以下环境：

- Python 3.11 或更新版本，以及对应的 venv 组件。Ubuntu 24.04 可使用系统 Python，执行 `sudo apt-get install python3-venv` 补齐 venv。
- Docker Engine 和 Compose 插件，按 [Docker 官方说明](https://docs.docker.com/engine/install/ubuntu/)安装。
- 一个已有的普通账户，用来运行 Runner。已有 Agent 时，优先选择平时使用它们的账户。
- 本次发布的 ChatRaw 源码。进入源码根目录，再执行下面的命令。

安装向导需要在有 systemd 的 Linux 主机上运行，不是在 ChatRaw 容器内运行。向导会检查依赖；缺少时说明需要补什么，不会擅自更换系统 Python、Docker 或全局 Agent 安装。

## 情况一：新机器，还没有 Agent

运行：

```sh
sudo bash deploy/setup-new.sh
```

向导会询问 Runner 使用哪个账户，然后列出准备执行的操作。确认后，它会：

1. 安装 Runner 及其独立 Python 环境，创建连接凭据和持久数据目录。
2. 设置 Runner 开机启动。
3. 构建并启动 ChatRaw Docker 容器，接通本机 Runner。
4. 检查网页服务，告诉你访问地址和下一步。

**不会安装五个 Agent，也不会替你调用模型。** 打开 `http://服务器IP:51111`，先配置普通聊天模型即可使用；想使用哪个 Agent，再看[按需添加 Agent](MANUAL.md#add-agent)。

## 情况二：机器上已经有 Agent

运行：

```sh
sudo bash deploy/setup-existing.sh
```

选择平时运行 Agent 的普通账户。向导会逐个询问是否接入 Codex、Pi、Hermes，可以全部跳过，也可以只选一个。

- 找到程序时，会显示路径供你确认；找不到时，可以手动填写完整路径。
- 配置目录由你确认。复用该目录，就会使用其中的原生设置和凭据；脚本不复制密钥，也不改写这些文件。
- 若程序依赖 Node.js，还会询问 Node.js 的路径，确保后台服务也能找到它。
- Hermes 连接你已有的 Gateway，脚本不会接管、启动或停止它。请先确保对应 Gateway 可用。
- Claude 和 DeepSeek 当前需要 Runner 专用环境中的 SDK。向导会单独询问是否安装，默认不安装；仅有现成 CLI 不代表已经满足接入要求。

在执行前，向导会列出运行账户、路径、选中的 Agent 和要安装的组件。检查无误后输入 `y`；直接回车表示不执行。

模型地址和 API key 不在向导里填写。安装完成后，根据[模型配置参考](REFERENCE.md#models)配置，再到 ChatRaw 网页安装并启用对应插件，发送一条简短消息验证。文档中的 RM-01 地址只是示例，不要照搬到自己的机器。

## 已有配置和数据会怎样处理？

两个入口共用同一个安装程序，采取相同规则：

|检测到的情况|向导怎么做|
|---|---|
|没有 Runner|创建新安装，不覆盖任何现有路径|
|已有完整且运行中的 Runner，使用标准本机连接配置|复用，不修改代码、配置、凭据，不重启、不追加 SDK；需要新增 Agent 时按手动指南操作|
|已有 Runner，但未运行或使用自定义连接配置|停止并说明原因，交由你按原部署方式处理|
|已有 `chatraw` 容器|保留原样，不重建；提醒核对它是否已连接 Runner|
|有旧 ChatRaw 数据卷，却没有对应容器|停止，避免把旧数据交给不匹配的版本|
|发现未完成的 Runner 安装|停止并保留现场，按下方“安装中断”处理|

**复用已有容器不等于自动改好了它的连接配置。** 如果原容器尚未连接 Runner，需要按[手动部署步骤](MANUAL.md#new-machine)添加 Agent Compose 配置，并在维护窗口更新。向导不会为此直接中断你的现有服务。

这两个脚本用于首次安装和安全复用，不是升级工具。已有运行中部署的升级、备份和恢复，见[维护参考](REFERENCE.md#maintenance)。

## 安装结束后检查什么？

1. 看终端是否显示“ChatRaw 就绪检查：通过”。如果尚未就绪，按提示查看日志。
2. 打开 `http://服务器IP:51111`，确认网页可访问。
3. 配置普通聊天模型，发送一条短消息。
4. 使用 Agent 时，安装并启用对应插件，检查可用性，再新建 Agent 聊天验证回答。

“Runner 已运行”“程序已安装”和“模型能回答”是不同的检查结果。向导不会在没有实际模型请求的情况下宣称 Agent 已完全可用，也不会自动消耗你的 API 余额。

## 安装中断或报错

- **确认前退出**：没有执行安装，可直接重新运行。
- **缺少依赖**：按终端提示补齐，然后重新运行。
- **Runner 已完整安装，Docker 构建失败**：修正 Docker 错误后重新运行，向导复用 Runner；若已经创建旧卷或容器，按显示的保留规则处理。
- **Runner 安装到一半失败**：向导会保留现场，不自动删目录、改配置或继续覆盖。先保留报错，查看 `/opt/chatraw-runner`、`/etc/chatraw-runner` 和 `/var/lib/chatraw-runner` 的实际状态，再按[手动安装](MANUAL.md)补齐。不要删除数据目录来强行重装；不确定时将报错交给管理员。

常用检查命令：

```sh
systemctl is-active chatraw-runner
sudo journalctl -u chatraw-runner -n 50 --no-pager
sudo docker logs --tail=50 chatraw
```

## 数据保存在哪里？

|位置|内容|
|---|---|
|Docker 卷 `chatraw_chatraw_data`|聊天、附件、插件和网页设置|
|`/var/lib/chatraw-runner`|Runner 状态、默认工作目录及新建的原生会话|
|`/etc/chatraw-runner`|服务配置、环境变量和连接凭据|
|你选择复用的原生配置或项目目录|已有 Agent 配置、会话及工作文件|

备份时需包括这些位置。只保存 Docker 卷不能完整恢复 Agent 会话。具体方法见[备份与恢复](REFERENCE.md#maintenance)。

需要自定义安装时，可使用[手动部署指南](MANUAL.md)；各 Agent 的版本和模型示例放在[安装配置参考](REFERENCE.md)。
