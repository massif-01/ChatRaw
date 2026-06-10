# Agent Skills in ChatRaw / ChatRaw 中的 Agent Skills

## English

Agent Skills are reusable instruction packages stored as `SKILL.md` files. In ChatRaw, skills are
installed locally, listed through the Skill Manager plugin, and activated explicitly for a single chat
turn with `/skill-name`.

### How Skills Are Loaded

ChatRaw uses progressive disclosure:

- `GET /api/skills` reads only the local skill catalog metadata.
- Skill details show status, source, diagnostics, and a resource summary.
- After installation, list and detail views do not read the full `SKILL.md`; the body is read during
  install validation, preview, or explicit chat activation.
- Resource folders (`scripts/`, `references/`, `assets/`) are summarized by safe relative path only.

The catalog stores enablement, trust metadata, source information, timestamps, license data, and diagnostics.
`SKILL.md` remains the source of truth for the actual instruction body.

### Install Skill Manager

1. Open **Plugins** from the bottom-left button.
2. Install **Skill Manager** from the Plugin Market.
3. Enable the plugin in the **Installed** tab.

When Skill Manager is disabled or not installed, `/skill-name` suggestions are unavailable and chat
requests with active skills are rejected by the backend.

### Install Skills

Skill Manager supports:

- GitHub repository URLs and `owner/repo` shorthand when the repository resolves to exactly one skill.
- GitHub raw or blob URLs that point directly to `SKILL.md`.
- Public GitHub tree URLs for a specific skill directory.
- Local `SKILL.md` uploads.
- Local `.zip` packages whose root, or one wrapper directory, contains `SKILL.md`.

For repository roots, ChatRaw resolves a root `SKILL.md` first, then a single `skills/<name>/SKILL.md`.
Repositories with multiple skills must use a tree URL to a specific skill directory. GitHub installs also
record `license` from `SKILL.md` frontmatter or the repository license API when available.

GitHub install is intentionally conservative. Ambiguous repositories, private repos, path traversal,
multiple possible skills, missing `name`, missing `description`, invalid names, oversize files, and
disallowed package paths are rejected by the backend.

You can also install a GitHub skill from chat with a clear command and a single URL:

```text
install this skill https://github.com/example/repo/blob/main/my-skill/SKILL.md
```

```text
安装这个 skill https://github.com/example/repo/tree/main/my-skill
```

Chat install does not send the message to the model. The Skill Manager plugin intercepts the command,
calls the backend install API, and inserts a local result message.

### Use Skills in Chat

Type `/` at the beginning of a token and choose a skill suggestion. ChatRaw keeps `/skill-name` inline in
the composer, highlights known skill tokens, and treats them as explicit activations for the next request.
Backspace/Delete removes a whole skill token at once, and each request can activate up to five distinct
skills. The suggestion menu displays at most five rows at once and scrolls for additional matches.

The backend injects the selected `SKILL.md` content into system context for that request only. The visible
user message, assistant message, and compaction summary do not store the skill body.

### Safety Boundaries

- Skills are third-party instruction content. Review the source before enabling or trusting a skill.
- ChatRaw never executes files in `scripts/`.
- `references/` and `assets/` are not read into chat automatically; only safe paths are summarized.
- `allowed-tools` is parsed as unsupported frontmatter and does not grant permissions.
- `compatibility` is ignored and is not stored or displayed.
- `trusted` is governance metadata only. It does not bypass Skill Manager, disabled-skill checks, or
  explicit `/skill-name` activation.
- No implicit skill matching is currently performed.

### Troubleshooting

- **No slash suggestions**: confirm Skill Manager is installed and enabled, then refresh the skills list.
- **Skill is not injected**: confirm the skill is enabled and the inline `/skill-name` token is present before sending.
- **Install rejected**: check `name`, `description`, file size, package paths, and whether the GitHub URL resolves to exactly one skill.
- **Duplicate skill**: enable overwrite in Skill Manager and retry.
- **GitHub repository is ambiguous**: use a raw/blob `SKILL.md` URL or a specific tree URL.
- **HTML appears in preview**: preview is plain text; HTML-like content is not rendered.

## 中文

