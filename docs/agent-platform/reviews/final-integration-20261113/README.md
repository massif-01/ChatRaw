# 最终组合核验

运行代码冻结在 adeb279（含 Codex 和 DeepSeek 最后修复），菜单源在03d35e5，压缩构建产物在f3edd81。现场最终镜像为 `chatraw-agent-integration:adeb279-final-ui`，运行文件和六个实际HTTP资产均逐项核对。后续提交只更新验证脚本/文档/证据。

## 本地与浏览器

[manifest.json](manifest.json)记录8组后端回归及Runner测试：169执行通过，29可选原生skip。初始本地环境缺依赖的失败及解释器调整已在清单说明；没有通过降低断言掩盖产品失败。`npm run build`、`npm run vendor:check`和CI YAML接线检查通过。GitHub Actions未运行/未推送，不能据此声明远端CI绿色。

[最终Firefox/109现场复验](../../handoffs/E/field/menu-fix/README.md)保留原横屏失败与修复后截图、真实版本、焦点/减少动效/原文复制和零外部请求/写入/浏览器错误证据。

## 独立审查与现场

C兼容与D审批增量分别通过[F Codex审查](../F-codex-responses-3bcb6a2-20261113.md)及[F DeepSeek审查](../F-deepseek-approval-ee1aef5-20261113.md)。F在总控收到最终现场81–83及E复验后给出有界结论：软件实现、部署及限定审查可交付，但不能标记全现场验收通过；未发现新增适配器P0/P1证据。该结论来自F对话 `01a1cc3e-9cc1-71b3-a6c1-ea33f770bf8a`，turn `01a1d594-4b37-7971-9f85-b5ec0e92ed43`，未重新调用现场模型。

[最终现场报告](../../../../handoff/rm01-deployment-20261113/81-final-combined-field-report.md)证明Codex原生压缩后同thread续接、工具与图片；两Agent工具停止见各自归档。受限备份、隔离副本与必要维护窗口内静止双库核对见[恢复报告](../../../../handoff/rm01-deployment-20261113/66-isolated-restore-report.md)。未对生产执行恢复或整机重启。

## 保留门槛

- G05的DeepSeek新公开审批：代码和原生SDK通过，当前.98模型三轮没有形成有效公开审批，拒绝/允许端到端为NOT_VERIFIED。停止有界重试，失败原文保留。
- G07整机重启：必须再次确认，尚未执行；组件重启和隔离副本检查不能替代。
- G10手机实机：用户明确暂缓；布局模拟不等于真实软键盘。
- 旧Codex unknown与旧宿主快照保持隔离。新宿主配置用于新绑定，不将新会话通过冒充旧会话迁移。

[总验收清单](../../VALIDATION.md)是当前状态入口。

## 2026-11-14追加证据

用户随后明确授权整机重启，G07已由[重启核验](../reboot-20261114/README.md)补齐正常重启范围。上文“尚未执行整机重启”为本报告原时间点的记录。G05当前模型审批补项、G10手机暂缓仍保留。软件运行字节没有因本次验收变更。
