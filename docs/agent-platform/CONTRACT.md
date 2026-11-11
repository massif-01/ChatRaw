# 公共接口 v1

总控拥有本文件。2026-11-12 合并A/F必要修订并冻结；Python精确类型/签名以 agent_runner/adapters/base.py（ADAPTER_CONTRACT_VERSION=1）为准，初始骨架提交02b25bd。兼容性补充由总控协调，叶模块不得私改。

## 1. 身份与数据归属

Agent ID 固定为 hermes / codex / claude / pi / deepseek；插件 ID 同名。普通聊天为 agent_id=null。
chat_id：ChatRaw聊天；session_id：执行服务会话；run_id：一次提交执行；interaction_id：一次交互；artifact_id：受控产物引用。全部为不透明字符串。
ChatRaw拥有聊天/显示记录/插件设置/绑定；Runner拥有运行权威状态、原生会话映射、交互等待和可重放事件。Agent拥有原生上下文。不得两边独立推进运行状态。
原生会话ID、原生请求ID、命令启动参数、认证信息和传输地址不由浏览器设置。Runner生成的安全ID在后端映射到原生引用。
普通聊天历史不自动导入Agent。旧聊天标识/文本保留，不能迁移的原生会话明确需要新会话。

## 2. 浏览器统一 API（ChatRaw 同源）

所有新端点遵守现有同源校验/限流，并由后端验证安装启用状态。无效请求在启动Agent/保存不可回滚副作用前拒绝。
新Agent API错误统一为 {error:{code,message,retryable}}，结合HTTP状态；message为安全可显示文本，不泄漏stderr/凭据。既有插件API保留原success/error字符串合同，B公共错误读取兼容这两类，不把对象显示成[object Object]。Runner错误不能直接透传内部trace。

- GET /api/agents → {agents:[{id,name,installed,enabled,availability,reason,capabilities,settings_revision}]}。availability=ready/unconfigured/unavailable/unknown；列表不隐式启动模型请求。
- GET /api/agents/{agent_id}/health → {agent_id,availability,reason,version,capabilities,models?}。明确区分程序存在/协议握手/认证/实际模型请求的验证层级。
- GET /api/agents/workspaces → {workspaces:[{id,label}]}。只列管理员允许的项目，浏览器不提交任意宿主绝对路径。
- POST /api/plugins/install-bundled，body={plugin_id:string} → {success,plugin_id,manifest}；只允许镜像bundled市场ID并完整复制插件及依赖资产。原URL/ZIP安装保留。本接口不安装或启动任何宿主Agent程序。
- POST /api/chats 沿用当前创建入口。
- PUT /api/chats/{chat_id}/agent，body={agent_id:null|string,workspace:{kind:"managed"}|{kind:"project",id:string}} → {chat_id,agent_id,session_id,workspace:{kind,id,label}}。有消息或活动执行的聊天不得改绑(409)，需要新聊天。managed目录持久化并按session隔离。
- GET /api/chats/{chat_id}/agent → {chat_id,agent_id,session_id,workspace,active_run_id,last_run_id}；未绑定返回agent_id/session_id=null。刷新/第二设备从此发现活动run，再取run snapshot与events。读取既有记录不因插件禁用而拒绝。
- POST /api/agents/attachments multipart(file,chat_id) → {attachment_id,name,mime_type,size}。文件归属绑定聊天，支持能力不符明确报错。
- POST /api/agents/runs，body={chat_id,client_request_id,message,attachments:[{attachment_id}]} → 202 {chat_id,session_id,run_id,status}。client_request_id 同chat幂等；同键不同内容409。body不能夹带全局prompt、history、RAG、active_skills、原生headers/keys。
- GET /api/agents/runs/{run_id} → {run_id,chat_id,session_id,status,last_seq,interactions:[],error?}。
- GET /api/agents/runs?chat_id=...&client_request_id=... → {run:记录|null,admission:"accepted"|"not_found"|"unknown"}；ChatRaw结果不明时核对Runner，不能凭本地缺记录返回not_found。unknown不允许自动换键重发；Runner在启动原生操作前持久保存幂等身份。相同键比较内容包括操作种类、绑定、输入和附件；compact使用同样规则。
- GET /api/agents/runs/{run_id}/events?after=N → application/x-ndjson；重放seq>N后继续订阅。断开只解绑订阅，不取消任务。
- POST /api/agents/runs/{run_id}/cancel → {run_id,status:"stopping"|终态}；幂等，确认上游结束后才能进入cancelled。
- POST /api/agents/runs/{run_id}/interactions/{interaction_id}/reply，body={answers:[...] }或{decision_id:string}或{cancelled:true}；仅接受请求声明的形状/选项。成功表示执行服务已接受，不伪装成工具已成功。重复相同响应幂等，冲突/失效409。
- POST /api/agents/sessions/{session_id}/compact，body={client_request_id} → 202 {run_id,...}；不支持返回明确能力错误；不回退ChatRaw压缩。
- GET /api/agents/artifacts/{artifact_id} → 经过归属和文件边界验证的内容/下载；不提供任意路径读取入口。

