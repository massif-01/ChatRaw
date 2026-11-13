# DeepSeek .99 现场接线阻塞（2026-11-13）

ChatRaw e91d32f → Runner → SDK/runtime 0.2.2rc2 → .98 `RM-01 VLM` 首轮失败，run `df3c329ec4db425c892bacd448570491`。Codex、Claude、Pi、Hermes 的同类工具回合均完成。

原生记录 `request/header` 的 config 是 `provider=deepseek-official, model=RM-01 VLM, maxTokens=256000, reasoningEffort=high`。最终 `turn/end` 为 CONTEXT_WINDOW_EXCEEDED：262144 上限，256000 输出预留 + 6145 输入 = 262145。首次超限后原生自动压缩，再次请求仍超限。不能将压缩摘要中的“已完成工具”文字当工具执行证据；当前没有 ChatRaw 工具完成事件。

安装的官方 SDK `deepseek_harness/api.py` 中 HarnessConfig 已支持 `max_tokens: int | None`，启动 session 时透传到 client `maxTokens`。当前 D adapter `_make_harness` 仅透传 model/reasoning_effort。需要 D 线最小补齐可配置的 max_tokens 透传与校验，并现场设置适配本地模型的输出预算（如8192）；不要改 .98，不加协议代理，不硬编码模型名或把未完成记为成功。

现场原生记录：`/var/lib/chatraw-runner/deepseek/session-2c63be8b22744b3cb0c81413a51f6aad/sessions/--var-lib-chatraw-runner-workspaces-14d1c7a3dbda4f3fad1a20a4b35d523f--/session-2c63be8b22744b3cb0c81413a51f6aad/session.v4.jsonl.zstd`。可用项目 Hermes Python 3.14 的 compression.zstd 只读解析。

A 保持现场所有权，等待可审查的 D 修复文件/提交后更新 Runner 并重测。若 max_tokens 是宿主字段，旧会话冻结宿主快照不应被静默改写，创建新验收会话；若为公共设置，走原有 settings 流程。
