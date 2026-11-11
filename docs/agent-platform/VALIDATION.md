# 集成验收进度

2026-11-12，总控集成源码至 `62dc389`。这是阶段记录，不是发布通过声明。
`simulated_pass` 包括真实浏览器/原生程序配合受控 API 或模型替身；真实引擎证据与真实模型服务认证分开记录。

|门槛|阶段状态|已有证据|仍需完成|
|---|---|---|---|
|G01 插件|simulated_pass|B 五插件安装/设置/启停/卸载及聊天单选，真实 109/157＋API fixture；总控集成树157复验通过|最终网关的真实安装与配置链路|
|G02 会话|simulated_pass|五款原生程序＋本地模型替身；C/D续接，F独立验证Pi/DeepSeek全新实例和聊天隔离，D验证Hermes真实Gateway|最终Runner持久映射、RM-01账户与真实模型|
|G03 上下文|simulated_pass|B输入只含本轮内容/附件引用；C真实Claude请求保留原生CLAUDE.md/Skill，不含ChatRaw哨兵|最终网关与五适配器完整链路|
|G04 状态|simulated_pass|公共合同及叶模块EOF/错run/replay反例；B断线与丢失接收响应fixture|最终Runner权威状态和恢复|
|G05 交互|simulated_pass|问答/审批已有原生程序证据；C-F02修复后F核对完整长命令及超限/掩码命令拒绝|最终界面回包与真实模型服务|
|G06 停止|simulated_pass|Pi/DeepSeek真实shell停止由F复验；Hermes保留Gateway；C-F01修复后F确认Codex无延迟写入，失败保持unknown|最终Runner持久隔离与Linux环境|
|G07 恢复|not_started|A开发树有持久化测试，尚未作为最终集成结论|浏览器/ChatRaw/Runner/机器逐层验证，unknown不得重发|
|G08 附件|simulated_pass|C/D图片到原生请求或存储；B附件/产物fixture|最终归属、下载、刷新与现场能力声明|
|G09 渲染|real_pass|总控集成树Chrome157实际渲染；B/E真实109测试：稳定DOM、公式/图表、原文复制、reduced motion；原KaTeX停顿问题关闭|正式后端流接线复验，不扩大视觉设计范围|
|G10 手机|simulated_pass|320/375/390/430及横屏截图，模拟visualViewport缩小与焦点检查|iPhone Safari/Android Chrome实际设备和软键盘|
|G11 Chrome109|simulated_pass|实际Chromium109.0.5414.46，非UA伪造；新版界面fixture通过|最终后端关键流程；Windows8实机证据单列|
|G12 本地UI资源|simulated_pass|70项vendor校验；旧基线真实离线验证；新版fixture禁止外部请求|最终本地市场安装、残缺旧插件资源升级、离线启动|
|G13 迁移|not_started|A正清除旧Hermes生产执行实现，保留只读历史/配置|最终数据库迁移、备份与回退演练|
|G14 普通聊天|simulated_pass|B开发基线83项上下文/Skill/TLS/字体检查通过|A/B最终集成普通聊天回归|
|G15 部署|not_started|宿主环境只读核实；Docker主程序＋宿主Runner方案已确定|最终镜像/服务部署、持久目录与开机恢复；新环境安装待用户批准|

## 独立审查与可重跑入口

- [D适配器审查](reviews/F-D-round2-20261112.md)：16项原有＋6项独立检查通过，无叶模块集成阻塞。现场门槛保留。
- [C适配器审查](reviews/F-C-round3-20261112.md)发现的C-F01/C-F02已由[独立复验](reviews/F-C-round4-20261112.md)关闭：34项回归＋4项原反例＋5项边界检查通过，未放宽原断言。
- [B界面与脚本](handoffs/B/README.md)、[E资源与浏览器](handoffs/E/README.md)、[真实HermesGateway](handoffs/D-hermes/README.md)。
- 总控在集成树运行 `npm run build`、`npm run vendor:check` 通过；指定本机Chrome路径后运行 `scripts/test-agent-ui.mjs` 和 `scripts/test-stream-markdown.mjs` 通过。默认Playwright缓存未安装浏览器，使用 `CHROME_PATH` 指定已安装程序，不以下载失败冒充产品失败。

目前不具备整体发布通过条件。每个门槛以最终提交、实际接收端和明确环境为准；实现者完成、程序安装成功、模型目录可读均不等于真实模型认证通过。
