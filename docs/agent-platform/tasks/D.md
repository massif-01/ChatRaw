# D：Pi 与 DeepSeek Harness 适配器

模型 gpt-6.1-sol，thinking xhigh。合同冻结且base.py可用后目标模式。

读 /Users/massif/ChatRaw/docs/agent-platform/{PLAN,CONTRACT,ACCEPTANCE}.md 和公共骨架。只写自己工作树中的pi.py/deepseek.py、必要Pi扩展、对应tests/docs；不改base/DB/API/UI。

Pi使用RPC，核对当前agent_settled/队列/abort语义；需要审批时使用可信配套扩展并明确不是OS沙箱。支持原生extension UI问答到统一interaction，不伪造原生能力。

DeepSeek优先验证Python SDK，以保留人工问答。当前研究显示SDK缺按会话cancel，候选按session独占runtime进程并正确停止/恢复；ACP支持cancel但交互较少。请用当前官方源码/协议核实，给有证据的最小推荐。接口选择和影响先报告总控，不能静默牺牲已定问答目标。

同一runtime多session时不能为停止一个任务杀掉其他任务。线程回调不能堵塞读循环。DSH_HOME必须显式受控，恢复不得无声创建替代session。SDK依赖/runtime版本兼容说明交A。

先完成本地协议测试与实现，RM01真实窗口由总控安排。无认证不能假装实测；不自动安装升级现有Agent、不改宿主共享配置、不打印秘密。

交付两个adapter、Pi必要扩展与安装指引、停止/恢复/提问正反例、能力矩阵、branch/commit、真实与模拟边界。提交前final-pr-commit；不push/部署。任务围绕交付，不研究无关的Harness扩展生态。
