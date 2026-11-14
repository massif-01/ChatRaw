# F 首轮独立审查：公共接口 v0.1 与基线验收

日期：2026-11-12（Asia/Shanghai）。代码基线：`0c14990d86066f6baf0d7de137b26f4e665c28d7`，当前工作树 detached HEAD。

## 决策

**v0.1 方向可采用，原文暂不直接冻结。补齐下列四组约束，由 A 发布对应的可导入 base 后即可冻结，不需要另起协议框架。** 四组中 F03、F04 已与总控同步的 A 候选修订重合；F01、F02 是需合并的独立补充。这里的优先级表示缺口若进入实现的影响，不声称新系统已有可复现生产漏洞。

五种 Agent 共用身份、状态、交互和事件的方向没有结构性阻塞。原生差异应留在 adapter，如实声明不支持能力；本次没有真实五 Agent 版本、认证或交互实测，不能据此断言全部原生协议已适配。

首轮不阻塞普通聊天回归、本地资源、手机布局和适配器调查等独立工作；C/D 共用调用签名应在 A 骨架明确后对齐。不存在要求多租户、跨 Agent 无损迁移、断电无缝续跑或恢复 LinkDB bridge 的理由。

## 审查输入与边界

- 只读主目录的 `docs/agent-platform/{PLAN,CONTRACT,ACCEPTANCE}.md`、`tasks/F.md`；输入 SHA-256 在 [review-inputs.json](review-inputs.json)。下文合同引用对应 v0.1 行号。
- 检查当前工作树的旧接口、测试、Hermes 说明及 CI 配置。未改主目录、业务代码、验收标准、插件、构建产物或部署配置。
- 仅使用主目录现有 `.venv/bin/python -B` 读取解释器和依赖；测试代码来自独立工作树，每个测试模块独立进程，临时数据位于本工作树报告目录并在结束后清除。
- 未接触 RM01、未 SSH、未操作或重启服务、未 push、未创建子对话。总控告知的现场 HTTP/SSH 访问问题仅是外部依赖状态，不是本轮亲测结果。
- 本轮交付文件路径，不提交；无需把报告提交作为合同审定的前置条件。

## 必须补入的最小约束

### F01 · P1 · 浏览器丢失 run_id 后没有约定发现路径

位置：CONTRACT 20–28、39、61。Owner：A／总控，B 消费。

原文提供按 run_id 查询，却没有说明 GET 聊天如何返回绑定和活动 run，也没有定义按 client_request_id 查询的精确入口。`允许查询` 尚不足以让独立前后端对接。

重现场景：Runner 已接受执行，202 返回前连接断开；网页刷新或另一设备打开同一聊天。浏览器没有 run_id，无法订阅输出、回答问题或停止。另一个危险路径是 ChatRaw 超时后给同一用户提交生成新幂等键，造成重复执行。

最小修订：

1. 扩展既有聊天读取结果或增加一个读取入口，返回持久绑定 `agent_id/session_id/workspace` 和 `active_run_id`。A 明确具体路由及响应，B 无需依赖浏览器本地状态恢复。
2. 固定一个按 `(chat_id, client_request_id)` 查询已接收 run 的入口，例如 `GET /api/agents/runs?chat_id=...&client_request_id=...`；对查询中/未确认的状态不能展示为可安全重新执行。只读查询也须能查出禁用插件的既有记录。
3. ChatRaw 到 Runner 透传稳定幂等身份，Runner 在启动原生操作前持久记录接收关系；compact 使用同样规则，键的内容比较包括操作种类和绑定。重发查询不创建新任务，同键提交只返回原 run；未知结果不换键自动重发。

验收：人为丢弃一次 202；刷新和第二客户端都找到同一 run；模拟 ChatRaw 重启后查询；最终原生启动计数恰为一次。跨聊天同字符串键互不混淆；同键异内容 409。

### F02 · P0 · 取消／禁用与审批必须有同一个生效顺序

位置：CONTRACT 15、26–27、37、68–72、92；PLAN 禁用/卸载和停止边界。Owner：A，C/D 配合原生转发，B 呈现。

原文已要求重复响应幂等、失效 409、重启确认上游仍等待，但没有规定 reply 与 cancel/disable 并发时谁先获得执行权。仅先读 `enabled=true` 或 `waiting_approval`，随后在另一个 await 后转发批准，不能保证停止生效后迟到批准不执行。

重现场景：两个设备分别发批准和停止；批准通过初检后暂停，停止先被 Runner 接受，批准随后到达原生回调。类似地，批准已发出但响应丢失，重试可能再次触发同一个原生动作。

最小修订：

