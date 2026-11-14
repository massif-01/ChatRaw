# F：DeepSeek 审批完整性有界审查

审查提交：`ee1aef5ed1b1c2dc89c58c25710bade24720a5ed`；停止证据：`e3622526b31dcbbcffcf59e9c69c55aa96ce3267`。日期：2026-11-13。

**结论：限定范围内未发现阻塞部署的 P0/P1，可交 A 合并部署后验收公开审批展示。** 不涉及 .98 推理、现场修改或 write/edit 产品合同扩展。

- 关联使用当前 `_Run` 的 `(sessionId, callId)` 和工具名称，兼容通知/审批两种到达顺序；重复请求不重复领取。SDK 源码确认审批携带原生 sessionId/callId，而参数来自同一 tool/call。工具结果移除该匹配，跨 run 不复用缓存。
- 展示前及批准分发前均核验 active run、stop、Harness 和原工具记录。F 独立复现：查询 cwd 时切换 run 后取消且不发布审批；工具已结束或 Harness 已替换后不能分发 allow；查找超时后的晚到通知不会自行发布审批，新 run 也不能借旧记录匹配。
- command/cwd 不截断；缺失、超限、NUL 或命中内联凭据规则的操作字段拒绝。原协议测试覆盖缺 command、工具名不符和跨 session；F 补充敏感/超限/NUL cwd 与缺 write/edit 路径，均没有可批准交互或敏感值泄漏。凭据检查按代码的内联模式规则验证，不声称识别所有秘密。
- 真实 DeepSeek SDK `0.2.2rc2` + 本地 loopback 模型接收端复现：超过 2,200 字符的完整命令及变更后的 cwd 与预期逐字段相同，拒绝不写 marker，单次允许写 marker；不接受 always。write/edit 按现有 operation 合同显示路径和 cwd，不展示文件正文。

## 证据

- [定向测试](approval-ee1aef5-evidence/targeted-tests.log)：4 项审批协议 + 1 项真实 SDK 测试通过。
- [F 独立边界](approval-ee1aef5-evidence/independent-tests.log)：4/4 通过；[复现源码](approval-ee1aef5-evidence/test_deepseek_approval_independent.py.txt)。
- [版本、命令与散列](approval-ee1aef5-evidence/manifest.json)。第一次测试启动使用了错误 cwd，导入旧工作树而缺少新测试类；该次不计入结果，[原始日志](approval-ee1aef5-evidence/harness-wrong-cwd.log)保留。随后全部在不可变 ee1aef5 归档目录中运行。

SDK 原生测试退出时报告已有的未关闭管道 `ResourceWarning`；测试断言通过，不据此宣称一般资源无泄漏。

停止证据 e362252 的 run `292b915f502f4f0f8d81a069624049a8` 记录了 started、公开 cancelled、同一 callId 的 ABORTED、32.14 秒观察期无 late 及所属 runtime/bash/sleep 退出。该证据发生在审批修复部署前，只证明该次停止；不能替代新审批展示的现场验收。
