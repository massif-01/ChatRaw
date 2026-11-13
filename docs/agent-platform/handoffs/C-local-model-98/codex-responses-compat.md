# Codex Responses 模板兼容

在 Runner 的宿主配置中，向已有的 `agents.codex` 添加：

```json
{
  "responses_compat_upstream": "http://10.10.99.98:58000/v1/responses"
}
```

省略字段时沿用原生 Codex provider。该字段属于 Runner 宿主配置，插件设置 API 拒绝该字段。启用后，适配器启动私有 app-server，选择专用 provider 并将其请求发到同进程管理的 `127.0.0.1` 临时端口。模型仍可通过现有 `model` 设置选择，留空沿用 Codex 原生模型设置。对 .98 使用 `RM-01 VLM`。继续使用同一 `CODEX_HOME`，保留原生会话、权限和审批策略。部署前由 A 确认目标服务使用无凭据的固定上游地址。

Runner 在绑定时保存宿主配置快照。部署后用新建 managed 会话验收，已有会话继续使用其原快照。

入口仅接受带随机鉴权的 `POST /v1/responses`。它将顶层 `instructions` 与原生 `developer`、`system` 文本按顺序合并到顶层 `instructions`，由 .98 转为唯一首位系统消息。普通消息、工具调用和结果、图片及其它请求字段原样转发。不能合并的指令项返回 400。入口禁用重定向，既有的上游 HTTP 错误和 SSE 响应体直接透传。

入口和连接池随 app-server 释放。令牌只注入该 app-server 的进程环境，普通原生 shell 收到的值为空，上游不接收该令牌。受信宿主账户及其同 UID 进程仍属于同一信任域。入口不记录请求体或访问日志。

本机 Codex 0.153.4 联调使用会拒绝非首位指令的 loopback 模型接收端。验证了原生压缩及同 thread 续接、保留权限说明和早期识别码、真实 shell 工具调用与结果 ID 配对、PNG 出站，以及新 app-server 恢复同一 thread。另验证了拒绝未认证和错误路径请求、非文本指令拒绝、上游 429 和 SSE 透传、禁重定向、流断开与进程退出清理。

```sh
CHATRAW_C_NATIVE_TESTS=1 python -m unittest discover -s agent_runner/tests
```

现场复验需在 F 审查、A 部署后，用 .98 真实模型在新 managed 会话完成写入随机码、原生压缩、同 thread 读回，并复核原生权限、图片和工具路径。本次实现未调用 .98 或修改现场。
