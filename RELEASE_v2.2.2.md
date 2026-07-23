# ChatRaw v2.2.2

## 新增功能

### Server-owned LinkDB Agent bridge (#45)

- 新增同源 `/api/linkdb-agent/health` 与 `/api/linkdb-agent/chat` 接口。
- Agent URL、API Key、超时与可信 principal 由 ChatRaw Host 持有；浏览器不能注入或覆盖这些传输与身份字段。
- 增加 Origin、请求大小、JSON 结构与字段校验；无效请求不会调用上游。
- 仅在上游成功后原子保存完整对话，避免失败时留下半条会话记录。
- `chatraw-linkdb-agent` 使用新的专用安全边界，其他插件继续沿用现有通用设置、密钥与代理行为。

## 部署说明

升级 Host 前，请先安装配套的新版 LinkDB Agent Plugin，并在服务端配置：

- `CHATRAW_LINKDB_AGENT_ENABLED=true`
- `CHATRAW_LINKDB_AGENT_BASE_URL`
- `CHATRAW_LINKDB_AGENT_API_KEY`
- 可选：`CHATRAW_LINKDB_AGENT_PRINCIPAL`
- 可选：`CHATRAW_LINKDB_AGENT_TIMEOUT_SECONDS`

Docker Hub 提供 `linux/amd64` 与 `linux/arm64` 镜像：

```bash
docker pull massif01/chatraw:2.2.2
```

也可拉取最新版本：

```bash
docker pull massif01/chatraw:latest
```

## 发布边界

本版本发布 ChatRaw Host 与 LinkDB Agent 的工程集成能力。完整链路仍需配套的 LinkDB、Agent 与 Plugin；客户网络、认证、硬件和生产切换需在目标环境完成验收。
