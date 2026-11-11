# 总控状态

目标：五Agent统一界面＋手机＋本地UI资源＋Chrome109。
用户已确认：宿主执行服务、独立持久任务目录/显式项目选择、总控/A/F Astra high。
当前：M0 公共合同v1已审定，A骨架02b25bd待总控集成；E/B实施中，F首轮完成。C/D按执行名额放行。

|Owner|模型/思考|阶段|thread/worktree|证据|
|---|---|---|---|---|
|A|astra/high|骨架已交付，等待下一阶段|01a1cc3e-4ff3-7410-94b5-43ef8740fb19 / .codex/worktrees/04ec/ChatRaw|02b25bd，5模拟契约测试|
|B|6.1-sol/xhigh|前端目标任务进行中|01a1cc44-651b-7110-8e53-8e7897dc228d / .codex/worktrees/a7f6/ChatRaw||
|C|6.1-sol/xhigh|等待base.py|||
|D|6.1-sol/xhigh|等待base.py|||
|E|6.1-sol/high|本地化进行中|01a1cc3e-72e2-7942-a25a-25f736a2d9b2 / .codex/worktrees/b360/ChatRaw||
|F|astra/high|首轮审查完成|01a1cc3e-9cc1-71b3-a6c1-ea33f770bf8a / .codex/worktrees/527c/ChatRaw|146基线测试通过；F01–F04已合入v1|

## 决策
- 2026-11-12：批准完整实施，模型按用户修正；所有已定范围不得缩减。
- 2026-11-12：公共合同v1冻结；A骨架精确类型成为叶adapter共享边界。

## 当前阻塞
- 现场环境/认证/测试设备尚未核实，不阻塞本地接口和UI资源工作。
- 首次SSH只读检查使用rm01用户被拒绝(publickey,password)；已异步询问正确用户名/连接方式，不打印或索取私钥。
- 10.10.99.99:51111 的/ready、/health、/api/plugins均连接被拒绝；未据此推断Agent不存在或数据丢失。

## 合同审查待合并
- A：首次native session ID产生后的持久化、compact携带run_id、unknown恢复核对。
- F：刷新发现active run、client_request_id结果查询、cancel与reply竞争顺序。
