# 任务详情空白修复：现场镜像更新

2026-11-13，派生镜像 `chatraw-agent-integration:2ba163e-ui` 已在 .99 生效。只替换 agents.js 与 index.html，不改后台或已验依赖。原生 DeepSeek patches 尚未部署，Runner/Hermes 未重启。

## 部署门槛

初查发现 D 的 Codex 工具停止 run `e05b8525931c4d1585cae79770c7be3d` 仍为 unknown，错误 codex_tool_stop_unverified，A 据此暂停。总控随后明确允许仅更新 ChatRaw 容器，保留该 unknown，要求无其他执行中任务。部署前再次查询 Runner SQLite，唯一非终态正是该 unknown；用户原 Codex 聊天空闲。未修改 run 状态、取消会话或清理原生进程。

## 操作

总控交付目录 `/Users/massif/ChatRaw/outputs/agent-platform/ui-details-2ba163e` 的三个文件哈希在本机与 .99 均校验通过。宿主交付目录 `/home/rm01/chatraw/ui-details-2ba163e`。

在 .99 用 `docker build --pull=false --network=none` 基于已经核实的 e91d32f 镜像构建；派生镜像 Linux/amd64，保留全部原12层、Env与Cmd，新增前端COPY层。未向旧容器热拷贝作为部署。

活动 overlay `/home/rm01/chatraw/deployment-e91d32f/compose.prebuilt.yml` 已改为新 image tag；旧内容另存 `compose.prebuilt.e91d32f.yml`。旧交付目录 SHA256SUMS 中 compose.prebuilt.yml 的摘要因此属于历史版本，不能再把它当作当前overlay摘要。源码和原镜像归档未修改。

使用原 Compose 项目 chatraw、原基础文件和 Agent overlay，`up -d --no-build --no-deps chatraw` 仅重建主容器。数据卷仍为 chatraw_chatraw_data，token只读挂载未变。

## 验证结果

- `/ready` 返回 ready/database connected。
- 首页与交付 index.html SHA256一致：86bd901644a82b24b4f145d369332da40ddab4e6a16ccd623b148cdbe3068626。
- 首页实际引用 `agents.js?v=2`；`http://10.10.99.99:51111/agents.js?v=2` 返回200，SHA256为5be914c38b03b24a11e349d7fc6150cf702deb6975f602a8258262106196ed85。
- 镜像ID为 sha256:97f9ac18f92decbba43e9f742689c9ef7a1f52ad67d18d3cf31d12c922d1434c，revision label=2ba163e。
- 用户聊天6a5b5091-00be-4bf3-90cf-303160876c4a的12条消息：数量、IDs、完整序列内容哈希均相同；聊天metadata、Agent绑定相同。证据只存哈希和IDs，不另存消息正文。
- 模型配置、普通设置哈希相同，数据卷/凭据挂载相同。
- Runner PID58386、Hermes PID34685保持不变。
- D的unknown run整个API快照相同，未冒充终态。

HTTP初查误用了/static/agents.js路径而收到404；随后依据首页真实script引用检查/agents.js?v=2并通过，不是现场缺失文件。前端交互回归由B/root在交付前完成；A此处验证正式服务交付内容与持久数据，未另发模型请求。

证据：33号为包校验和初始门槛；34号为容器前后快照；35/36为构建和重建日志；37号为HTTP哈希及保留项比较；38-ui-image-proof.json为继承镜像层证明。