1. Runner 对每个 run 的交互回复、取消和禁用收敛使用同一串行判定点。进入 stopping/终态或禁用生效时使所有未处理交互不可再提交；迟到回复 409，不能再调用 adapter.respond。无需给数据库和适配器各造一套权威状态。
2. 若批准先获得转发权，不能承诺撤销已经执行的动作；后到停止仍须停止剩余执行。响应语义记录这个先后顺序，不能把“点过停止”伪装成“此前没有执行”。
3. 同 interaction 相同回复重试复用已接收结果，不再触发原生回调；冲突回复拒绝。原生接收结果不明且无原生幂等保证时，查询/核实，不能自动再发批准。重启后的旧交互也遵守同一原则。
4. `cancelled:true` 仅在 allow_cancel 时接受，并映射原生取消/拒绝或停止本 run；不得映射成任何允许选项。

验收：在 Runner 判定点与原生接收端之间设置可控屏障，分别测批准先/停止先；并发重复回复、禁用后迟到回复、响应丢失重试。断言最终原生接收计数和工具标记文件，而非只看 HTTP 状态或前端按钮消失。这不要求持锁等待整个模型运行。

### F03 · P0 · unknown 必须继续占用 session，不能借 interrupted 释放

位置：CONTRACT 26、31、43–44、59、92。Owner：A，adapter owners 提供结束证据。

总控同步 A 已拟修订：失联未核实结束应 unknown，不能终态。独立审查确认需要该修订，并补上并发含义。

重现场景：Runner 重启失去进程/原生流引用，旧 Agent 或其工具仍在运行；如果标记 interrupted 并释放 session，新 run 会与旧操作并发，破坏同一原生上下文串行和副作用唯一性。

最小修订：unknown 是未收敛状态，继续占用该 session 的活动位置（或由等价 session 隔离状态阻止新执行）；拒绝新 run/compact，不自动 resume 成新一轮。不确认上游结束时不得以 failed/interrupted/cancelled 绕过此约束。确认原执行结束后才释放；interrupted 表示已确认终止但无法完整续接，区别于结果不明。done 仅代表已收敛终态；unknown 用状态事件告知核实原因。queued、所有 waiting、stopping、unknown 都算未收敛运行。

验收：隔离进程故障注入，使工具留下可观察活动标记，再丢失 Runner 通道；确认同 session 新请求 409、其他 session 仍按总并发策略运行。原生进程结束/受控清理确认后才解除占用。不把进程停止请求返回当作工具树已停止的证据。

### F04 · P1 · 原生映射增量持久化与 compact 的 run 身份

位置：CONTRACT 81–92。Owner：A／总控定义公共骨架，C/D/Hermes 遵循。

总控同步 A 已拟修订这两项；独立审查确认是实际接入约束，不是泛化需求。

重现场景：create_session 尚未获得原生 ID，首轮事件才返回 ID；run 未结束时 Runner 崩溃。如果 ID 只在 adapter 内存或 run 最终返回值中，重启无法恢复同一原生 session。另一个调用不对称是 compact 无 run_id，而 cancel 必须以 run_id 识别运行，压缩不能稳定复用统一取消/事件路径。

最小修订：A 提供一个 Runner 私有的绑定更新通道，明确 adapter 获得/变更原生 session ID 时调用且由 Runner 持久化；不转发到浏览器，不让 adapter 写公共数据库。用回调或现有 emit 中一种明确的私有消息即可，不同时保留两套方式。原生映射未知时按 F03 隔离，不自动新建会话。compact 增加 request（至少 run_id）参数；与 run 共用活动位、幂等、事件、取消及结果语义。

冻结配套：base 必须明确 emit 是否 await、binding 更新形状及确认时点、create/resume 返回字段、capabilities 数据类型、interaction 私有 key 的剥离位置。只固定本次实际用到的类型，禁止 C/D 分别猜测。resume_session 恢复原上下文不等于重新提交未完成输入。

验收：首轮取得原生 ID 后、最终输出前终止 Runner，再核对绑定仍可查询；不提供 ID 的故障窗口不得自动重跑。compact 与普通 run 同时提交只能接受一个；compact 取消使用相同 run_id 路由并验证真实收敛。

## 非新增冻结阻塞，但集成验收必须落实

1. **最终正文归一（A/B）**：v0.1 的 `done.final_text` 没有定义替换还是追加。建议固定：有 final_text 时为本 run 的权威完整正文（含显式空串）；缺失时使用累积正文。按 run_id 幂等生成/更新聊天显示记录，不能依赖浏览器在线才能保存。重放 done 不新增 assistant 消息。不另造消息总线；在 G04/G09 用冲突快照验证复制、导出、刷新一致。若实现者采用其他语义，必须在同一骨架中固定并联合验证。
2. **数据清理与终态记录（A）**：删除聊天/旧聊天清理不得留下无法归属的活动任务；可在活动时明确拒绝删除，避免扩大本次设计。seq 持久后发布的要求应落实到事件事务，终态与 done 不出现“状态终止但永远无收尾事件”的间隙。ChatRaw 展示记录可从 Runner 重建，不以两库分布式事务作为前提。
3. **五种真实能力尚未证明**：如实 unavailable、原生不支持清晰提示是合法结果；但五种实际接入以及 Chrome109 仍是发布门槛。不能以 fake 构造一个 question 证明原生 Agent 的 question 能交付。
4. **兼容范围已经足够清楚**：Chrome109 用真实引擎；Win8 的实机证据单列，不伪造 UA。手机尺寸模拟与 Safari/Android 软键盘证据分列。离线只要求核心/官方插件运行资源，不把业务 API 纳入离线保证。

