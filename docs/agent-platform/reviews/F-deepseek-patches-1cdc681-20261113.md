# F：DeepSeek 宿主 profile patches 小范围独立审查

**结论：`1cdc681258470524f40c4d57675adc9ac2b10a29` 无新增 P0/P1，增量可放行。现场图片成功仍需 A 在明确新建的会话中验收，本轮没有向 .98 发请求。**

审查集成快照 `0a805fc4a788fa84c211eeffa277eb71ada2f2ff`，目标四个文件与源提交完全一致；临时目录 `/private/tmp/chatraw-f-hostpatch-0a805fc.bsj1wn`。没有改业务或现场配置，没有重启服务，没有启动原生 runtime。

|边界|独立检查|
|---|---|
|宿主专用|`patches` 只出现在 validate_config 的宿主字段中，settings_schema 不含它且 additionalProperties=false。实际 Runtime.set_settings 提交 patches 返回400，未把宿主路径写成网页设置。|
|路径与类型|D 的定向单测通过：接受绝对路径字符串列表，复制列表；拒绝 None、bool、单字符串、相对路径、NUL 和非字符串元素。无需在无 I/O 的配置校验中打开文件。|
|SDK 最终参数|对真实 SDK0.2.2rc2 仅构造对象和启动参数：省略/空列表均保持默认空 tuple；两个路径按顺序成为 tuple，再按原生逻辑生成 `--profile sdk --patch … --patch …`。macOS 的 `/etc` 经 SDK resolve 为 `/private/etc`，属于原生路径规范化。没有执行该启动参数。|
|既有会话冻结|受控 adapter＋真实 Runtime/SQLite 检查：宿主 v1 路径换为 v2 后，旧会话在公开 max_tokens 更新引发的 close/resume 边界仍用 v1，binding不变；新会话使用v2。没有回写旧宿主快照。|
|配置来源|adapter 仅透传管理员路径；没有将模型回答、图片识别文本或浏览器请求当作模型目录配置，没有写 native profile。|

证据：[路径校验](patches-1cdc681-evidence/path-validation.log)、[SDK构造及参数顺序](patches-1cdc681-evidence/sdk-construction.json)、[公开设置拒绝与冻结快照](patches-1cdc681-evidence/host-snapshot-boundary.json)、[输入校验值](patches-1cdc681-evidence/manifest.json)。

A 的 `31-deepseek-image-investigation.md`、`31-deepseek-image-evidence.json` 与 `32-deepseek-native-patch-handoff.md` 已读取：原生历史确有图片附件引用，已有 profile 为空目录覆盖；当时 request/header 使用真实模型名 RM-01 VLM 和8192预算，但没有配置视觉目录。模型文字回答仅是旁证，不能单独证明过滤或修复成功。

交接的配置格式与 D 的 SDK 原生测试一致：顶层 patch 数组，以 `id: llm-deepseek` 定位 provider，在 `config.models` 中声明 `id: RM-01 VLM`、`inputModalities: [text, image]`、`contextWindow: 262144`。保持模型真名、endpoint 和既有 max_tokens 设置，没有伪装模型或文本化 base64。D 新测试检查真正 SDK 发往本地模型替身的 image 内容块和非空字节；本轮只审查该测试，未另跑推理。

既有会话冻结的是**路径配置**，不是文件内容。因此沿用 A 的明确约定：文件放在工作目录外、普通 Agent 不可改写的位置；内容变更使用新版本路径，已引用文件保持不变。该约定下旧会话不追改，新图片验收不得冒充旧会话恢复成功。本轮未验证尚待 A 管理的现场 patch 文件权限或新的随机像素挑战结果。

B 空详情修复、Chrome109/WebKit和主容器派生镜像不在本轮扩展审计范围；仍采用各 owner 已交付的证据。
