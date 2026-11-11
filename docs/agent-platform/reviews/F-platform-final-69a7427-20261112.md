# F：本地完整平台有界验收结论

**F-PLAT-01 已关闭。在 `2d770f0`＋标题增量 `cb4d9fc`＋问答修复 `69a7427` 的已审查组合内，没有已知未闭环的 P0/P1。本地集成可放行，尚不能宣告全项目交付完成。**

## 本轮固定范围

- 基线：`2d770f0e079652d2dc99b49124d60f3305c8c393`。
- 标题增量：`cb4d9fc786d3284bcaebaadfb1d670d49f931315`，此前 [5 项定向验证通过](F-title-cb4d9fc-20261112.md)。
- 问答修复：`69a7427f620760d1c33c025d7bfcb66056ea00fc`，只涉及 Claude adapter、对应原生测试及说明，没有改 A 公共回复交易框架。
- 新快照：`/private/tmp/chatraw-f-final-69a7427.Jwgg3Z`，按上述组合核验 **297 个普通文件，零意外变化**。原 `2d770f0` 快照及失败证据保留。

## F-PLAT-01 闭环证据

两个原反例脚本未修改、未放宽预期：

|验证|结果|
|---|---|
|真实 UI 编码函数＋Runner SQLite＋实际 Claude 答案编码器|原先 unknown 改为 accepted；原生接收端获得 `["Small", "Custom size"]`。|
|真实 UI 编码函数＋Runner＋Claude SDK/CLI＋本地模型替身|回复 accepted，查询正常完成；后续模型请求包含选项与自定义文字，不再留下不可回答的交互。|
|相关原生单选/多选＋补充文字、批次问答回归|原生工具结果保留 Blue 与补充说明，以及 Small/Large/Custom size；无工具错误。|
|公共交互验证回归|批次、过期格式、取消精确匹配及错误选项等反例继续通过。|
|F 新增无效回复修正检查|不存在的 option_id 在 dispatch 前返回 400；SQLite 仍为 `pending, reply=NULL, receipt=NULL`，原生零调用；修正为合法选项＋文字后 accepted，重复同回复不再派发。|

本轮 **9/9 定向验证通过**，没有重跑全量或新增第三方功能审计。解释器仍为 A 的 Python 3.12.4 和 C 的 Python 3.14.2；原生版本为 Claude Agent SDK 0.2.180 / Claude Code 2.1.321，模型端是 loopback fixture。

证据：[合同反例](platform-69a7427-evidence/question-contract.log)、[真实原生反例](platform-69a7427-evidence/native-question-contract.log)、[6项相关回归](platform-69a7427-evidence/related-regression.log)、[无效回复修正](platform-69a7427-evidence/invalid-reply.log)、[输入与计数清单](platform-69a7427-evidence/manifest.json)。

## 汇总放行范围

- [固定基线权威层报告](F-platform-2d770f0-20261112.md)：153 项执行通过、23 项可选原生 skip；F 的竞态、丢失响应、单次投影、崩溃后 unknown、附件/产物归属和 WAL 备份七项检查通过。
- [C 停止与完整审批复验](F-C-round4-20261112.md)：C-F01/C-F02 已关闭，相关43项通过；D 线此前无独立审查阻塞。
- 标题增量已通过，当前唯一新增跨组件 P1（F-PLAT-01）也已关闭。G05 的本地合同与原生问答子范围现可通过；不将所有 Gate 自动提升为完整 real_pass。

E 的真实 Chrome109/157、离线外部请求0及总控的双浏览器、Docker断网/同卷持久性证据由各 owner 汇总，本轮未重复执行。原生程序＋模型替身不能替代五种真实服务账号认证。

未获现场安装批准、真实模型凭据、手机 Safari/Android 软键盘实机及系统重启证据的边界维持。可继续现场准备和后续验收，但这些门槛闭环前不得宣布整套项目交付完成。F 未修改业务代码、推送或部署 RM01。
