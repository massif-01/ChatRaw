# C：Codex 与 Claude 适配器

模型 gpt-6.1-sol，thinking xhigh。合同冻结且base.py可用后目标模式。

读 /Users/massif/ChatRaw/docs/agent-platform/{PLAN,CONTRACT,ACCEPTANCE}.md 和A发布公共骨架。只写自己的工作树中agent_runner/adapters/codex.py、claude.py及对应tests/docs。公共base/DB/网关/依赖变更提交建议给总控/A。

实施Codex app-server和Claude官方Agent SDK路径。开始前核对当前官方文档、安装版本与签名；Codex使用OpenAI Docs技能。文本/工具/问答/审批/停止/恢复/压缩/附件按真实能力声明。

认证不得假设个人订阅CLI登录可以用于任意第三方SDK产品；明确支持的路径和缺失信息。原生事件EOF不能完成任务，Claude interrupt后旧消息正确排空，Codex审批request id与session/turn严格绑定。不自行暴露WebSocket端口，不自动批准。

运行时读事件与respond/cancel必须并发可达。进程由Runner控制，adapter不自己保存第二套公共状态。停止只影响本任务/会话拥有的资源。

先完成确定性协议测试和实现，再由总控安排RM01真实验证窗口；不能因缺认证停掉全部本地实现，也不能把fake算成实测。不自行安装/升级用户Agent、不读出/打印凭据、不改用户配置。

交付两adapter、能力矩阵、错误/中断/审批反例、版本/认证说明、branch/commit、真实测试边界；提交前final-pr-commit。不push/部署。重大缺口报告总控，不无界研究第三方所有功能。