初版同一session只接收一个活动run，忙时409；B在客户端保留未发草稿。原生steer/queue可在声明支持后开放，但不得静默把新输入送到另一会话。若实现需要扩大此接口，先给总控最小补充建议。
有消息的Agent聊天不能通过/api/chat绕过绑定改成普通模式。ChatRaw手动compact入口同样尊重Agent绑定。
删除含活动run（包括unknown）的聊天先返回409并提供明确停止/核实提示；用户完成收敛后才删除显示记录。删除不得移除用户项目、原生全局配置或仍活跃的执行归属。

## 3. Runner 边界

Runner为独立宿主机进程，默认仅本机监听，通过专用凭据认证来自ChatRaw后端。Docker host-network场景可访问宿主loopback。浏览器不直连Runner。
建议/v1前缀，镜像sessions/runs/events/reply/cancel/compact/attachments/artifacts语义；A提供精确实现及版本握手。ChatRaw负责业务授权，Runner再次校验已有session/run/交互归属及启用配置。
宿主可执行程序/允许项目目录/运行账户由服务端配置管理，不接受浏览器拼接shell。插件设置只能通过adapter声明的字段schema存储/转发。进程启动使用参数数组。
ChatRaw→Runner超时不能自动重发未知是否成功的任务；创建接口同键幂等并允许查询。Agent配置在session/run适当边界保存快照，修改设置不改变进行中的运行。

## 4. 状态和事件

Run状态：queued, running, waiting_input, waiting_approval, stopping, completed, failed, cancelled, interrupted, unknown。
终态completed/failed/cancelled/interrupted；unknown表示需要核实，不能自动重试。浏览器断线不是终态。等待回答/审批不按普通输出空闲超时错误终止；遵守真实请求的expiry/cancellation。
queued/running/waiting/stopping/unknown均继续占用session活动位。unknown期间新run/compact返回409，不以failed/interrupted绕过隔离。interrupted只用于已确认原生执行终止但无法完整续接的情况；确认结束后才释放活动位。

每条事件：
```json
{"schema_version":1,"run_id":"...","session_id":"...","seq":1,"timestamp":"UTC ISO8601","type":"text_delta","data":{"text":"..."}}
```

type与data：
- status: {status,reason?}
- text_delta / reasoning_delta: {text,message_id?}；只转发原生实际提供的可见内容。
- tool_started / tool_updated / tool_completed: {tool_call_id,name,title?,input_preview?,output_preview?,status?,duration_ms?}；脱敏、限长，不能混入最终正文。
- interaction_requested: 见下节；interaction_resolved: {interaction_id,outcome,answer_summary?}。
- artifact: {artifact_id,name,mime_type,size?}。
- usage: {input_tokens?,output_tokens?,cost?,currency?}；未知不伪造0，不跨provider直接合并货币。
- error: {code,message,retryable:false|true}；retryable只是提示，不代表自动重发授权。
- done: {status,final_text?,error?}；Runner在真实run收敛后发出一次。需要重放完整记录，原生事件流EOF不等于完成。

done.final_text若存在（含显式空串），替换本run累计正文而不是追加；缺失则使用累计正文。按run_id幂等生成/更新ChatRaw assistant显示记录，浏览器离线不能导致结果未保存。重放done不新增消息。unknown只发布status，不发布done。终态与done在同一Runner事务持久化。

seq按run单调递增，持久后发布。重复订阅/刷新按seq去重；snapshot与事件不得产生丢失间隙。运行活动与终态必须持久，文本存储可做有界批处理但结束前flush。A明确异常退出的数据保障边界。

## 5. 通用交互

```json
{"interaction_id":"...","kind":"question","title":"...","detail":"...","questions":[{"id":"q1","text":"...","type":"single","options":[{"id":"a","label":"...","description":"...","recommended":true}],"allow_custom":false,"required":true}],"allow_cancel":true,"expires_at":null}
```
question.type=single/multi/text。回复answers=[{question_id,option_ids:[],text?}]；仅允许声明的选项和自定义输入。批次完整性按请求校验。
approval：{interaction_id,kind:"approval",title,detail?,operation:{tool?,command?,cwd_label?,paths?,host_label?},decisions:[{id,label,scope?}],allow_cancel,expires_at?}。decisions来自native允许值，经adapter映射，不能固定once/session/deny。
plan可使用question/approval的detail显示计划并声明presentation="plan"，不另造一套批准通道。
问题/选项文本不改写事实；所有HTML/Markdown均视不可信。禁止自动提交推荐选项，关闭UI不代表允许。多请求按列表管理，不只保存一个pending字段。
Runner分配interaction_id并私有保存原生回调/请求id；重启后必须确认上游仍等待，无法恢复则失效，不能用旧记录授予新操作。

