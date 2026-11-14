# 手机布局修复部署回执

2026-11-14 23:00:05（北京时间），前端提交 `fcc75bece38a06607b83d703f59bc9509f193cc7` 的 v8.2 已上线，可刷新 iPhone Safari 继续实机验收。

- 以现有镜像为基底，仅替换 `backend/static/index.html`、`styles.css`、`styles.min.css`，持久化为 `chatraw-agent-integration:fcc75be-phone-v82`；仅重建 ChatRaw Web。
- 三个容器内文件与实际 HTTP 返回均匹配提交 SHA-256，`/ready` 返回200。详见 [manifest.json](manifest.json)。
- Runner/Hermes保持运行，PID分别保持3424/1378；boot ID、数据卷、挂载、运行配置、模型设置、Agent绑定和插件配置均保持。
- 切换前后均无排队、运行或待审批任务，仅保留原有1条unknown，未清理或重发。没有模型请求，没有重启Runner、Hermes或整机。
- 原镜像 `chatraw-agent-integration:adeb279-final-ui` 保留；需要回退时恢复该镜像标签并仅重建Web。此次没有执行回退。

发布前的WebKit、Chromium109和Firefox手机布局回归由总控完成；本回执证明现场部署及资产一致性，不代替用户的iPhone15Pro Safari实机复验结果。
