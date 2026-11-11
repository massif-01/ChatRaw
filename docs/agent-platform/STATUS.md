# 总控状态

目标：五Agent统一界面＋手机＋本地UI资源＋Chrome109。
用户已确认：宿主执行服务、独立持久任务目录/显式项目选择、总控/A/F Astra high。
当前：M0基线6874553、E首批资源df5de2d、D适配器2512fe7已集成；A/B/C实施中，D补充Hermes原生协议核验；F第二轮无D集成阻塞，E/F等待正式集成版本复验。

|Owner|模型/思考|阶段|thread/worktree|证据|
|---|---|---|---|---|
|A|astra/high|公共Runner/Hermes目标任务进行中|01a1cc3e-4ff3-7410-94b5-43ef8740fb19 / .codex/worktrees/04ec/ChatRaw|02b25bd，5模拟契约测试；集成6874553|
|B|6.1-sol/xhigh|前端目标任务进行中|01a1cc44-651b-7110-8e53-8e7897dc228d / .codex/worktrees/a7f6/ChatRaw||
|C|6.1-sol/xhigh|Codex/Claude目标任务已放行|01a1cc53-86d3-7ba0-bf50-314739d9fa55 / .codex/worktrees/1d34/ChatRaw||
|D|6.1-sol/xhigh|首批集成并通过叶模块审查；补测Hermes|01a1cc50-17c8-71a3-bb04-4ec011d226bc / .codex/worktrees/9133/ChatRaw|270cf79/224b012；集成2a95724/2512fe7；总控11协议检查通过；原生程序＋本地模型替身证据见D-adapters.md|
|E|6.1-sol/high|首批交付，待集成版复验|01a1cc3e-72e2-7942-a25a-25f736a2d9b2 / .codex/worktrees/b360/ChatRaw|e8db0e0，本地vendor/构建/真实109旧基线断CDN验证|
|F|astra/high|D适配器独立审查完成，待整体版本|01a1cc3e-9cc1-71b3-a6c1-ea33f770bf8a / .codex/worktrees/527c/ChatRaw|146旧基线测试；D原有16＋新增6通过，无跳过；F-D-round2-20261112.md|

## 决策
- 2026-11-12：批准完整实施，模型按用户修正；所有已定范围不得缩减。
- 2026-11-12：公共合同v1冻结；A骨架精确类型成为叶adapter共享边界。
- 2026-11-12：官方bundled插件本地完整安装由A提供后端、B接市场，E交付资源；第三方URL/ZIP原路径保留。Marked9高亮由B统一渲染，E提供接线参考。
- 2026-11-12：集成E资源时，PostCSS单独补丁升级8.5.32以消除已确认sourceMappingURL路径读取公告；未运行audit fix --force，未整体升级库。vendor:check及build通过。剩余4项low涉及esbuild开发server/KaTeX前置原型污染，按实际调用面复核，不据此宣称无风险。
- 2026-11-12：D采用DeepSeek官方SDK＋独占session runtime保留完整交互，停止必须核对所属工具进程收敛。A发现Hermes Runs不能直接满足cwd绑定，获准核实并采用满足能力的官方TUI Gateway JSON-RPC；不改变统一公开接口，不伪造工作目录或会话恢复。
- 2026-11-12：公共接口稳定、E/F首批已结束后，临时放行A/B/C/D四条互不写同一文件的实现线，减少C无依赖的串行等待；现场联调和配置仍由总控排队。

## 当前现场与阻塞
- SSH认证已由用户提供的信息解决；密码不落盘。仅总控持有临时连接，未清除密钥。
- 现场实测：Ubuntu24.04.4 x86_64，Python3.12.3，Node22.23.2，npm10.9.8，15GiB可见内存，约830G可用盘。
- 主机lpmu305仍有TTO Web/采集端口以及NFS/SMB服务；不得为本项目擅自中断它们，整机重启安排独立窗口。
- docker命令实际为Podman4.9.3/podman-docker；Docker服务inactive。rm01 PATH及/home/rm01、/opt、/usr/local/bin有限目录检查未找到五Agent/ChatRaw。
- 10.10.99.99:51111拒绝连接。已询问是否授权准备独立Docker Engine与Agent环境，保留既有Podman及数据。待答期间不做现场安装。
- E已运行官方Playwright存档Chromium109.0.5414.46；正式集成/Win8实机待验收。本机simctl当前无可用模拟设备；真实手机键盘证据仍待准备。

## 已关闭的合同审查项
- A：首次native session ID产生后的持久化、compact携带run_id、unknown恢复核对，已合入v1。
- F：刷新发现active run、client_request_id结果查询、cancel与reply竞争顺序，已合入v1；实现仍需验证。

## 实现中发现
- B/G09已关闭：真实Chrome中复现stream renderer与markdown-enhancer交互：live停顿后KaTeX先渲染，finalize同source时公式被TextNode扁平化。B修复后总控重验：live停顿1600ms不提前增强，收敛后保留1个KaTeX公式。正式整体渲染另验；临时诊断位于outputs/agent-platform/check-stream-plugin.mjs。
- A/G01：草稿session.config永久快照可能使保存后的可编辑设置对既有聊天下轮无效；已要求对齐进行中不变/下轮生效，复用空闲resume边界并做出站测试，不改变native会话身份。
- 总控PostCSS8.5.32产出的旧基线CSS SHA256与E首批8.5.15证据相同：ca131c569c41fed286c3225404fc5447f7f510d2072f279bdc9d7caf7f68de31。
- A/G13–G15：要求清除生产模块已退役的旧Hermes执行状态机，并把Runner凭据挂载放入Agent专用Compose overlay，保留未安装Agent时普通聊天的独立Docker启动。
