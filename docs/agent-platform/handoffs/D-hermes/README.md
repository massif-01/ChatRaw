# Hermes Gateway 原生协议复验

2026-11-12 · D 线独立验证 · macOS arm64，Python 3.14.2，aiohttp 3.14.5

真实 Hermes Gateway 使用 NousResearch 官方源码 `6a0d2d12815c0546b0bcaf05046e2fe3293f60aa`。模型端点为本机 OpenAI 兼容替身。Gateway、票据签发、WebSocket、执行权威与会话存储均运行官方实现。验证脚本给子进程独立 HOME、HERMES_HOME 和宿主锁目录，清除继承的模型凭据，结束时回收自己启动的进程。 [Hermes 官方接线说明](https://hermes-agent.nousresearch.com/docs/developer-guide/programmatic-integration)

## A 修订后复验

A 在文本提交中省略空 `attachments` 后，对其工作树 `106e28f` 上的在写文件重新冻结并以默认模式验证。该副本 `hermes.py` 的 SHA-256 为 `20f6e6ae2efab86205818a700a4fbd81c3a39f80002e414925af648cb956cfd7`。全程使用适配器原样出站，脚本退出码为 0。

票据握手、显式 cwd 建会话、空会话恢复、正文增量与最终正文、带历史恢复全部通过。停止在模型替身释放之前收到原生终态 `interrupted`，适配器也返回 `interrupted`。Gateway 保持运行，原会话之后完成另一轮。这个终态命名仍需与 ChatRaw 的显式停止语义核对。

## 原始适配器

第一次验证取自 A 工作树 `4401323` 上的在写文件，冻结副本 `hermes.py` 的 SHA-256 为 `9a92c3c40fa37cee94576294177dd42a572739578b47c0bab341b6bfaba94ff9`。

|路径|结果|
|---|---|
|Gateway 启动前探测|返回 `unavailable`|
|票据签发与 WebSocket|通过。协商 `hermes-gateway-v1`，`runtime.describe` 握手通过|
|新会话与 cwd|通过。Gateway 确认指定绝对路径|
|空会话恢复|通过。新适配器以相同原生会话 ID、profile 和 cwd 恢复|
|普通文本|阻断。Gateway 的 `prompt.submit` 返回 `4001 invalid_params`，文本未进入原生执行|
|带历史恢复和停止|依赖首轮原生提交通过，原始适配器的路径在该点中止|

**根因。** A 的 `run` 总会带 `attachments: []`。Gateway 的 `admit_attachments` 把字段缺失视为纯文本输入，把空列表视为无效参数。最小修复是纯文本提交省略该字段，并以原始出站报文补回归。文件上传另有原生约束。源码规定 `prompt.submit` 的附件必须是允许的图片类型，并先放入当前 profile 的图片缓存目录；本批未运行上传。 [Gateway 附件准入源码](https://github.com/NousResearch/hermes-agent/blob/6a0d2d12815c0546b0bcaf05046e2fe3293f60aa/gateway/session_ingress_media.py)

## 最小报文差异复验

在 A 修订之前，使用脚本的 `--omit-empty-attachments-for-diagnosis` 只在测试进程的 WebSocket 发送边界去掉空 `attachments`，每次转换都输出记录。适配器文件、Gateway 和模型替身保持相同，用于定位根因。

- 首轮返回 `completed`，原生增量拼接与最终正文一致，并产出带原生 admission ID 的私有 checkpoint。
- 断开后换适配器重新附着，同一会话的后续模型请求包含原先提交的 prompt。关闭适配器后 Gateway 仍在运行。
- 停止测试在模型流已建立并被替身暂停时调用适配器的 `cancel`。替身仍未放行时，原生 `prompt.receipt` 已到达终态，`outcome=interrupted`。A 将结果返回为 `interrupted`。Gateway 继续运行，原会话恢复后又完成一轮。
- 若 ChatRaw 对显式停止统一显示 `cancelled`，A 应将本轮用户停止与原生终态按同一 admission 关联后映射，保留未请求停止的原生 `interrupted`。该决定归 A 和总控。 [原生取消实现](https://github.com/NousResearch/hermes-agent/blob/6a0d2d12815c0546b0bcaf05046e2fe3293f60aa/gateway/session_controls.py)

原生停止阶段记录为 `{"stage":"cancel","status":"interrupted","native_outcome":"interrupted","owner_alive":true,"before_provider_release":true}`。

## 复现

在临时目录取得同一官方源码。用 Python 3.14 和 upstream lock 安装，普通 pip editable 安装会碰到 Hermes 与 browser-harness 的 Pillow 版本冲突。上游 `[tool.uv].override-dependencies` 已定义解析办法。 [官方依赖定义](https://github.com/NousResearch/hermes-agent/blob/6a0d2d12815c0546b0bcaf05046e2fe3293f60aa/pyproject.toml)

```sh
git init hermes-src
git -C hermes-src fetch --depth=1 https://github.com/NousResearch/hermes-agent.git 6a0d2d12815c0546b0bcaf05046e2fe3293f60aa
git -C hermes-src checkout --detach FETCH_HEAD
cd hermes-src
uv sync --locked --no-dev --python 3.14
uv pip install --python .venv/bin/python 'aiohttp==3.14.5'
```

用该 venv 的 Python 运行 [verify.py](verify.py)，将 `--chatraw` 指向含 A 适配器的工作树或冻结副本，`--hermes` 指向上述 `.venv/bin/hermes` 的绝对路径。默认模式复验真实出站。诊断模式加 `--omit-empty-attachments-for-diagnosis`。逐阶段输出 JSON，记录适配器散列和原生错误码。

本机 Hermes 发现 Python 链接 SQLite 3.51.2，按上游实现使用 DELETE 日志模式。RM-01、真实模型凭据和模型服务、真实工具副作用与权限、图片和普通文件、Gateway 崩溃恢复均在本批验收之外。
