# ChatRaw Agent 平台实施任务书

状态：执行中。决策来源：2026-11-12 用户在总控对话明确授权。
总控 chat：01a1cbe7-07c0-7220-8038-ba312e08fd53。
初始代码基线：0c14990（main）；不得恢复已回退的 LinkDB bridge。

## 唯一交付目标

让 ChatRaw 成为 Hermes、Pi、DeepSeek Harness、Codex CLI、Claude Code 五种 Agent 共用的操作界面，并完成手机适配、界面资源本地化和 Chrome 109 兼容。

完成含义是整套功能集成、实测并交付，不是任务书完成、模拟测试通过或某个适配器能回复一句话。局部问题按是否阻塞验收排序；不得反复无边界打磨一个小问题而停止其他可推进工作。

## 已确定的产品边界

- 五个独立插件；可同时安装启用。输入框旁单一按钮打开上拉菜单，选择普通聊天或一个 Agent。
- 每个聊天持久绑定 Agent、工作目录和执行服务 session；有消息后更换 Agent 创建新聊天。
- 五个 Agent（包括 Hermes）全部经过统一执行服务、状态与事件协议。原生传输差异只能留在适配器。
- Agent 模式完全跳过 ChatRaw 历史拼接、摘要/压缩、RAG/搜索自动增强、全局 system prompt 和 Skill 正文注入。普通聊天保留原有功能。
- Agent 本轮消息/附件按能力交付。原生 slash 指令不能被 ChatRaw Skill/install 等 intercept 抢走。压缩使用 Agent 原生能力；不支持则明确提示。
- 提问与审批通用：单选、多选、自由输入、多题批次、工具审批、支持时的计划确认。选择不等于提交，关闭不等于批准。
- 已认可柔和出字预览：新片段轻微模糊渐清晰，旧内容稳定。正式实现普通聊天和 Agent 共用，支持 reduced motion，不能为了动画积压输出。
- 手机覆盖聊天、键盘、菜单、设置、问答、审批、附件和长内容；保持现有视觉方向，不重绘整站、不换框架。
- Chrome 109 为最低 Chromium 兼容验收版本；IE 不支持。iPhone Safari、Android Chrome 纳入移动验证。Firefox ESR 115 不属于强制交付。
- 核心 UI/Markdown/高亮和交付的官方插件运行资源本地化；UI 启动不能依赖外部 CDN。业务模型/搜索 API 不属于离线保证。
- 单用户/共享工作环境，多设备访问同一套聊天与配置，不新增多租户。
- ChatRaw 主程序必须 Docker；执行服务在 RM-01 10.10.99.99 宿主机，使用受控系统服务；Agent 不放进 ChatRaw 主容器。
- 普通任务自动分配独立持久工作目录；已有项目从管理员配置的目录中显式选择。cwd 不是沙箱，不改变 Agent 权限。
- 不自动安装或升级用户的 Agent，不覆盖原有配置。保存并复用正确运行账户的原生状态，认证可用性必须实测。
- 网页关闭/切换聊天不取消任务；显式停止才取消。同一会话串行，不同会话有总并发上限。
- 重启保留记录并核对运行状态；不得自动重发可能已执行的操作，不承诺断电无缝续跑。
- 禁用/卸载阻止新任务，取消/收敛所拥有的活动任务和交互，不删除用户项目、全局配置或已有聊天记录。

## 对话与配置

|Owner|职责|模型|thinking|模式|
|---|---|---|---|---|
|总控|协议审定、调度、集成、交付|gpt-6-astra|high|分阶段 goal|
|A|统一后端/执行服务/部署/Hermes|gpt-6-astra|high|接口审查普通；放行后 goal|
|B|主界面/五插件/手机/渲染|gpt-6.1-sol|xhigh|goal|
|C|Codex+Claude adapters|gpt-6.1-sol|xhigh|goal|
|D|Pi+DeepSeek adapters|gpt-6.1-sol|xhigh|goal|
|E|本地依赖/构建/Chrome109|gpt-6.1-sol|high|普通批次|
|F|独立审查/验收|gpt-6-astra|high|普通里程碑|

默认最多三条执行线同时运行；总控用 wait_threads 跟踪真实进展，不创建定时自动化代替监督。所有工作使用独立工作树。不得自行创建更多执行对话或递归委派。

## 所有权

- A：backend/main.py、统一 backend Agent 网关/数据迁移、agent_runner 公共模块、Hermes adapter、Dockerfile/compose、宿主机服务与部署脚本、后端依赖。
- B：backend/static/app.js、index.html、styles.css、新渲染/交互模块、五个 Agent 插件、市场目录、移动布局。
- C：agent_runner/adapters/codex.py、claude.py 及其独立测试/说明。
- D：agent_runner/adapters/pi.py、deepseek.py、Pi 配套扩展及其独立测试/说明。
- E：backend/static/vendor、前端依赖锁/构建工具、兼容检查。涉及 index/app.js 的接线先提供精确 patch 交总控/B，避免双写。
- F：独立验证脚本、验收报告；不替实现者修改业务代码。
- 总控：docs/agent-platform/公共协议与状态、集成分支和冲突协调。
- backend/static/app.min.js/styles.min.css 等构建产物由总控集成时统一生成。提交前不要夹带其他 owner 的修改。

## 节点

M0：接口审定、任务书与环境清单；M1：统一执行骨架+本地 UI 资源；M2：Hermes 纵向贯通；M3：五适配器与插件接通；M4：完整 UI/手机/109；M5：迁移、重启、真实环境与独立验收交付。

首批 A/E/F。公共接口确认且 base.py 发布后，B/C/D 按空位启动。每条线可先用契约测试双推进，但真实运行证据不能用 fake 替代。

## 交付与变更纪律

每次交付报告：branch/commit、改动范围、接口变更、测试命令/结果、real vs simulated、阻塞项、迁移/重启要求。
执行完成→待集成→待独立验收→验收通过。实现者的完成报告不直接等于全项目完成。
发现协议缺口，先记录问题与最小建议供总控确认，不扩展自己的私有协议。P0 数据损坏/权限错误/错误执行、P1 核心流程失败优先修复；P2 视觉细节有界修正并跟踪。
工作树内可按授权完成本地提交供集成；遵守 final-pr-commit 技能。不得自行 push/发布/升级生产服务。RM-01 只读检查可以推进；实际安装部署、共享配置变更和重启由总控统一执行窗口，避免干扰现有工作。

## 未完成的技术核实

执行主机 OS/CPU、账户与Agent版本/认证、Hermes原生session恢复、DeepSeek SDK停止边界、Claude允许的认证路径、真实Chrome109/Win8与手机设备环境。用调查解决；缺少访问或凭据时明确报告。不能因为暂时缺一项实机证据放弃可完成的本地实现，也不能因此声称整体验收通过。

## 参考

- 出字预览绝对路径：/Users/massif/.codex/visualizations/2026/11/11/01a1cbe7-07c0-7220-8038-ba312e08fd53/chatraw-stream-preview.html。
- 项目插件文档：Plugins/README.md；Hermes现有文档：docs/hermes.md。
- 当前代码主目录：/Users/massif/ChatRaw。各执行线只读此处的协议/任务书，不修改主目录。
