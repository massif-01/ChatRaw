# Agent 安装、配置与维护参考

首次部署请先阅读 [部署入门](README.md)，根据机器情况选择安装路径。本页供需要安装某个 Agent、配置模型或维护数据时查阅，不必从头执行全部命令。

本指南供 Linux 管理员安装、更新和恢复 ChatRaw。普通聊天运行在 Docker 中；五种 Agent 由宿主上的 Runner 调用各自原生程序。浏览器只访问 ChatRaw，Runner 只监听宿主回环地址。

2026-11-13 已在 Ubuntu 24.04.4、Linux/amd64 上完成实际部署。本文给出人工操作步骤，**不是一键安装器**。已有部署请先阅读“更新、备份与恢复”，不要直接重跑首次安装命令。

## 1. 确认环境与安装账户

|组件|现场验证版本|
|---|---|
|Docker Engine / Compose|29.9.3 / 5.7.1|
|Runner Python|3.12.3；项目要求 Python 3.11 或更新版本|
|Node.js / npm|22.23.2 / 10.9.8；本次 Pi 使用 Node 22|
|Codex CLI|0.153.4|
|Claude Agent SDK / 随附 Claude Code|0.2.180 / 2.1.321|
|Pi|1.5.2，包名 `@earendil-works/pi-coding-agent`|
|DeepSeek SDK / runtime|均为 0.2.2rc2|
|Hermes|提交 `6a0d2d12815c0546b0bcaf05046e2fe3293f60aa`；该锁文件要求 Python 3.14 或更新版本，现场使用独立的 3.14.10|
|uv|0.13.8，用于项目独立 Python 环境|

