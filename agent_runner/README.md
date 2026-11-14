# ChatRaw Host Agent Runner

当前实现与交付见 [M2](M2.md)，部署见 [deploy/README.md](../deploy/README.md)。
公共 adapter v1 已由总控冻结；Runner 负责运行权威状态与持久事件，ChatRaw 只负责同源网关和显示投影。
以下保留首轮候选合同审查作为设计依据，不代表当前仍只有骨架。

## 首轮合同审查记录

2026-11-12；基线 `0c14990`。本批只交付可导入合同、模拟消费者测试和审查建议，
未实现 Runner HTTP/数据库/调度、Hermes 迁移或部署。已核对总控合并 A/F 修订后的 v0.2；
`docs/agent-platform/CONTRACT.md`
由总控拥有；本文件不是另一份已经冻结的协议。总控冻结 v1 后再放行叶 adapter。

## 结论与最小修订

v0.1 的统一入口、原生上下文归属、异步交互和单 session 串行方向可实现。
但仅凭当前八个方法，无法安全表达迟到的 native session ID、压缩停止关联和失联恢复。
建议冻结下表；候选类型已落实在 `adapters/base.py`。

|缺口|候选约定|为什么需要|
|---|---|---|
|native ID/运行引用在首轮才产生|私有 `binding_updated`，完整 `SessionBinding`；`await emit` 返回前 Runner 持久化|只在 run 返回时保存会丢失中途崩溃后的恢复定位信息|
|compact 缺 run_id|`compact(binding, {run_id}, emit)`|压缩也占用 session、可被停止、必须归属同一事件日志|
|EOF/传输失联不代表结束|`RunResult.status` 允许 `unknown`；unknown 不发 done，不释放 session 给下一次执行|避免重发已执行操作或产生同会话并行任务|
|恢复与普通 resume 混在一起|新增 `recover_run(binding, {run_id}, config, emit)`；没有 message 字段，默认返回 unknown|恢复的是旧运行，不能通过重新 run 或新建 session 假装恢复|
|原生交互 ID 的生命周期不完整|requested/resolved 都带顶层私有 `native_key`；Runner 转为公开 interaction_id|解决原生取消、超时、关闭后仍留可点击审批的问题|
|产物 ID 分配者不清楚|adapter 发受控候选 `path/name/mime_type`，Runner 验证、复制并分配 artifact_id|不能让叶模块或浏览器任意登记宿主路径|
|能力与探测只有散落布尔值|固定 Capabilities；`cancel_mode=none/native/process_stop`；probe 按 program/protocol/authentication/model_request 分别报告|安装成功不等于认证或模型可用，停止实现也不能靠 UI 猜测|
|工厂/设置 schema 没有签名|每 session 一个无 I/O 的无参实例；`AdapterFactory=Callable[[], AgentAdapter]`；`validate_config` + `settings_schema`|叶模块不自建注册表，也不从浏览器导入 Python/拼 shell|

这些是候选共享字段，不授权各叶模块再增加自己的顶层协议。`native` 是唯一允许
adapter 自有的持久化命名空间，存原生 ID/恢复引用，不存秘密、进程句柄或回调。
`ADAPTER_CONTRACT_VERSION=1` 表示候选目标版本，发布是否冻结由总控决定。

## 可直接使用的签名

```python
from agent_runner.adapters.base import AgentAdapter, Emit, RunRequest, RunResult

# 全部方法在 Runner 事件循环调用；除 validate_config 外均为 async。
validate_config(config: AdapterConfig) -> AdapterConfig
probe(config: AdapterConfig) -> ProbeResult
create_session(session_id: str, workspace: Path, config: AdapterConfig) -> SessionBinding
resume_session(binding: SessionBinding, config: AdapterConfig) -> SessionBinding
recover_run(binding: SessionBinding, request: RecoveryRequest,
            config: AdapterConfig, emit: Emit) -> RunResult
run(binding: SessionBinding, request: RunRequest, emit: Emit) -> RunResult
respond(binding: SessionBinding, interaction_key: str, reply: InteractionReply) -> None
cancel(binding: SessionBinding, run_id: str) -> None
compact(binding: SessionBinding, request: CompactRequest, emit: Emit) -> RunResult
close(binding: SessionBinding) -> None
```

公共导入还包含 `Attachment`、`Capabilities`、`ProbeResult`、`SessionBinding`、
问题/审批/答复 TypedDict、`AdapterEvent`、`AdapterError`、`UnsupportedCapability`。
所有类型定义只有标准库依赖。TypedDict 不是运行时输入校验器。
工厂的显式白名单由后续 Runner 持有；本批不提前导入未安装的 SDK 或未交付的叶模块。