Agent Skills 是以 `SKILL.md` 保存的可复用指令包。在 ChatRaw 中，skills 安装到本地，
通过 Skill 管理器插件查看，并且只通过 `/skill-name` 在单轮聊天中显式激活。

### 加载方式

ChatRaw 使用渐进披露：

- `GET /api/skills` 只读取本地 catalog metadata。
- 详情页展示状态、来源、诊断和资源摘要。
- 安装完成后，列表和详情视图不会读取完整 `SKILL.md`；正文只在安装校验、预览或显式激活聊天时读取。
- 资源目录（`scripts/`、`references/`、`assets/`）只列安全相对路径。

Catalog 保存启用状态、trust 元数据、来源、时间戳、许可证信息和诊断信息。真正的指令正文仍以
`SKILL.md` 为准。

### 安装 Skill 管理器

1. 点击左下角 **Plugins**。
2. 在插件市场安装 **Skill Manager / Skill 管理器**。
3. 在 **Installed / 已安装** 标签页启用插件。

如果 Skill 管理器未安装或已禁用，`/skill-name` 不会出现建议，带 active skills 的聊天请求也会被后端拒绝。

### 安装 Skills

Skill 管理器支持：

- 能唯一解析到一个 skill 的 GitHub 仓库 URL 和 `owner/repo` 简写。
- 指向 `SKILL.md` 的 GitHub raw 或 blob URL。
- 指向具体 skill 目录的公开 GitHub tree URL。
- 本地 `SKILL.md` 上传。
- 根目录或一层外包目录包含 `SKILL.md` 的本地 `.zip` 包。

对于仓库根目录，ChatRaw 会先解析根目录 `SKILL.md`，再解析单个 `skills/<name>/SKILL.md`。
包含多个 skills 的仓库必须使用指向具体 skill 目录的 tree URL。GitHub 安装还会在可用时记录
`SKILL.md` frontmatter 或仓库许可证 API 中的 `license`。

GitHub 安装是保守的。模糊仓库、私有仓库、路径穿越、多个可能的 skills、缺少 `name`、缺少
`description`、非法名称、超大文件和不允许的包路径都会被后端拒绝。

也可以在聊天中用明确命令和唯一 URL 安装 GitHub skill：

```text
install this skill https://github.com/example/repo/blob/main/my-skill/SKILL.md
```

```text
安装这个 skill https://github.com/example/repo/tree/main/my-skill
```

聊天安装不会发送给模型。Skill 管理器插件会拦截命令，调用后端安装 API，并插入本地结果消息。

### 在聊天中使用 Skills

在 token 开头输入 `/` 并选择 skill 建议。ChatRaw 会把 `/skill-name` 保留在输入框文本中，
对已知 skill token 做内联高亮，并将它们视为下一次请求的显式激活。Backspace/Delete 会一次删除
整个 skill token，每次请求最多激活 5 个不同 skills。建议菜单最多同时显示 5 行，更多匹配项通过滚动查看。

后端会把选中的 `SKILL.md` 内容注入本轮请求的 system context。可见用户消息、助手消息和压缩摘要不会保存
skill 正文。

### 安全边界

- Skills 是第三方指令内容。启用或信任前请检查来源。
- ChatRaw 永远不会执行 `scripts/` 中的文件。
- `references/` 和 `assets/` 不会自动读入聊天，只会摘要安全路径。
- `allowed-tools` 会作为不支持的 frontmatter 处理，不会授予权限。
- `compatibility` 会被忽略，不再保存或展示。
- `trusted` 只是治理元数据，不会绕过 Skill 管理器、禁用状态检查或显式 `/skill-name` 调用。
- 当前不做隐式 skill 匹配。

### 排错

- **没有 slash 建议**：确认 Skill 管理器已安装并启用，然后刷新 skills 列表。
- **Skill 没有注入**：确认该 skill 已启用，并且发送前输入框中存在内联 `/skill-name` token。
- **安装被拒绝**：检查 `name`、`description`、文件大小、包路径，以及 GitHub URL 是否能唯一解析到一个 skill。
- **重复 skill**：在 Skill 管理器中启用 overwrite 后重试。
- **GitHub 仓库模糊**：改用 raw/blob `SKILL.md` URL，或使用具体 tree URL。
- **预览中出现 HTML**：预览是纯文本，HTML-like 内容不会被渲染。