Runner对同run的reply/cancel/插件禁用使用一个串行判定点；停止或禁用先生效，则未处理交互全部失效，迟到reply返回409且不能调用adapter.respond。批准先取得转发权，则后到停止不能保证撤销已执行操作，但仍停止剩余执行。不能持锁等待整轮模型结束。
同interaction同回复复用已接受结果，不再调用原生回调；异回复409。原生接收结果不明且没有原生幂等保证时，只查询/核实，不自动重发批准。cancelled:true仅在allow_cancel时接受，映射取消/拒绝或停止，不得变成允许选项。

## 6. 最小 Python adapter 合同

A拥有agent_runner/adapters/base.py与公共类型；C/D只实现叶模块，不改公共base。下列为方法概览，精确TypedDict/ABC及恢复类型以已发布base为准。

```python
class AgentAdapter:
    def validate_config(self, config: dict) -> dict: ...
    async def probe(self, config: dict) -> dict: ...
    async def create_session(self, session_id: str, workspace: Path, config: dict) -> dict: ...
    async def resume_session(self, binding: dict, config: dict) -> dict: ...
    async def run(self, binding: dict, request: dict, emit: Callable) -> dict: ...
    async def respond(self, binding: dict, interaction_key: str, reply: dict) -> None: ...
    async def cancel(self, binding: dict, run_id: str) -> None: ...
    async def compact(self, binding: dict, request: dict, emit: Callable) -> dict: ...
    async def recover_run(self, binding: dict, request: dict, config: dict, emit: Callable) -> dict: ...
    async def close(self, binding: dict) -> None: ...
```

factory/config校验和能力清单由A骨架确定。binding为仅Runner持久的原生session信息，不含可直接回显秘密；进程/回调句柄放adapter内存，避免序列化它们。
request至少包含run_id/message/本地受控attachment引用；不含ChatRaw历史。emit接收{type,data}并由Runner补安全ID/seq/time。交互emit包含私有native_key，由Runner剥离后绑定interaction_id。
run/compact返回{status,final_text,error?}，Runner发布终态。Adapter不自行写公共数据库。cancel可和run并发，返回不等于完成；run最终收敛。respond必须能在run正在等待时被并发调用，避免锁住读流。
compact.request至少包含run_id。首次或后续取得原生session/run引用时，adapter await emit({type:"binding_updated",data:完整binding})；Runner持久化后返回，不向浏览器公开该私有事件。不存在与上游的分布式事务：checkpoint前故障仍按unknown核实。
recover_run只核对/重新订阅既有执行，禁止重发原prompt；恢复能力缺失返回unknown并隔离该session。resume_session只恢复已收敛session的原生上下文，不等于恢复正在执行的run。binding私有数据、事件/交互typed定义以A发布base.py为准。
能力字段最少：streaming_text,tools,questions,approvals,cancel,resume,compact,images,files,steer,queue；具体限制放limits/reason，不能伪造支持。cancel要标明native或process_stop，进程级停止只能影响其独占session。

## 7. 前端注册与渲染边界

五插件manifest保留现有安装/启用/custom_settings机制，新增agent声明由后端白名单adapter注册表验证；浏览器不能动态加载服务器Python。
B新增统一ChatRawPlugin.agents入口或等价宿主API：插件注册身份/设置入口，不自行管理当前会话选择或HTTP流。选择状态以ChatRaw绑定为准。
主界面共享run/interaction结构；普通聊天和Agent文本都使用同一增量渲染器。插件不依赖旧hermesRun对象。保留普通聊天原hooks；Agent绕过改变输入上下文的hooks。
未稳定Markdown尾部可重解析，已稳定DOM不重复动画。收敛时完整一致，复制/导出取原文，动画只影响表现。

## 8. 兼容迁移

Hermes ID/现有密钥服务名尽量保留；旧专属API仅作为迁移过渡，发布前统一到新的权威执行路径，不长期运行两套状态机。
普通聊天记录/模型/插件设置不可丢失。迁移有版本与备份，回退不执行反向破坏性数据改写。
原生session无法恢复时明确提示新会话，不能重传所有历史伪装恢复。浏览器持久草稿不能变成审批权威。
