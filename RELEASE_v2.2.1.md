# ChatRaw v2.2.1

## 新增功能

### Skill Manager 插件 (#31)
- 支持从 GitHub URL、本地 `SKILL.md` 和本地 zip 安装 Skills。
- 新增 Skills 管理能力：启用、禁用、删除、预览和安装诊断。
- 聊天输入支持 `/skill-name` 调用和补全，选中的 Skill 由后端注入到本轮模型上下文，不污染用户可见消息。

### Hermes 插件后端路由 (#32)
- 新增 Hermes 路由插件，可将选定聊天请求安全转发到 Hermes API Server。
- 支持 Chat Completions 与 Runs 两种 Hermes 执行模式。
- Hermes API Key、Session Key 和 Base URL 只由 ChatRaw 后端保存和使用，浏览器端不暴露敏感传输信息。

### Hermes Runs 工具事件与审批 (#41)
- Runs 模式支持展示 run 生命周期、工具调用进度、reasoning、失败、取消和完成状态。
- 聊天气泡新增 Hermes Run 区块，工具事件和审批事件不会混入最终 assistant 正文。
- 新增工具审批卡，支持“允许一次”“本会话允许”“拒绝”三种操作。
- Stop generation 可中断 active Hermes run，并清理运行态。
