# E：前端资源本地化与 Chrome 109

模型 gpt-6.1-sol，thinking high。普通模式，按批次完成。

读 /Users/massif/ChatRaw/docs/agent-platform/{PLAN,CONTRACT,ACCEPTANCE}.md，自己工作树可写，主目录只读。

第一批直接实施：将当前Alpine3.13.3、collapse3.13.3、marked9.1.6、highlight11.9.0所需脚本语言包样式及官方插件前端依赖核实并本地化；固定版本/校验/许可证，添加可复现构建与Chrome109检查。不要顺便升级所有库或迁移框架。

拥有static/vendor、前端package/lock、构建/兼容脚本及文档。index.html/app.js等入口由B拥有：第一批提交可直接应用的精确patch（存docs/agent-platform/handoffs/E/）和接线说明，供总控/B合入，不在本分支改这些公共入口；现有plugin依赖接线同理。压缩产物由总控统一生成。

确认是否能获得真实Chrome109浏览器用于隔离测试；用户没有授权安装未知来源的浏览器。只从官方可验证来源准备，真实版本证据不能用UA替代。可用现代浏览器先阻断外部CDN做离线UI检查，但不得据此称Chrome109通过。

验收覆盖UI依赖不是业务API。避免为某个极少用第三方插件无限拓展本地化范围，先完整清点并区分必要/可选资源。IE仅不支持提示，Firefox115不强制。

交付资源/构建配置/入口patch、许可证、验证报告、兼容缺口、branch/commit。提交前final-pr-commit；不push/部署。待总控下一批任务再对集成版做109验证。
