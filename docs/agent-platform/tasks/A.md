# A：统一后端、宿主执行服务与 Hermes

模型 gpt-6-astra，thinking high（不是xhigh）。首轮普通模式。

先读主目录 /Users/massif/ChatRaw/docs/agent-platform/{PLAN,CONTRACT,ACCEPTANCE}.md。以当前独立工作树实现，主目录只读。用户已批准完整实施和独立本地提交供总控集成。

第一批任务：审查v0.1合同是否足够支持五种原生接口；列出阻塞性问题和最小修订；检查现有后端、Hermes、数据库与Docker边界；提出并创建可导入的agent_runner/adapters/base.py公共骨架和叶adapter测试所需最小类型。不要实现第二套公共抽象或私有字段。第一轮交付后由总控冻结v1，再发送后续goal任务。

后续负责：公共执行服务、会话/状态/事件/交互持久化、ChatRaw同源网关、上下文流程拆分、附件产物、Hermes迁移、Docker与宿主systemd交付、迁移与恢复。Runner管理的进程与外部Hermes服务区分所有权；不得停止用户已有服务。

所有权：backend/main.py、新backend公共模块、agent_runner除C/D叶模块、Hermes adapter、backend依赖、Dockerfile/compose、宿主部署脚本和相关测试。前端接线写建议供B，不修改app.js/index/styles。

首轮不得部署RM01或改其配置；远程环境清单由总控统一调查。发现需新增产品决策，报告而不自行选。协议小修可建议，不必反复讨论惯常实现。任务核心是能交付的公共基础，不追求泛化框架。

交付：合同审查、骨架签名、branch/commit、窄范围检查、待确认点。完整阶段再按G02–G08/G13–G15给测试证据。实际提交前使用final-pr-commit；不push、不发布。