`settings_schema` 为浏览器可编辑字段的 JSON Schema object，必须禁止额外字段。
可执行路径、参数数组、允许目录、凭据由宿主配置另行管理，不能由该 schema 开放。
`validate_config` 对合并后的可信私有配置做纯校验/规范化，不启动进程、不打印配置。
Runner 负责设置 schema 校验、配置快照和秘密存储；adapter 只收到对应会话的快照。

### 事件、停止与恢复的不变量

1. `Emit = Callable[[AdapterEvent], Awaitable[None]]`。返回表示 Runner 接收并持久化，
   不等待用户答题。浏览器断开不能取消此 sink；adapter 持续读原生输出。
2. `binding_updated` 只进 Runner 的私有存储，不进入浏览器事件日志。
   事件携完整新快照，只能更新同 session/agent/workspace 的 native 引用；Runner 校验归属。
   adapter 在获知 ID 后、继续依赖它的操作前 await 保存。初始 create/resume 返回值同样先持久化。
3. 原生操作与本地 SQLite 不可能跨进程原子提交。创建已成功但回包/保存前崩溃的窗口仍存在；
   缺定位证据时保持 unknown，不补发。此骨架没有声明消除该窗口。
4. `run`/`compact` 单 session 串行；`respond`/`cancel` 可并发调用。
   原生阻塞/线程回调必须单独调度，不阻断传输读循环或 Runner 事件循环。
5. cancel 返回只表示停止请求已发出；原 run/compact 的结果提供结束证据。
   有显式停止且证实停下才 cancelled；确认非用户停止的中断可 interrupted；无法核对则 unknown。
   如果停止与成功完成竞态，保留实际 terminal evidence，不把已完成强制改成 cancelled。
6. adapter 不发 done/终态 status、不写公共数据库。Runner 事务落终态、flush 文本后发一次 done。
   `final_text` 是最终全文，覆盖显示快照，不能当成另一段 delta 追加。
7. 交互私有 key 在 run 内唯一且绑定当前原生请求，原生数字/对象 ID 留在 adapter 映射中。
   `respond` 返回不证明工具成功；原生 answered/expired/invalidated 用 resolved 通知。
   Runner 保存多个 pending 交互；取消、过期、重启失效后旧公开 ID 不能批准新操作。
8. 重启先 fence 非终态运行、使旧交互失效，再调用 recover_run；后者仅查询/重接旧运行，
   可以持续 await 原生结束。确认上游仍等待的请求才用新 key 重新 emit。
   没有恢复能力或无法关联 native run 就 unknown；普通 resume 不接管此工作。
9. process_stop 只可停止本 session 独占且 Runner 拥有的运行时。
   close 在运行收敛后释放所属句柄，不删除用户原生记录，不停止用户已有 Hermes 服务。

总控 v0.2 已合并浏览器恢复入口和竞争规则：刷新按 chat 找回绑定/活动 run；按
client_request_id 查询未知提交结果；cancel/reply/禁用使用同一串行判定点。
本批不实现这些 API。后续 reply 只有在取得原子转发权后才能转发，
cancel 一旦先进入 stopping 则不接纳新 reply；已转发的批准不能宣称可撤回。
跨网络转发与本地 ack 也有未知窗口，不能在崩溃后盲重发批准。

## 五条原生路径的适配可行性

以下为 2026-11-12 文档/源码边界核对，不是宿主版本和认证的实测。

|Agent|已核对的约束|公共骨架的对应点/剩余问题|
|---|---|---|
|Codex|app-server 审批有 thread/turn/request 关联，可用决策包含对象；resolved 也可能表示请求被清除|decision_id 映射完整原生允许值，不能固定三按钮；清除不能伪装已同意。复杂 MCP 表单/URL 不应静默改成纯文本问答|
|Claude|官方 Python SDK 支持并发 interrupt；停止后必须读出旧 ResultMessage 才能接新 query|cancel ack 与 run 结果分离；首次获得 native ID 时 checkpoint；SDK 认证路径由 C 核实|
|Pi|RPC 是长期 JSONL 进程；agent_end 后自动重试/压缩仍可继续，agent_settled 才没有后续自动工作|run 等待 settled；扩展 UI 走通用交互；不得把一条 RPC response 当任务完成|
|DeepSeek|Python SDK 明确 dsh_home，支持原生问答回调；会延迟启动 runtime 并复用到 close|线程回调需桥到事件循环；本次 README 不足证明有按 session cancel，D 继续核源码并验证独占进程停止/恢复|
|Hermes|仓库已有 runs/events/approval/stop 桥接，含配置快照、同源验证和 remote allowlist|外部服务所有权必须保留；真实 session 持久化、事件重接和运行查询能力待现场核对，不能用 fake server 证明|

