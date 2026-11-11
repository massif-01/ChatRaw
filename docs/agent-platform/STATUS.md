# 总控状态

目标：五Agent统一界面＋手机＋本地UI资源＋Chrome109。
用户已确认：宿主执行服务、独立持久任务目录/显式项目选择、总控/A/F Astra high。
当前：本地完整实现已集成165a509，E真实109/离线验收通过，F已关闭全部本地已知P0/P1；总控最终网关与断网Docker同卷重建通过。全项目目标仍未完成，等待现场安装授权、真实模型认证、手机实机与整机重启验收。逐项门槛见VALIDATION.md。

部署准备：e91d32f固定源码包及Linux amd64镜像已生成、导出并校验；本机仿真断网/同卷重建通过。产物在outputs/agent-platform/deployment-e91d32f，证据见reviews/deployment-e91d32f/README.md，尚未上传现场。

等待项复核：六个执行对话均为completed/idle，本地没有仍在运行的验证任务。现场安装确认在连续三个总控目标回合中仍未收到；源码、镜像和复现材料准备完毕，后续须由用户确认新增宿主环境后继续。总目标不视为完成。

|Owner|模型/思考|阶段|thread/worktree|证据|
|---|---|---|---|---|
|A|astra/high|完整后端及标题增量已集成|01a1cc3e-4ff3-7410-94b5-43ef8740fb19 / .codex/worktrees/04ec/ChatRaw|a688cc8/7057c6e/cb4d9fc；集成5430b39/2d770f0/e822294；153执行通过23可选跳过，标题4项通过|
|B|6.1-sol/xhigh|已集成并通过最终后端复验|01a1cc44-651b-7110-8e53-8e7897dc228d / .codex/worktrees/a7f6/ChatRaw|70894b7；集成bd9ad55；E与总控最终真实网关/浏览器检查通过，手机实机边界保留|
|C|6.1-sol/xhigh|修复完成并通过最终定向复验|01a1cc53-86d3-7ba0-bf50-314739d9fa55 / .codex/worktrees/1d34/ChatRaw|69a7427/集成165a509；F-PLAT-01关闭，UI编码到真实原生9项通过|
|D|6.1-sol/xhigh|首批与Hermes补测完成|01a1cc50-17c8-71a3-bb04-4ec011d226bc / .codex/worktrees/9133/ChatRaw|270cf79/224b012；集成2512fe7；Hermes真实Gateway补测2add9fd/集成40bbb20|
|E|6.1-sol/high|最终G11/G12本机验收通过|01a1cc3e-72e2-7942-a25a-25f736a2d9b2 / .codex/worktrees/b360/ChatRaw|2d770f0真实109/157、真实后端/Runner、外部请求0；reviews/E-2d770f0/REPORT.md|
|F|astra/high|本地完整平台有界验收通过|01a1cc3e-9cc1-71b3-a6c1-ea33f770bf8a / .codex/worktrees/527c/ChatRaw|F-platform-final-69a7427-20261112.md；153执行/23可选跳过、7权威层、5标题、9问答定向通过，现场边界保留|

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
- E已使用官方Playwright存档Chromium109.0.5414.46通过正式集成本机验收；Win8实机证据单列。本机simctl当前无可用模拟设备；真实手机键盘证据仍待准备。

## 已关闭的合同审查项
- A：首次native session ID产生后的持久化、compact携带run_id、unknown恢复核对，已合入v1。
- F：刷新发现active run、client_request_id结果查询、cancel与reply竞争顺序，已合入v1，并通过完整平台独立检查；现场原生运行仍待验收。

## 实现中发现
- B/G09已关闭：真实Chrome中复现stream renderer与markdown-enhancer交互：live停顿后KaTeX先渲染，finalize同source时公式被TextNode扁平化。B修复后总控重验：live停顿1600ms不提前增强，收敛后保留1个KaTeX公式。正式整体渲染另验；临时诊断位于outputs/agent-platform/check-stream-plugin.mjs。
- A/G01已关闭：草稿session.config永久快照导致既有聊天下轮设置不生效的风险已修正；进行中不变，下轮通过空闲resume边界生效，原生会话身份不变，接收端测试通过。
- 总控PostCSS8.5.32产出的旧基线CSS SHA256与E首批8.5.15证据相同：ca131c569c41fed286c3225404fc5447f7f510d2072f279bdc9d7caf7f68de31。
- A/G13–G15已完成本地验证：生产模块旧Hermes执行状态机已移除，Runner凭据挂载置于Agent专用Compose overlay；未安装Agent时普通聊天的独立Docker启动通过。
- C/G03已关闭：Claude SDK改用官方claude_code preset，真实原生请求核对用户/项目/本地配置、CLAUDE.md和Skill加载，同时无ChatRaw上下文标记；F独立复验通过。
- A/D/G02已修正：真实Hermes Gateway无附件提交不可发送attachments空数组；A修正构造后，D以原样adapter验证握手/cwd/文本/历史恢复/停止与后续继续，报告见handoffs/D-hermes/README.md。
- C-F01/G06：Codex turn interrupted后后台shell仍继续写入，必须核对所属后台工具收敛；C-F02/G05：Codex/Claude审批命令截断隐藏了实际执行后缀。C修复62dc389已通过F原反例和失败边界复验，两项关闭；最终后端本机验收通过，现场边界保留。
