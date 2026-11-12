# RM-01 Docker 与 Compose 安装验证

2026-11-12，应用户要求在 `10.10.99.99` 安装 Docker 和 Compose。此前用户明确要求删除的 Podman 已移除；本次没有安装 Agent 或部署 ChatRaw。

## 安装结果

- Ubuntu 24.04.4 LTS、amd64；采用 [Docker 官方 Ubuntu 软件仓库](https://docs.docker.com/engine/install/ubuntu/)，APT 校验仓库签名与软件包。新增 `containerd.io`、`docker-ce-cli`、`docker-ce`、`docker-buildx-plugin`、`docker-compose-plugin`；没有移除或升级其他软件包。
- Docker Engine/CLI **29.9.3**，Compose **5.7.1**，Buildx **0.39.0**。`docker.service` 和 `containerd.service` 均为 active、enabled。
- `rm01` 加入 `docker` 组，保留原有组；用全新 SSH 会话验证无需 `sudo` 即可访问 Docker。旧登录会话需要重新登录才能获得新组。该组具有 Docker 管理权限，等同 root 级别权限，见 [Docker 官方说明](https://docs.docker.com/engine/install/linux-postinstall/)。
- 系统预有 `/usr/bin/docker-compose` 1.29.2，在实际运行中出现事件线程兼容异常。保留该软件包，在此前不存在的 `/usr/local/bin/docker-compose` 创建指向官方插件的兼容链接；普通 PATH 下的 `docker compose` 和 `docker-compose` 均为 5.7.1。显式调用 `/usr/bin/docker-compose` 仍会运行旧版。
- 官方仓库配置位于 `/etc/apt/sources.list.d/docker.sources`，公钥位于 `/etc/apt/keyrings/docker.asc`。用户打开网络后，Docker 和 Ubuntu 官方源均可直连；安装前临时使用的本地 SSH 转发已撤销，没有持久代理或 DNS 配置变更。

## 接收端验证

- 真实 `docker compose up` 从 Docker Hub 拉取 amd64 `hello-world`，创建并运行容器，退出码为 0；兼容命令 `docker-compose` 指向新版后也完成相同运行。测试使用独立临时客户端配置和 `network_mode: none`，测试容器与镜像已删除；复核当前容器、镜像和命名卷均为空。
- 在 RM-01 上用真实 Compose 5.7.1 解析现有 ChatRaw 基础配置、Agent overlay 和本地预构建镜像 overlay，验证 image、host 网络、固定名称的数据卷和只读 token 挂载；只解析配置，没有启动应用。
- 安装前后的 TTO 59090/59009、NFS 2049 与 SMB 445/139 端口仍由相同服务监听；59009 首页返回 HTTP 200，smbd/nfs-server 为 active。59090 根路径返回 404，但进程和端口仍在；本次未对 TTO 采集或共享文件操作做完整功能测试。
- 原有 iptables FORWARD 规则内容及相对顺序保留；Docker 在其前增加 Docker 自有链。现有局域网路由保留，新增 Docker 默认 `172.17.0.0/16` 桥接路由。

## 仍待完成

Docker 和 Compose 本身已安装并验证。五个 Agent 的宿主运行环境、ChatRaw 容器部署、真实模型认证、手机实机和整机重启仍未执行；用户此次指令仅要求先安装 Docker 与 Compose。
