# B：主界面、五插件、流式渲染与手机

模型 gpt-6.1-sol，thinking xhigh。总控放行后启动目标模式，不设未经用户指定的token预算。

先读主目录 /Users/massif/ChatRaw/docs/agent-platform/{PLAN,CONTRACT,ACCEPTANCE}.md 与 Plugins/README.md。只能写自己的工作树。目标是完整前端交付，不把出字预览当成正式功能完成。

任务：五Agent独立插件（hermes/codex/claude/pi/deepseek）、菜单单选持久聊天绑定、独立设置/检查、通用多题单多选/文本/审批/plan面板、run事件订阅和重放、普通/Agent发送路径分离、附件与产物UI、增量Markdown和认可动效、手机全流程。

现有视觉保留。按用户指令应用frontend-design等适用技能；代码实施前形成简洁方案，实际截图检视。预览：/Users/massif/.codex/visualizations/2026/11/11/01a1cbe7-07c0-7220-8038-ba312e08fd53/chatraw-stream-preview.html，仅为效果参考，其中现代CSS不得直接当作Chrome109正式兼容实现。

拥有backend/static/app.js/index.html/styles.css、新UI/renderer模块、五Agent插件及市场目录。接收E的依赖接线patch；不自行重选E锁定版本。禁止改backend/main.py/Runner；接口问题报总控。

先用规范事件fixtures接UI，随后接真实网关。按钮选择不自动提交；已失效问题不可再批准；恢复依据后端。UI不提供任意可执行命令/宿主路径输入。Mobile包括键盘/横屏/长选项/所有插件设置，不只是首页。

验收G01/G03/G05/G08–G10/G14；Chrome109约束贯穿代码并由E/F复验。输出截图/测试/真实与模拟边界、branch/commit、遗留问题。app.min/styles.min由总控集成统一生成。提交前final-pr-commit；不push/发布/操作RM01。