先检查现有 Docker 与 Compose，已可用就复用。新 Ubuntu 主机按 [Docker 官方安装说明](https://docs.docker.com/engine/install/ubuntu/)安装 Engine 和 Compose 插件；ChatRaw 的脚本不安装 Docker。

```sh
docker version
docker compose version
python3 --version
node --version
npm --version
```

选择已有的非 root 服务账户，以下例子使用 `rm01`。如使用其他账户，替换命令和 systemd 模板中的账户，并按实际主组调整权限。Docker 操作需要该账户具有 Docker 权限，或由管理员执行。

先确认 51111 未被占用；51112 只供本机 Runner 使用。保留宿主现有服务，不为安装 ChatRaw 停用无关服务。

## 2. 安装 Runner 和原生程序

以下命令从**本次发布源码的仓库根目录**执行，普通命令使用服务账户。部署前保存源码版本、镜像标签和文件校验值，后续恢复使用相同版本。

### Runner

先准备可创建 venv 且带 pip 的 Python。在新 Ubuntu 主机上可安装与系统 Python 匹配的 `python3-venv` 组件，再执行：

```sh
sudo bash deploy/install-runner.sh rm01
```

该脚本复制 Runner、建立独立 venv、安装基础依赖、首次创建配置与 token、安装 systemd unit 并刷新服务配置。它**不会启动服务、安装五种 Agent、配置模型或部署 Docker 容器**。它会更新 Runner 代码和 unit，因此已有部署必须在维护窗口使用。

如果 Python 报 `ensurepip is not available`，先处理环境，不要反复重跑脚本。现场采用了人工替代路径：复制相同 Runner 代码与 unit，以 `python3 -m venv --without-pip` 创建环境，再用项目内 uv 的 `pip install --python /opt/chatraw-runner/venv/bin/python` 安装相同 requirements；目录、首次 token 和账户权限仍需管理员完整准备。这是现场手动安装记录，不是 `install-runner.sh` 已支持的自动分支。一般新部署补齐 venv 组件后使用上面的脚本更直接。

Claude 和 DeepSeek 的可选 SDK 安装命令分别列在[按需添加 Agent](MANUAL.md#add-agent)，只执行所需项。

<a id="install-codex"></a>
### 安装 Codex

先准备 Node.js（本次验证版本见上表），确认 `node --version` 和 `npm --version` 正常。使用项目独立目录，避免覆盖已有全局安装；下面命令使用服务账户执行：

```sh
sudo install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents/codex
npm install --prefix /opt/chatraw-agents/codex --no-audit --no-fund @openai/codex@0.153.4
/opt/chatraw-agents/codex/node_modules/.bin/codex --version
```

看到版本号后，将程序目录加入 Runner 的 PATH，再配置模型。无需安装 Pi。

<a id="install-pi"></a>
### 安装 Pi

先准备 Node.js 22，确认 `node --version` 和 `npm --version` 正常。下面命令使用服务账户执行：

```sh
sudo install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents/pi
npm install --prefix /opt/chatraw-agents/pi --no-audit --no-fund @earendil-works/pi-coding-agent@1.5.2
/opt/chatraw-agents/pi/node_modules/.bin/pi --version
```

看到版本号后，在 Runner 配置中填写该程序的绝对路径和会话目录，再配置模型。Runner 源码中的 `pi_extensions` 必须一同保留。无需安装 Codex。

<a id="install-hermes"></a>
### Hermes

使用支持原生 Gateway 的已验证提交。先按 [uv 官方说明](https://docs.astral.sh/uv/getting-started/installation/)将 uv 0.13.8 准备在 `/opt/chatraw-agents/tools/bin/uv`；可从官方发行包安装到此目录，不需要更换系统 Python。以下是首次安装命令，目标目录应为空：

```sh
sudo install -d -m 0755 -o rm01 -g rm01 /opt/chatraw-agents/hermes /opt/chatraw-agents/python /opt/chatraw-agents/cache
git clone https://github.com/NousResearch/hermes-agent.git /opt/chatraw-agents/hermes/source
git -C /opt/chatraw-agents/hermes/source checkout --detach 6a0d2d12815c0546b0bcaf05046e2fe3293f60aa
export UV_PYTHON_INSTALL_DIR=/opt/chatraw-agents/python
export UV_CACHE_DIR=/opt/chatraw-agents/cache/uv
/opt/chatraw-agents/tools/bin/uv sync --project /opt/chatraw-agents/hermes/source --locked --no-dev --python 3.14.10
/opt/chatraw-agents/tools/bin/uv pip install --python /opt/chatraw-agents/hermes/source/.venv/bin/python aiohttp==3.14.5
/opt/chatraw-agents/hermes/source/.venv/bin/hermes --version
```

这组命令把 Python 和依赖放在项目目录。`aiohttp` 是本次 Gateway 接线实际使用的显式依赖。升级 Hermes 前应重新验证 Gateway 协议，不能只依赖 CLI 版本命令成功。

## 3. 配置目录、账户与服务环境

首次部署准备独立原生 home。已有账户正在使用的 home 不应被这些示例覆盖：

```sh
sudo install -d -m 0700 -o rm01 -g rm01 \
  /var/lib/chatraw-runner/codex-home /var/lib/chatraw-runner/claude-home \
  /var/lib/chatraw-runner/pi-home /var/lib/chatraw-runner/hermes-home
```

|位置|用途与权限|
|---|---|
|`/opt/chatraw-runner`|Runner 代码和 venv，管理员维护|
|`/opt/chatraw-agents`|独立原生程序、Hermes Python 与依赖|
|`/etc/chatraw-runner`|配置目录，root 与服务账户主组可进入，0750|
|`/etc/chatraw-runner/token`|Runner 专用随机凭据，服务账户可读，0600；不输出其内容|
|`/etc/chatraw-runner/environment`|systemd 环境文件，root/服务账户主组可读，0640|
|`/var/lib/chatraw-runner`|Runner 数据库、工作目录、附件副本及原生会话，服务账户拥有，0700|
|Docker 卷 `chatraw_chatraw_data`|ChatRaw 数据库、模型配置、附件、已安装插件及插件设置|

按 [runner-config.example.json](runner-config.example.json)核对 `/etc/chatraw-runner/config.json`，并用 [runner-environment.example](runner-environment.example)准备环境文件。**示例不是已授权覆盖现有文件的命令**；先检查目标文件，再由管理员编辑和设置权限。

首次部署且目标 environment 尚不存在时，可复制示例后编辑：

```sh
sudo install -m 0640 -o root -g rm01 deploy/runner-environment.example /etc/chatraw-runner/environment
```

配置中的 `workspaces` 可登记已有项目，例如 `{"project-a":{"path":"/srv/projects/a","label":"Project A"}}`。未选择项目时，每个聊天获得独立工作目录。工作目录并不等于权限沙箱；原生 Agent 的权限与审批仍然生效。

宿主配置包括程序路径、home、会话根目录和 DeepSeek `provider`、`patches`。这些配置只用于新会话；旧聊天继续使用建立时保存的宿主配置。网页允许编辑的模型、推理强度、DeepSeek `max_tokens` 及其他 Agent 的 provider 等在下一轮空闲会话恢复时生效，不替换原生会话 ID。DeepSeek 的 provider 仅由宿主管理员配置。

<a id="models"></a>
## 4. 接入模型：以 RM-01 本地服务为例

官方 DeepSeek Flash 的独立配置与本轮实测范围见[官方复验记录](../docs/agent-platform/reviews/official-flash-20261114/README.md)、[Harness/Pi 配置](../docs/agent-platform/handoffs/D-field/deepseek-official-flash.md)和[Codex/Claude 配置](../docs/agent-platform/handoffs/C-local-model-98/deepseek-official-codex-claude.md)。这些是可选的独立 provider 配置，不代表现有生产会话已切换；按真实模型能力和价格选用，凭据留在受限宿主环境中。

下面例子对应已验证服务 `http://10.10.99.98:58000`、精确模型名 `RM-01 VLM`，上下文上限262144。该局域网端点无需认证；示例中的占位 key 只用于满足 SDK 格式检查。其他服务必须使用它实际要求的认证，不能照搬无鉴权配置。

环境文件中的 `NO_PROXY` 和 `no_proxy` 应覆盖回环地址及模型、ChatRaw 的实际内网地址，避免局域网请求被账户代理转发。此处只设置项目服务环境，不修改系统全局代理。

### Codex

服务账户的 `/var/lib/chatraw-runner/codex-home/config.toml`：

```toml
model = "RM-01 VLM"
model_provider = "rm01"

[model_providers.rm01]
name = "RM-01 local vLLM"
base_url = "http://10.10.99.98:58000/v1"
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false

[model_providers.rm01.capabilities]
remote_compaction = "unsupported"
```

该直连服务没有 Responses compact 接口，配置选择原生本地压缩。其消息模板会拒绝压缩后的原生权限消息位置；本版本提供下述可选兼容配置，并已在 RM-01 验证同一原生会话的压缩、标记续接、工具执行和图片输入。该兼容配置默认关闭，使用本地模型且需要此兼容行为时由管理员明确启用。

在 Runner 宿主配置的 `agents.codex` 中增加：

```json
{
  "responses_compat_upstream": "http://10.10.99.98:58000/v1/responses"
}
```

这必须是已确认无鉴权的固定上游，不能填带凭据的地址。省略字段时仍使用上面的原生 provider。该字段不属于网页插件设置；启用后 Runner 管理仅监听本机的临时兼容入口，将原生指令顺序调整为该模型服务接受的形式，保留普通消息、工具、图片与流式响应。管理员不需要再配置对外监听端口。

该结构性配置只用于**新绑定的会话**，旧聊天继续使用原快照；不要重写旧绑定或将新聊天冒充旧会话恢复。仍用同一 CODEX_HOME、原模型名称及原权限/审批策略。当前配置和实现说明见发布附带的 `docs/agent-platform/handoffs/C-local-model-98/codex-responses-compat.md`。RM-01 的新建验收会话已通过实际模型验证；历史失败回合保留，不改写为成功。

### Claude

环境示例使用 `ANTHROPIC_BASE_URL=http://10.10.99.98:58000`，**不带 `/v1`**；将默认 Haiku/Sonnet/Opus 模型均指向 `RM-01 VLM`，网页插件设置也选择该精确模型名。原生 home 由 `CLAUDE_CONFIG_DIR` 指定。接入需要认证的服务时使用 SDK 支持的凭据，不把其他账户的订阅登录状态复制过来。

### Pi

创建 `/var/lib/chatraw-runner/pi-home/models.json`：

```json
{
  "providers": {
    "rm01": {
      "baseUrl": "http://10.10.99.98:58000/v1",
      "api": "openai-completions",
      "apiKey": "local-no-auth-placeholder",
      "models": [{
        "id": "RM-01 VLM",
        "input": ["text", "image"],
        "contextWindow": 262144,
        "maxTokens": 8192
      }]
    }
  }
}
```

网页中 Pi 的 provider 选择 `rm01`、model 填 `RM-01 VLM`。配置文件由服务账户读取，保持0600权限。

### Hermes

创建 `/var/lib/chatraw-runner/hermes-home/config.yaml`：

```yaml
model:
  provider: custom
  default: RM-01 VLM
  base_url: http://10.10.99.98:58000/v1
  supports_vision: true
agent:
  image_input_mode: native
auxiliary:
  title_generation:
    enabled: false
plugins:
  auto_update_check_hours: 0
```

网页中 provider 选择 `custom`、model 填 `RM-01 VLM`。环境中的 `OPENAI_BASE_URL` 同样带 `/v1`。图片应走原生图片通道，不以文字描述替代附件。使用独立 Gateway 服务前，确认不会接管或停止账户已有的 Gateway。

### DeepSeek Harness

RM-01 的本地服务使用 Harness 内置 `llm-pi-ai` 的 OpenAI-compatible 路由。此前默认 Messages 路由发送的 `thinking`、`output_config` 未被该服务转换，实际未打开模型的思考模板；固定请求因此出现错误工具格式和空参数。新路由用原生配置正确传递 `chat_template_kwargs.enable_thinking`，不修改模型服务或审批机制。详见[协议定位](../docs/agent-platform/handoffs/C-local-model-98/deepseek-messages-thinking.md)。

1. 将 [v2 宿主 patch](../docs/agent-platform/handoffs/D-field/deepseek-rm01-models-v2.patch.yml)安装为 `/etc/chatraw-runner/deepseek-rm01-models-v2.patch.yml`，核对端点、模型名、上下文上限和图片模态。文件由 root 管理、服务账户主组可读，0440。
2. 在现有宿主 `agents.deepseek` 中合并以下配置，保留原 `dsh_home`。环境中保留 `DEEPSEEK_API_KEY`；本地无鉴权服务可用占位值，其他服务使用其真实凭据。v2 的端点由 patch 的 `baseURL` 决定。

```json
{
  "provider": "rm01-qwen",
  "model": "RM-01 VLM",
  "reasoning_effort": "high",
  "max_tokens": 8192,
  "patches": ["/etc/chatraw-runner/deepseek-rm01-models-v2.patch.yml"]
}
```

3. 网页中 model 填 `RM-01 VLM`，`max_tokens` 填 **8192**，推理强度用 `high` 或留空继承宿主设置。公开设置会覆盖宿主默认，须核对有效值。该模型的 `off` 会如实关闭思考模板，不能把它当作已验证相同工具表现的设置。省略预算会沿用原生默认值；现场默认256000曾使输入加输出预算超过模型上限。
4. 在无执行任务的维护窗口重启 Runner，然后**新建 Agent 聊天**。不需要修改或重启共享模型服务。通过实际待审卡片确认完整命令与目录，再由用户选择拒绝或仅允许一次。

`provider` 和 `patches` 都不接受浏览器编辑。旧聊天不回填这些结构性配置；保留原 [v1 patch](deepseek-rm01-models-v1.patch.example.yml) 文件及其内容供旧会话恢复。省略 provider 的配置仍使用原生默认 `deepseek-official`，其 `DEEPSEEK_BASE_URL` 和认证方式不变。不要用覆盖旧 patch 文件的方式迁移会话。

### 普通聊天

Agent 插件设置与普通聊天模型配置彼此独立。普通聊天需要单独配置一个聊天模型：api_url 填 `http://10.10.99.98:58000/v1`，model_id 为 `RM-01 VLM`，context_length262144、max_output8192，后端会追加 `/chat/completions`。现场保留了原模型配置 ID `default-chat`。

没有对应服务时，让 embedding/rerank 保持未配置，不要把 VLM 填成嵌入或重排模型。

<a id="start-services"></a>
## 5. 启动 Gateway、Runner 与 ChatRaw

首次使用本部署专属 Hermes Gateway，可依据 [chatraw-hermes.service.example](chatraw-hermes.service.example)创建 unit，替换其中账户。它加载相同的项目环境文件，运行 `hermes gateway run`。不要覆盖同名既有服务。

确认该 unit 尚不存在且模板账户正确后，首次安装：

```sh
sudo install -m 0644 deploy/chatraw-hermes.service.example /etc/systemd/system/chatraw-hermes.service
sudo systemctl daemon-reload
sudo systemctl enable --now chatraw-hermes
sudo systemctl enable --now chatraw-runner
systemctl is-active chatraw-hermes chatraw-runner
```

Runner 只执行 `hermes gateway attach --json` 连接已有 Gateway，不负责自动启动或恢复共享 Gateway。

确认环境与路径后构建 ChatRaw。项目名固定为 `chatraw`，避免不慎创建另一个空数据卷：

```sh
export CHATRAW_RUNNER_TOKEN_FILE=/etc/chatraw-runner/token
docker compose -p chatraw -f docker-compose.yml -f deploy/docker-compose.agent.yml up -d --build chatraw
```

Linux host networking 使容器能访问宿主127.0.0.1:51112。token从宿主只读挂载至 `/run/secrets/chatraw-runner-token`，不放进镜像、浏览器或普通插件设置。

使用交付的预构建镜像时，先校验文件、`docker load` 导入，再增加一个明确指定该镜像的 Compose overlay：

```yaml
services:
  chatraw:
    image: YOUR_VERIFIED_IMAGE_TAG
    pull_policy: never
```

将其作为最后一个 `-f` 文件，使用 `up -d --no-build --no-deps chatraw`。不要直接照填未确认的标签，也不要仅往旧容器热拷贝文件当作最终部署。已安装插件在数据卷中；镜像的插件市场文件更新不会自动覆盖已安装副本。需要同步单个资产时，只替换目标文件并验证设置保持不变，不通过卸载重装实现。

## 6. 检查是否可用

打开 `http://HOST:51111`，先确认普通聊天能返回一条短回答。再在插件市场安装并启用所需 Agent，逐项保存模型设置，查看能力检查并新建对应 Agent 聊天。

```sh
curl -fsS http://127.0.0.1:51111/ready
curl -fsS -H 'Origin: http://127.0.0.1:51111' http://127.0.0.1:51111/api/agents
```

`/ready` 检查主服务和数据库；Agent“ready”主要确认程序、协议及配置，不能代替真实模型请求。至少核对一条回答、一次无害工具操作、一次停止及同聊天续接；需要图片时用只有像素包含答案的图片确认，不以回合 completed 单独判定。

现场部分原生沙箱受到宿主限制。命令若被沙箱拒绝，应查看原生错误，按准确命令选择单次批准或拒绝；不要为了通过检查关闭系统保护或将全部任务改成无约束执行。`unknown` 的含义见下节。

2026-11-13 已验证普通聊天、五 Agent 基础工具/会话恢复/生成停止，以及对应专项记录。Codex 工具中途停止修复已通过新会话现场测试；旧未知记录仍保持隔离。2026-11-14经用户明确授权完成一次正常整机重启：服务自动恢复，五Agent在原生会话中正确续答，配置/聊天/工作目录保留。手机实机仍按用户要求暂缓；不承诺运行中强制断电后任务无缝继续。具体范围以 [验收记录](../docs/agent-platform/VALIDATION.md)为准。

<a id="maintenance"></a>
## 7. 更新、备份与恢复

### 先判断任务状态

关闭网页或重建 ChatRaw 容器不会主动取消宿主任务。Runner 重启则需要检查原生状态，旧审批会失效；它不会自动重发已提交的提示。

`unknown` 表示无法确认任务是否结束。它继续占用原会话和一个并发位置，不能当作已停止，也不能通过编辑数据库、删除聊天或伪造成功来释放。先保留 run/session ID、原生记录和工作目录，由管理员核实。需要运维重启时应明确维护窗口及恢复行为，保存前后证据，不能顺便清除未知记录。

更新前检查所有聊天，不只看管理员当前打开的一条。确认没有排队、执行中、待审批/待输入或停止中的任务，通知使用者维护窗口，再更新需要变更的层：仅前端/主镜像更新只重建ChatRaw；Runner或原生配置变更才安排相应服务重启。不要取消用户任务来腾出更新窗口。

### 备份内容与一致性

至少保存：

- ChatRaw整个数据卷：聊天数据库、附件、模型配置、已安装插件和插件设置。
- `/var/lib/chatraw-runner`：Runner数据库、工作目录、附件副本、五种原生home与会话目录。
- `/etc/chatraw-runner`：配置、环境文件、token及所有仍被会话引用的版本化patch。
- 部署源码/镜像标签与摘要、原生版本、systemd unit和Compose文件。

备份含凭据，应限制为管理员可读。若使用本指南之外的既有Agent home或项目目录，也要纳入备份范围。

SQLite使用WAL。在线备份单个数据库请用仓库工具，不能只复制一个正在使用的`.db`文件：

```sh
python3 script/agent_db_backup.py SOURCE_DATABASE NEW_BACKUP_DATABASE
```

该工具拒绝覆盖已有目标，并执行integrity_check。它保证单个SQLite快照，不保证ChatRaw、Runner及原生文件树之间的统一时点。

需要可协调回退的完整备份时，在维护窗口阻止新请求、核实任务，再停止ChatRaw、Runner和**由本部署管理的**Hermes Gateway。确认无文件写入后备份两侧数据库和完整目录。若仍有无法核实的unknown，可先保留只读快照和证据，但不能把它称为已验证的一致恢复点，也不要清账后继续。

ChatRaw数据库位置为卷内 `chatraw.db`，Runner为 `/var/lib/chatraw-runner/runner.db`。可用以下命令定位实际卷，不依赖猜测宿主路径：

```sh
docker volume inspect chatraw_chatraw_data --format '{{.Mountpoint}}'
```

原生Agent会话文件和Hermes自身数据库同样需要备份；只保存ChatRaw消息不能恢复原生上下文。

### 回退与重新启动

先保留当前数据副本，核实并停止相关写入，再恢复一套匹配的代码、数据库和原生文件。不要把较新数据库直接交给旧代码，也不要执行破坏性的反向schema修改。首次Agent数据库迁移可能生成迁移前备份，但它不包含之后的新消息，不能代替日常备份。

恢复后先启动必要的原生Gateway和Runner，再启动同一项目名/数据卷的ChatRaw。检查 `/ready`、原聊天消息、Agent绑定和原生会话身份，再在维护窗口内验证续接。遇到unknown继续保留隔离，原工具对外部系统造成的效果需要单独核实。

已验证具体服务重启及一次空闲状态整机正常重启，五Agent会话均可恢复；不承诺强制断电后所有任务无缝继续。

## 浏览器与设备验证

本次已在 macOS 上使用实际 Chromium 109.0.5414.46、Chrome 157 和 Playwright Firefox 150.0.2 引擎验证核心界面，并在 RM-01 部署上复验。Firefox 和 Chromium 109 的横屏菜单、键盘焦点、减少动效、历史回放及原文复制已通过。参见[现场浏览器记录](../docs/agent-platform/handoffs/E/field/README.md)及[横屏修复复验](../docs/agent-platform/handoffs/E/field/menu-fix/README.md)。

不支持 IE。上述结果不是 Windows 8 实机、旧版 Firefox ESR 115 或手机软键盘实测；手机实机检查按用户安排暂缓。刷新页面可加载本次带版本号的新前端资源。
