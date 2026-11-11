# 集成验收进度

2026-11-12，总控完整集成源码 `165a509`（`2d770f0`＋标题与Claude问答增量）。本地已知P0/P1已清零；现场门槛仍未关闭，不是全项目发布通过声明。
`simulated_pass` 包括真实浏览器/原生程序配合受控 API 或模型替身；真实引擎证据与真实模型服务认证分开记录。

|门槛|阶段状态|已有证据|仍需完成|
|---|---|---|---|
|G01 插件|simulated_pass|B 五插件安装/设置/启停/卸载及聊天单选，真实 109/157＋API fixture；总控集成树157复验通过|最终网关的真实安装与配置链路|
|G02 会话|simulated_pass|五款原生程序＋本地模型替身；C/D续接，F独立验证Pi/DeepSeek全新实例和聊天隔离，D验证Hermes真实Gateway|最终Runner持久映射、RM-01账户与真实模型|
|G03 上下文|simulated_pass|B输入只含本轮内容/附件引用；C真实Claude请求保留原生CLAUDE.md/Skill，不含ChatRaw哨兵|最终网关与五适配器完整链路|
|G04 状态|simulated_pass|公共合同及叶模块EOF/错run/replay反例；B断线与丢失接收响应fixture|最终Runner权威状态和恢复|
|G05 交互|simulated_pass|C-F02与F-PLAT-01均关闭；真实UI编码→Runner→Claude保留选项与补充文字，无效选项派发前拒绝且允许修正；F定向9项通过|现场原生服务与真实账号流程|
|G06 停止|simulated_pass|Pi/DeepSeek真实shell停止由F复验；Hermes保留Gateway；C-F01修复后F确认Codex无延迟写入，失败保持unknown|最终Runner持久隔离与Linux环境|
|G07 恢复|simulated_pass|F核验Runner子进程突然退出后的真实SQLite/WAL恢复、unknown占位及不重发；ChatRaw组件/数据库重开单次投影；总控容器替换保留数据|RM-01真实运行环境与整机重启单独验证|
|G08 附件|simulated_pass|C/D图片到原生请求或存储；B附件/产物fixture|最终归属、下载、刷新与现场能力声明|
|G09 渲染|real_pass|总控集成树Chrome157实际渲染；B/E真实109测试：稳定DOM、公式/图表、原文复制、reduced motion；原KaTeX停顿问题关闭|正式后端流接线复验，不扩大视觉设计范围|
|G10 手机|simulated_pass|320/375/390/430及横屏截图，模拟visualViewport缩小与焦点检查|iPhone Safari/Android Chrome实际设备和软键盘|
|G11 Chrome109|real_pass|E在最终后端上用实际Chromium109.0.5414.46跑通普通聊天、离线插件、真实网关和跨浏览器审批；Agent端受控|Windows8实机证据单列，不把macOS上的实际109说成Win8实机|
|G12 本地UI资源|real_pass|E最终109/157外部请求尝试为0；本地市场安装、残缺旧插件字体升级、CSV兼容、公式/图表/PDF通过；总控无网络Docker复验|业务模型/搜索API不属于离线保证|
|G13 迁移|simulated_pass|F核验旧记录、旧schema恢复、活动WAL备份、拒绝覆盖；旧Hermes执行已移除|现场数据/文件树一致回退窗口|
|G14 普通聊天|simulated_pass|F固定集成版本153项执行通过、23可选原生跳过；普通压缩/Skill/TLS/字体83项通过；E实际后端普通聊天流通过|真实模型服务和现场环境；跳过不计通过|
|G15 部署|simulated_pass|最终linux/arm64 Docker镜像通过无Runner启动、无网络安装、同卷替换容器的数据保留；主镜像无原生CLI|RM-01 x86_64宿主服务部署、原生持久目录与开机恢复；新环境安装待用户批准|

## 独立审查与可重跑入口

- [D适配器审查](reviews/F-D-round2-20261112.md)：16项原有＋6项独立检查通过，无叶模块集成阻塞。现场门槛保留。
- [C适配器审查](reviews/F-C-round3-20261112.md)发现的C-F01/C-F02已由[独立复验](reviews/F-C-round4-20261112.md)关闭：34项回归＋4项原反例＋5项边界检查通过，未放宽原断言。
- [B界面与脚本](handoffs/B/README.md)、[E资源与浏览器](handoffs/E/README.md)、[真实HermesGateway](handoffs/D-hermes/README.md)。
- [E最终G11/G12报告](reviews/E-2d770f0/REPORT.md)及[总控网关/镜像记录](reviews/integration-2d770f0/README.md)固定到同一集成提交，附截图与原始日志。
- [F完整平台报告](reviews/F-platform-2d770f0-20261112.md)列明7项独立权威层检查与唯一问答P1；[标题增量](reviews/F-title-cb4d9fc-20261112.md)另经5项检查通过。
- [F最终有界结论](reviews/F-platform-final-69a7427-20261112.md)关闭问答P1，本地已审查组合无已知未闭环P0/P1。总控在165a509重跑双浏览器网关与最终Docker持久卷检查通过。
- 总控在集成树运行 `npm run build`、`npm run vendor:check` 通过；指定本机Chrome路径后运行 `scripts/test-agent-ui.mjs` 和 `scripts/test-stream-markdown.mjs` 通过。默认Playwright缓存未安装浏览器，使用 `CHROME_PATH` 指定已安装程序，不以下载失败冒充产品失败。

目前不具备整体发布通过条件。每个门槛以最终提交、实际接收端和明确环境为准；实现者完成、程序安装成功、模型目录可读均不等于真实模型认证通过。