## 基线实测

运行命令（独立工作树根目录）：

```sh
/Users/massif/ChatRaw/.venv/bin/python -B docs/agent-platform/reviews/run_baseline.py
```

环境：macOS 27.0.1 arm64、Python 3.12.4。FastAPI 0.136.3、aiohttp 3.14.1、Pydantic 2.13.4、certifi 2026.5.20、python-multipart 0.0.32。完整命令和时间见 [results.json](baseline-0c14990/results.json)，逐项输出见同目录 `.log`。

|模块|数量|结果|证据边界|
|---|---:|---|---|
|test_context_compaction|20|通过|模拟 LLM，旧普通聊天压缩|
|test_fonts_route|2|通过|本地字体解析和路径边界|
|test_hermes_bridge|52|通过|内存假响应/直接函数调用，旧 Hermes 路径|
|test_hermes_smoke|11|通过|真实 loopback HTTP/SSE，接收端为 FakeHermesServer，非真实 Hermes|
|test_http_session_tls|4|通过|HTTP session/SSL 配置单测，非外部 TLS 端到端|
|test_skills|57|通过|本地注册、安装、上下文等测试，外部调用为替身|
|合计|146|全部通过，无跳过|仅旧基线 simulated_pass，不等于 G01–G15 通过|

每个模块都在 import 时设置 DATA_DIR，而 backend.main 持有模块级数据库；因此逐模块独立进程，避免同进程 discovery 的环境覆盖/清理相互污染。不修改已有测试以追求通过。系统默认 Python 3.14 缺少 FastAPI，未安装/升级它，使用现有只读环境完成验证。

### 必须替换的旧行为断言

这些是既定产品改动，不应因旧测试通过而保留：

- `backend/test_hermes_bridge.py:1162` 要求 outbound `instructions` 与 `conversation_history` 含 ChatRaw 内容；新 Agent 路径必须反向验证不注入，而普通聊天的 skills/summary/system 测试保留。
- `backend/test_hermes_bridge.py:1593`、`backend/test_hermes_smoke.py:318`、`:345` 要求断线/关闭消费流即上游停止；新断线应只移除订阅，显式 cancel 才停止。
- `backend/test_hermes_bridge.py:1221`、`backend/test_hermes_smoke.py:377` 要求非流式模式遇审批就停止；新问答审批生命周期独立于浏览器文本显示设置。
- `backend/test_hermes_bridge.py:1691` 的 EOF 不保存为完整答复这一不变量仍正确；其中“立即 stop”的旧桥接动作应依据统一 Runner 的实际失联核实策略重写，不照搬旧生命周期。

`.github/workflows/ci.yml:43–78` 当前主要是语法、关键 lint、导入、Docker 构建和 print smoke，并没有执行上述 146 项。绿色现有 CI 不是 G14 证据。新增系统的回归入口应显式运行相关 suite；报告脚本可复用，但不是要求引入新的测试平台。

## G01–G15 阶段验收安排

所有新平台 Gate 当前均 `not_started`；下表是原 ACCEPTANCE 的执行细化，不更改其标准。G14 有旧基线 `simulated_pass` 子证据，尚未在新实现提交上完成回归。真实环境暂不可用不妨碍本地契约/故障注入；也不能用后者代替 real_pass。

