# DeepSeek 原始请求与响应：首轮定位

2026-11-14，北京时间。仅完成原始证据采集，未修改产品代码或配置，未执行模型提出的工具命令，未批准或绕过任何审批。G05仍为NOT_VERIFIED。

## 方法和边界

现场SDK/runtime均为0.2.2rc2。专属home、workspace、虚拟API key和loopback接收器捕获原生SDK首条Messages请求；接收器返回明确400诊断错误，不连接模型。SDK退出后用无SDK、无工具执行器的socket客户端串行发送两条HTTP请求，逐字节保存HTTP原始响应，另保存去除HTTP分块传输编码后的原始实体。没有记录真实凭据，没有操作用户聊天、生产Agent配置或.98服务。

原始文件仅位于.99的0700目录 `/home/rm01/chatraw-diagnostics/deepseek-wire-20261114-01`；原始body/HTTP响应为0600。仓库仅保存脱敏字段、必要响应片段与SHA-256，见92号JSON。捕获、重放和提取脚本也保存在该受限目录，未加入产品路径。

## 观测

SDK实际请求为POST /v1/messages，86433字节，31个工具；bash schema必填description、command，预算8192，thinking enabled。原样重放的body SHA-256为 `32df36c6cdf2ab3c2235de9c2ffa4627a5ce19291e460f8f13a2e25eeafa8ef3`。

|请求|唯一对照目的|实际原始响应|
|---|---|---|
|1：SDK body原样，stream=true|检查SDK解析前是否已有工具调用/参数|HTTP200；只有text块，无tool_use、无input_json_delta；stop_reason=end_turn|
|2：只改stream=false|检查非流式Messages是否提供结构化工具调用|HTTP200；content仍是text，内含`<tool>bash ... <parameter>{description,command}</parameter></tool>`文字；stop_reason=end_turn|

两次响应实体SHA-256分别为 `2619f4c23210e7836694b1f1afabfe9d4f3d61319108a434ae7ea0704e4b5f92` 和 `726c188c0b3ae273bb961cf5bbccaef536ee2d8e10af4599f61b45ea40204c60`。二者未经SDK解析，也没有把文字JSON变成工具调用。诊断marker文件不存在。

## 结论与下一步依据

这两条请求的结构化调用缺失发生在SDK之前。因此不能把本次现象归咎于SDK把完整参数解析成空对象；同样也不能把SDK历史`tool/call {}`冒充原始模型输出。本轮未复现历史空参数tool_use，不能声称已排除SDK的所有问题。

目前无法区分模型生成、模型chat template/工具解析器、Messages协议转换三者。两次采样没有固定随机性，不能用正文差异证明stream字段导致故障。下一步应结合C对.98实际模板/解析器/转换代码的核验，以及D对原生decoder的核验，选定单个可区分假设的协议对照；不继续更换提示抽样，不先改生产接入。
