# Security Policy / 安全政策

## Supported Scope / 支持范围

ChatRaw security fixes target the current maintained branch and the latest public release line. The
project does not currently publish a long-term version support matrix.

ChatRaw 的安全修复面向当前维护分支和最新公开发布线。项目目前不维护长期版本支持矩阵。

## Reporting a Vulnerability / 报告漏洞

If you find a vulnerability, please use GitHub Security Advisories when available. If that is not
available, open a GitHub issue with minimal public detail and ask for a private contact path.

Please include:

- Affected ChatRaw version or commit.
- Whether the issue affects the web app, backend API, plugin runtime, local data directory, or packaged app.
- Reproduction steps with minimal sensitive data.
- Expected impact and any known workaround.

如果你发现漏洞，请优先使用 GitHub Security Advisories。如果不可用，请在 GitHub issue 中只公开最少细节，
并请求私下沟通渠道。

请提供：

- 受影响的 ChatRaw 版本或 commit。
- 问题影响范围：Web app、后端 API、插件 runtime、本地数据目录或打包应用。
- 使用最少敏感数据的复现步骤。
- 预期影响和已知规避方式。

## Plugins and Skills / 插件与 Skills

Plugins and Agent Skills are user-enabled local extensions. Treat third-party plugin code and skill
instructions as untrusted until you review their source.

插件和 Agent Skills 都是由用户启用的本地扩展。在审查来源前，请将第三方插件代码和 skill 指令视为不可信内容。

ChatRaw v1 security boundaries:

- Skill activation is explicit. There is no implicit skill matching by default.
- Skill Manager must be installed and enabled before active skills can be injected into chat requests.
- Disabled skills cannot be activated, even when marked `trusted`.
- Skill `scripts/` files are stored only as reference resources and are not executed by ChatRaw.
- `allowed-tools` in `SKILL.md` does not grant runtime permissions in ChatRaw v1.
- `trusted` is metadata for governance and future matching behavior. It does not bypass current checks.
- Skill resources are summarized by safe relative path; resource file contents are not read into chat automatically.

ChatRaw v1 的安全边界：

- Skill 必须显式激活。默认不做隐式 skill 匹配。
- 必须安装并启用 Skill 管理器后，active skills 才能注入聊天请求。
- 已禁用的 skills 不能被激活，即使标记为 `trusted`。
- Skill `scripts/` 文件只作为参考资源保存，ChatRaw 不会执行它们。
- `SKILL.md` 中的 `allowed-tools` 不会在 ChatRaw v1 中授予运行时权限。
- `trusted` 是治理和未来匹配行为的元数据，不会绕过当前检查。
- Skill 资源只摘要安全相对路径，资源文件内容不会自动读入聊天。

## Local Data / 本地数据

ChatRaw stores settings, chats, plugins, skills, and indexes under the configured `DATA_DIR`. Protect this
directory like application data. Do not share it publicly if it contains API keys, private chats, private
documents, installed plugins, or installed skills.

ChatRaw 会在配置的 `DATA_DIR` 下保存设置、聊天、插件、skills 和索引。请像保护应用数据一样保护该目录。
如果其中包含 API keys、私有聊天、私有文档、已安装插件或已安装 skills，请不要公开分享。

## Operational Guidance / 运行建议

- Install plugins and skills only from sources you trust.
- Review Skill Manager diagnostics before enabling or trusting a skill.
- Keep API keys scoped to the minimum provider permissions needed.
- Avoid exposing a local ChatRaw backend to untrusted networks.
- Keep backups of important local data before testing third-party extensions.

- 只从可信来源安装插件和 skills。
- 启用或信任 skill 前先查看 Skill 管理器诊断信息。
- API keys 应尽量使用最小权限范围。
- 不要把本地 ChatRaw 后端暴露给不可信网络。
- 测试第三方扩展前，请备份重要本地数据。
