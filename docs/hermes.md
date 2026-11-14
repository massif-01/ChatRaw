# Hermes in ChatRaw

Hermes now uses the unified host Agent Runner and its native canonical Gateway.
ChatRaw remains the same-origin UI and display store; Hermes owns its context,
working directory, native session, tools and authentication.

## Existing installations

Existing chat text, plugin settings and the `hermes` / `hermes-session-key`
secret-store entries are retained. The former `/api/hermes/chat`, health and
approval routes return **410 Gone**. Their execution loop and active-run map have
been removed from production code; there is one Runner state machine.

Old HTTP base URLs, API modes and API keys are not native Gateway identities.
They are not silently reused for another target. Configure the Runner account's
Hermes Gateway, save the new non-secret settings, and create a new Agent chat.
Existing chats do not have reliable native binding metadata, so ChatRaw never
resends their history to pretend it restored an Agent session.

## Setup and behavior

1. Prepare the actual native Hermes installation and authentication under the
   same host account as Runner. Start its Gateway through the normal native
   operator workflow.
2. Configure the host executable/home using the deployment instructions. Runner
   uses `hermes gateway attach --json`, without starting or stopping that service.
3. Install and enable the bundled Hermes plugin, check its availability, then bind
   a new chat to a managed workspace or an administrator-listed project.
4. Model, provider and reasoning are editable non-secret settings. An empty or
   omitted value uses native defaults. A running task retains its snapshot;
   updated settings apply when the idle native session is resumed for the next run.

ChatRaw sends only the current input and supported attachments. Native slash and
Skill handling stays with Hermes. Closing a browser does not stop the run; use the
explicit stop action. Approval selection is not submission. A lost connection is
not successful completion and can leave the session awaiting verification.

See [host and Docker deployment](../deploy/README.md),
[protocol/limitations](../agent_runner/adapters/hermes.md), and
[the unified contract](agent-platform/CONTRACT.md).

## 中文迁移说明

旧聊天、插件资料和独立密钥记录保留。旧Hermes专属执行入口返回410，生产代码已移除
旧执行循环和活动状态集合。新的统一Runner负责状态、交互、持久化和恢复。

旧HTTP服务配置不能直接当作原生Gateway身份。请按部署说明配置实际运行账户和Gateway，
保存新的非秘密参数后创建Agent聊天。系统不会重发旧聊天历史来伪装原生会话恢复。

网页关闭不停止任务；显式停止仍需原生结束证据。无法确认时保持unknown，先核实再继续。
模型目录和协议握手通过不等于真实模型认证通过，现场验收需另行记录。
