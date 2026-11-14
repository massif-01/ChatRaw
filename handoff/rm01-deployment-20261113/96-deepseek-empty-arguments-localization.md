# 空参数已定位到原始生成格式

2026-11-14。依据C的vLLM固定版本转换方案，从92号捕获体生成一对非流式、temperature=0、8192预算、auto选择的Messages/Chat请求。原提示、system、消息顺序、31个工具及schema均保留，没有工具执行或服务配置修改。

## 无生成核对

先调用Chat render与detokenize。9209个prompt tokens；有效temperature=0、max_tokens=8192。渲染后的bash参数schema与SDK捕获schema逐项完全一致。模板要求`<tool_call><function=...><parameter=...>`；助手前缀为闭合think。Chat真正推理返回的prompt_token_ids与render逐项一致。

## 两条串行生成结果

- Messages：HTTP200，`tool_use name=bash input={}`，stop_reason=tool_use，输出40tokens。
- Chat：HTTP200，`function.name=bash arguments="{}"`，finish_reason=tool_calls，输出40tokens。
- Chat同一次生成的40个原始token经detokenize得到：

```text
<tool_call>
<function=bash>
description="Write and read diagnostic marker file" command="printf %s DIAG_FIXED_MARKER > diagnostic-marker.txt && cat diagnostic-marker.txt"
</function><|im_end|>
```

原始生成有description和command内容，但未遵循模板要求的`<parameter=...>`块，而是写成行内赋值。Chat侧已解析成空对象，因此这次空参数不能归因于Messages响应转换或SDK丢参。这是同一次Chat生成的token→解析结果证据；另一条Messages生成的相同结果只是独立佐证，不冒充同一次生成的跨接口跟踪。

本结论限定此对照，不声称覆盖所有历史失败，也不把文本恢复为可执行工具。已有SDK解码离线调查仍可独立完成。

## 交接

95号JSON记录精确body/HTTP/entity哈希、有效采样、原始40tokens及结构化结果；完整请求/响应仍在.99受限目录`/home/rm01/chatraw-diagnostics/deepseek-wire-20261114-01/protocol-compare`。

本组仅两条实模型请求；累计诊断四条，均串行，工具执行0。尚未执行thinking对照。下一候选是在完整请求只加`chat_template_kwargs.enable_thinking=true`，先render核对开放think，再单次观察；它用于验证SDK已声明thinking.enabled被当前转换器忽略这一语义差异，不改提示、工具清单或审批门槛。