原生能力不能无损映射时给出明确不支持；不凭空增加通用任意表单/URL执行器。
全量原生功能覆盖不是本轮公共接口的目标，但已定多题、单选/多选/文本、审批及计划呈现不能丢。

原始依据：

- [Codex app-server approvals](https://learn.chatgpt.com/docs/app-server#approvals)
- [Claude Python SDK interrupt](https://code.claude.com/docs/en/agent-sdk/python#example---using-interrupts)
- [Pi RPC](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/rpc.md)、[Pi JSON events](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/json.md)
- [DeepSeek Harness Python SDK](https://github.com/deepseek-ai/deepseek-harness/blob/master/python/sdk/README.md)
- 本库 `docs/hermes.md` 与 `backend/main.py`；本轮不以搜索摘要推断 Hermes 服务实现。

## 现有代码/数据库/Docker 的实施边界

|位置（基线行号）|现状|下一阶段应改的根因|
|---|---|---|
|backend/main.py:2241 prepare_chat_submission|拼 Skill/system，执行自动压缩并保存消息|Agent admission 必须在该入口之前分流和校验，不能先保存后拒绝|
|backend/main.py:4481 / 4531 Hermes payload|复用 build_chat_completion_messages，传 instructions/history|Agent 只传本轮 message/附件，普通聊天路径保留|
|backend/main.py:3931 / 4346 / 4380|内存 active runs、一个 pending_approval|Runner 持久 runs/events/interactions 为唯一运行权威；ChatRaw 只存绑定/展示投影|
|backend/main.py:4927 / 4949|网页断开/生成器关闭时 stop，非流式审批被停止|任务寿命与 HTTP 订阅拆开；统一交互不依赖 Stream Output 设置|
|backend/main.py:230 Database / 3145 chats|SQLite WAL + synchronous NORMAL；无 Agent 绑定/迁移版本|独立 Runner DB、版本迁移与备份；ChatRaw 增量加绑定/投影，不共写同一权威状态|
|backend/main.py:3155 / 3165 / 3190|删除/手动压缩/普通 chat 未处理 Agent 绑定|按 v0.2 补统一 admission；含活动/unknown run 的聊天删除返回409，先停止/核实|
|Dockerfile|Python 3.11，只 COPY main.py/static/Plugins|新增 backend 模块后修 COPY；不要把宿主 Agent/原生配置塞进主容器|
|docker-compose.yml|Linux host network，/app/data 卷，预构建 latest 镜像|可访问宿主 loopback Runner；需要专用凭据、独立持久目录和明确 systemd 用户/环境|
|.github/workflows/ci.yml|路径触发未覆盖 agent_runner，测试未发现该包|集成时由总控/CI owner 加路径及 unittest，不能把本地通过当 CI 已覆盖|

持久化建议：运行状态/交互/绑定用提交后发布；若使用 WAL，关键状态采用 FULL 同步并在目标文件系统验证。
进程异常退出仅能保证已提交数据，机器断电和外部 Agent 的原生状态不能由本地事务兜底。
文本可有界批次持久化，最终 done 前 flush；这部分是下一阶段实现与 G07 测试，当前未交付。

## 首批验证与后续依赖

```sh
python3 -m unittest agent_runner.tests.test_adapter_base -v
/opt/anaconda3/bin/python -m unittest agent_runner.tests.test_adapter_base -v
mypy --python-version 3.11 --strict agent_runner/adapters/base.py
git diff --check
```

五项测试验证：无第三方依赖导入、未支持能力显式失败、默认恢复 unknown 且不重发、
await checkpoint 后才继续以及等待时 reply/cancel 可并发进入、错误对象可序列化。
本地 Python 3.14.2 / 3.12.4 均通过；mypy 1.10.0 的 Python 3.11 严格类型检查通过，
另以 `mypy --python-version 3.11 --check-untyped-defs agent_runner` 检查模拟消费者通过。
当前未找到 Python 3.11 可执行程序，因此尚无 3.11 运行时测试证据。
并发测试中的 adapter 与 sink 是模拟消费者，没有实现实际数据库或进程控制。
这不建立 G02–G08/G13–G15 的 real_pass，也不覆盖浏览器 API 校验/产物文件边界。

后续依赖：总控冻结上述最小合同与 F 的公共 API 修订；C/D 提供精确 SDK/运行时依赖与
原生能力证据；宿主访问、账户/认证、Hermes 服务版本/所有权由总控统一核实。
本批不修改既有 schema/配置，不需要迁移或重启；没有 push、部署或远程变更。
