# RM-01 部署产物准备

2026-11-12，固定源码 `e91d32f3674389be2c94c3a939c6a4179246e4c2`，工作树构建前干净。
这是本机交付产物验证；现场安装审批、账号认证、手机和整机重启门槛不变。

## Linux x86_64 主镜像

```sh
docker build --platform linux/amd64 -t chatraw-agent-integration:e91d32f-amd64 .
DOCKER_DEFAULT_PLATFORM=linux/amd64 python3 scripts/test-docker-persistence.py \
  --image chatraw-agent-integration:e91d32f-amd64 \
  --report outputs/agent-platform/deployment-e91d32f/docker-amd64.json
```

构建通过，镜像为 `sha256:faeb75dc86eb10583fa0af6a800e3c630247e2a193d7c7f2cd232d48162a45a9`。
本机 arm64 通过 OrbStack 运行 amd64 容器，Python 3.11.18；实际包版本见 [runtime.json](runtime.json)。
首次 registry 令牌请求遇到 EOF；单独拉取官方基础镜像成功后构建通过，没有改变仓库 Dockerfile。

`--network none` 下通过：无 Runner 启动、前端文件逐字节比对、五 Agent 插件和 Markdown
增强插件完整安装、嵌套字体读取、移除容器后同卷重建保留聊天 ID 与插件、原生 CLI 未进入主镜像。
详见 [docker-amd64.json](docker-amd64.json)。这不是 RM-01 实机、宿主 Runner 或 Linux 原生工具停止验收。

## 固定交付包

本地目录：`outputs/agent-platform/deployment-e91d32f/`。

- `ChatRaw-e91d32f.tar.gz`：20,632,816 字节，340 个版本管理文件；已核对 Docker、部署、五适配器、五插件和构建产物入口，无运行数据目录。
- `ChatRaw-e91d32f-linux-amd64.docker.tar.gz`：200,049,612 字节；导出实际受测镜像。
- `compose.prebuilt.yml`：固定该镜像标签，`pull_policy: never`；配合 `--no-build` 使用受测产物。
- `README.md`：校验、装载及现场获准后的部署顺序，固定 Compose 项目名以保持升级的数据卷归属。
- `SHA256SUMS`：以上四个文件的摘要。

归档内的 Docker manifest/config 再次核对了镜像 ID、`linux/amd64` 和目标标签；源码包核对了
五个原生适配器与五个插件清单。镜像与源码摘要见 [deployment-manifest.json](deployment-manifest.json)。
大体积产物留在本地输出目录，未推送、上传或在 RM-01 装载。

组合 Compose 仅执行配置解析，确认预构建镜像、Agent token 挂载及固定项目名配置有效；
没有执行宿主安装、原生 Agent 安装、远程配置变更或启动现场服务。
