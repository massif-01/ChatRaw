# F：Codex 前台进程登记竞态独立审查

**结论：`e889688fd12f9342c0d31271d9baa72a53c8907f` 可集成，本次增量未发现 P0/P1。最多0.5秒的登记等待没有替代原有停止证据核对，也没有扩大跨轮进程终止范围。**

范围仅为前台命令 spawn→登记→interrupt 的竞态。使用 `git archive e889688` 快照 `/private/tmp/chatraw-f-codex-e889688.GF3KVF`；未修改业务代码，未访问 .98 或改变现场。交付文档中的压缩兼容调查不在本轮扩展审计范围。

## 实现判断

- cancel 仍先标记 stopping、清除待批回复并 checkpoint 停止意图，再进入有界登记检查。等待期间迟到审批不能取得允许权。
- 只检查当前 turn 已开始的 command item，未获批准的初始审批项不等待登记。查询固定使用当前 threadId；`_owned_background` 仍按本 turn 的 itemId 过滤。
- 0.5秒耗尽、查询断线/拒绝或格式错误后仍尝试发送 turn/interrupt。没有因为“等过登记”就宣称取消成功。
- 原 `_confirm_tool_stop` 保持：原生终止确认及列表复查不足时返回 unknown；停止意图恢复隔离不变。没有新增全 thread 清空、按名称杀进程或跨轮终止。

## 实际验证

|验证组|结果|
|---|---|
|C 的 Codex 协议回归＋3项真实隔离原生停止|10/10通过，无跳过。覆盖延迟登记、跨轮过滤、unknown恢复，以及前台 shell、后台 shell、待审批停止。|
|F 原独立失败边界|3/3通过：列表失败、terminate=false、terminate=true但列表仍有进程，均保持 unknown；只处理所属进程。|
|F 新增登记查询挂起反例|1/1通过：第一次登记查询永不回复，约 **0.501秒**后取消该查询并发出 interrupt；最终仍为 unknown，没有调用任何不明进程的 terminate。|

合计 **14项通过**。真实原生部分使用 Codex CLI **0.153.4**、C 的 Python3.14.2隔离环境及 loopback 模型替身；协议反例使用 A 的Python3.12.4。前台测试设置 yield_time_ms=30000，在实际 `started` 文件出现、尚未返回工具结果时取消，随后等待完整延迟并确认 `.late` 不出现。后台测试同样检查实际文件副作用。

证据：[定向回归](codex-e889688-evidence/targeted-regression.log)、[停止失败边界](codex-e889688-evidence/independent-stop-failures.log)、[登记等待上界](codex-e889688-evidence/registration-bound.log)、[新增反例脚本](codex-e889688-evidence/test_codex_registration_bound.py.txt)。

复现从上述快照执行：

```sh
CHATRAW_C_NATIVE_TESTS=1 PYTHONDONTWRITEBYTECODE=1 /private/tmp/chatraw-c.fMJYKf/venv/bin/python -B -m unittest -v \
  agent_runner.tests.test_c_adapter_protocol.CodexProtocolTests \
  agent_runner.tests.test_c_native_adapters.NativeAdapterTests.test_codex_native_stop_confirms_foreground_shell \
  agent_runner.tests.test_c_native_adapters.NativeAdapterTests.test_codex_native_stop_terminates_background_shell \
  agent_runner.tests.test_c_native_adapters.NativeAdapterTests.test_codex_native_stop_during_approval
```

F 独立脚本用 `PYTHONPATH=<快照>:<本报告目录>`，分别执行 `python -B -m unittest test_c_fix_boundaries.StopFailureTests -v` 和 `python -B -m unittest test_codex_registration_bound.RegistrationBoundTests -v`。

可交 A 在受控窗口做 .99/Linux 的新 managed 会话复验；本机替身通过不改写既有现场 unknown，也不替代现场进程作用域证据。此前 [DeepSeek patches 审查通过](F-deepseek-patches-1cdc681-20261113.md)的结论保持。

归档说明：新增反例源代码按 `.py.txt` 文本保存；复现时另存为原 `.py` 文件名。此归档提交不携带可执行脚本或产品代码。
