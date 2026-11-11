# 总控状态

目标：五Agent统一界面＋手机＋本地UI资源＋Chrome109。
用户已确认：宿主执行服务、独立持久任务目录/显式项目选择、总控/A/F Astra high。
当前：M0基线6874553已提交，含公共合同v1/A骨架/F基线审查；A/B/E实施中，F首轮完成。C/D按执行名额放行。

|Owner|模型/思考|阶段|thread/worktree|证据|
|---|---|---|---|---|
|A|astra/high|公共Runner/Hermes目标任务进行中|01a1cc3e-4ff3-7410-94b5-43ef8740fb19 / .codex/worktrees/04ec/ChatRaw|02b25bd，5模拟契约测试；集成6874553|
|B|6.1-sol/xhigh|前端目标任务进行中|01a1cc44-651b-7110-8e53-8e7897dc228d / .codex/worktrees/a7f6/ChatRaw||
|C|6.1-sol/xhigh|等待base.py|||
|D|6.1-sol/xhigh|Pi/DeepSeek目标任务进行中|01a1cc50-17c8-71a3-bb04-4ec011d226bc / .codex/worktrees/9133/ChatRaw||
|E|6.1-sol/high|首批交付，待集成版复验|01a1cc3e-72e2-7942-a25a-25f736a2d9b2 / .codex/worktrees/b360/ChatRaw|e8db0e0，本地vendor/构建/真实109旧基线断CDN验证|
|F|astra/high|首轮审查完成|01a1cc3e-9cc1-71b3-a6c1-ea33f770bf8a / .codex/worktrees/527c/ChatRaw|146基线测试通过；F01–F04已合入v1|

## 决策
- 2026-11-12：批准完整实施，模型按用户修正；所有已定范围不得缩减。
- 2026-11-12：公共合同v1冻结；A骨架精确类型成为叶adapter共享边界。
- 2026-11-12：官方bundled插件本地完整安装由A提供后端、B接市场，E交付资源；第三方URL/ZIP原路径保留。Marked9高亮由B统一渲染，E提供接线参考。
- 2026-11-12：集成E资源时，PostCSS单独补丁升级8.5.32以消除已确认sourceMappingURL路径读取公告；未运行audit fix --force，未整体升级库。vendor:check及build通过。剩余4项low涉及esbuild开发server/KaTeX前置原型污染，按实际调用面复核，不据此宣称无风险。

## 当前现场与阻塞
- SSH认证已由用户提供的信息解决；密码不落盘。仅总控持有临时连接，未清除密钥。
- 现场实测：Ubuntu24.04.4 x86_64，Python3.12.3，Node22.23.2，npm10.9.8，15GiB可见内存，约830G可用盘。
- docker命令实际为Podman4.9.3/podman-docker；Docker服务inactive。rm01 PATH及/home/rm01、/opt、/usr/local/bin有限目录检查未找到五Agent/ChatRaw。
- 10.10.99.99:51111拒绝连接。已询问是否授权准备独立Docker Engine与Agent环境，保留既有Podman及数据。待答期间不做现场安装。
- E已运行官方Playwright存档Chromium109.0.5414.46；正式集成/Win8实机待验收。本机simctl当前无可用模拟设备；真实手机键盘证据仍待准备。

## 合同审查待合并
- A：首次native session ID产生后的持久化、compact携带run_id、unknown恢复核对。
- F：刷新发现active run、client_request_id结果查询、cancel与reply竞争顺序。