|Gate / 阶段|关键动作和最终断言|Owner / 证据|
|---|---|---|
|G01 / M3–M4|五插件分别安装、配置、启用、禁用、卸载；有消息改绑 409；刷新/第二设备取回绑定；禁用中活动任务收敛，旧记录可读|B/A/F；真实 UI 操作与服务状态，插件生命周期正反例|
|G02 / M2–M3|每 Agent 两聊天，各置不同测试标记；多轮及重连后仅原聊天能取回；核对原生 session ID；问答、附件/产物跨聊天引用拒绝|A/C/D/F；真实 adapter/native trace（脱敏）+ 隔离断言|
|G03 / M1–M3|设置明显的历史/system/summary/Skill/RAG 哨兵；Agent 实际出站只有本轮消息/附件，native slash 原样到达；普通聊天保留增强|A/B/F；同时捕获浏览器到后端与 adapter 到原生边界，不能只看请求字段 schema|
|G04 / M1–M3|切换聊天、断网、EOF、重复/乱序消费、丢 202；恢复原 run；seq 去重、不漏尾；最终文本修正后刷新/复制不重复；最终原生操作计数为一|A/F；独立 Runner 协议测试 + 五 Agent 真实事件样本|
|G05 / M2–M4|single/multi/text/批次、计划呈现、推荐但未提交、关闭、允许/拒绝；缺题、重复题、错选项、过期、跨 run、重复/冲突回复；按 F02 竞态测试|A/B/C/D/F；契约覆盖所有形状，真实 Agent 覆盖原生支持项，接收端断言|
|G06 / M2–M3|文本、工具执行、等待交互、compact 中分别停止；另一 session 持续运行；停止后迟到批准不得生效；进程模式核对所属工具子进程终止|A/C/D/F；真实 native/process 停止证据，不用按钮状态证明停止|
|G07 / M5|分别关浏览器、重启 ChatRaw 容器、重启 Runner、重启宿主；覆盖运行/等待/已完成/未知窗口；记录恢复、失效、unknown，不重发副作用|A/F；每层独立步骤和前后 run/session/交互/计数；只有总控安排现场窗口|
|G08 / M3–M4|图片/文件按能力传递；尺寸/类型不符在执行前拒绝；跨聊天 attachment、artifact、符号链接逃逸与任意路径读取拒绝；下载字节正确|A/B/C/D/F；隔离 fixture + 实际支持 Agent 的接收证据|
|G09 / M4|长文/代码/列表/表格/公式/多字节跨片段；新片段效果、旧内容稳定、输出不积压；final_text 收敛、复制导出原文、reduced motion|B/F；正式动态页面截图/录屏、原文比对；旧小预览不算正式通过|
|G10 / M4–M5|320/375/390/430 CSS 宽及横屏覆盖聊天、菜单、设置、问答审批、附件长内容；焦点/溢出；iPhone Safari 与 Android Chrome 真实软键盘出现和收回|B/F；viewport 模拟与真实设备/OS/浏览器/键盘证据分别记录|
|G11 / M4|真实 Chrome109 登录/启动、发消息、流、交互、停止、附件、设置、渲染；记录引擎完整版本和 OS；Win8 实机状态单列|E/F；不能以现代 Chrome 改 UA 或语法构建成功替代|
|G12 / M1–M4|清缓存/无既有 CDN 缓存，阻断外部 CDN；核心页面及所有交付官方插件启动；Markdown/高亮/字体所需资源可用|E/F；网络请求日志、阻断规则、截图；业务模型/搜索 API 排除|
|G13 / M5|独立复制旧数据，含普通聊天、模型/密钥配置、旧 Hermes 历史/设置；迁移和备份回退演练；不可恢复原生会话明确提示；旧入口无第二执行状态机|A/F；前后记录清单/校验值（不输出密钥）、迁移版本与恢复命令|
|G14 / 每阶段/M5|在集成 commit 运行普通聊天/skills/压缩/TLS/字体回归并补 UI 主流程；旧 Hermes 冲突断言按以上目标替换；不把删测试当修复|A/B/E/F；命令/版本/逐项日志和保留不变量映射|
|G15 / M5|主程序 Docker、Runner 宿主受控服务；正确运行账户的原生配置/认证实测；持久工作目录、项目允许列表、服务凭据、并发上限、重启启动顺序可复核|A/F；总控部署窗口的真实 compose/service/UID/path 与脱敏认证探测；不自动安装升级 Agent|

阶段依赖：M1 先运行 G03/G04/F01–F04 契约及故障注入，G12 本地资源可并行；M2 用 Hermes 完成纵向实测；M3 将同一组不变量应用到其余四 Agent；M4 验证正式 UI、真实109和移动设备；M5 再做现场重启、迁移、部署及全量回归。仅当缺陷影响后续结果时暂停相关 Gate，其他已授权工作继续。

每份阶段证据固定记录：集成 commit、Agent/浏览器/OS/运行账户版本、命令步骤、预期与实际、real 或 simulated、原始日志路径、失败 Owner 和优先级。每 Agent 的文本/工具/问答/审批允许和拒绝/停止/恢复/compact/附件分别列能力与证据；不支持是明确说明，不伪造通过记录。

## 冻结与后续放行

总控将 F01–F04 的最小语义合入 CONTRACT，A 用可导入 base 固定字段/调用时序后，可冻结 v1 并启动对接；不要求先拿到全部现场证据才冻结接口。F02/F03 的最终接收端不变量必须在运行实现中闭环，不能只改文档。

后续 F 接收总控指定的集成 commit 再执行验收，不在当前基线上伪造新接口测试结果。真实五 Agent、Chrome109、手机软键盘和四层重启均尚未验收；146 项旧测试通过不能宣布大更新完成。
