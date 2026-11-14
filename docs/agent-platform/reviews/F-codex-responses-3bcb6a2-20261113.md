# F：Codex Responses 兼容入口独立审查

审查提交：`3bcb6a2aadf36192257f9c2d687cac55130efebf`。日期：2026-11-13。

**结论：本次限定范围内未发现阻塞合入的 P0/P1。可交由 A 按宿主显式配置、固定无鉴权上游、新建 managed 会话的范围进行现场验收。此结论不代表真实 .98 的压缩后续接已修复。**

## 已验证的接收端行为

|范围|结果与证据|
|---|---|
|指令完整性与顺序|顶层 instructions 在前，随后按原 input 顺序收集 system/developer 文本；不支持的指令结构先拒绝，不静默丢弃。独立接收端逐字段比较验证普通用户消息、工具定义、function_call/function_call_output 的 call_id 与图片 data URI 保留。|
|入口边界|默认不启用；启用后仅监听 127.0.0.1 随机端口。两个实例的随机令牌不能交叉授权；令牌不转发上游。目标地址来自宿主固定配置，客户端 header/metadata 不能改目的地；不跟随上游重定向。|
|SSE 与错误|现有测试验证上游错误状态与 SSE 字节保留、坏鉴权、路径、非文本指令和关闭清理。独立中途断流验证下游收到传输错误，不能以正常 EOF 宣告成功。|
|原生 Codex|真实 Codex CLI 0.153.4 配合隔离本地接收端：同一 thread 压缩后续接保留上下文及权限指令；工具调用/结果配对、图片、关闭后 resume 通过。批准执行的 shell 验证 listener 令牌为空。默认原生 provider 的文本与 resume 亦通过。|
|取消与清理|启用兼容后停止生成得到 cancelled，同一 adapter 可继续下一轮；关闭 adapter 后原监听端口不可连接。此项不替代现场停止长工具的已有独立证据。|
|旧宿主配置快照|真实 Runtime/SQLite + 受控 adapter 接收端：公开 set_settings 写宿主字段返回 400；宿主新增兼容配置并重启后，旧会话 binding/base_config 不变，公开 model 更新仍可生效且不会引入兼容字段；新会话收到显式兼容配置。|

## 验证与复现

- [现有协议/HTTP 测试](compat-3bcb6a2-evidence/compat-regression.log)：11/11 通过。
- [隔离真实 Codex 测试](compat-3bcb6a2-evidence/native-regression.log)：2/2 通过。
- [F 独立边界测试](compat-3bcb6a2-evidence/independent-boundaries.log)：4/4 通过；[检查源码](compat-3bcb6a2-evidence/test_codex_responses_independent.py.txt)。
- [宿主快照检查](compat-3bcb6a2-evidence/host-snapshot-boundary.json)：通过；[检查源码](compat-3bcb6a2-evidence/host_snapshot_check.py.txt)。
- [输入版本、命令和证据散列](compat-3bcb6a2-evidence/manifest.json)。宿主快照检查使用 root `8c0da0cf93fa7952833fa37fce1ba9ed768efa5b` 的临时归档，仅覆盖上述 C 提交的两个 Codex 运行文件；其他检查直接使用 C 提交归档。

没有访问 .98、修改现场或主工作区业务文件。未扩展审查到未提交的 D 审批展示修复。下一步由 A 验证真实 .98 上同一新建会话的 seed → compact → follow-up 与上下文连续性，保留 run/thread 与最终接收结果。
