# .98 DeepSeek 工具空参数的协议定位

2026-11-14。现场服务为 vLLM `0.21.1rc1.dev104+g301d98647`。`/v1/models` 返回模型服务名 `RM-01 VLM`，模型路径末段为 `Qwen3.8-27B-NVFP4`。具体权重来源、模板文件及启动时选用的解析器未核实。原生 DeepSeek SDK 和 Harness 为 `0.2.2rc2`。[vLLM 模型目录 `models/serving.py` 60–73 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/openai/models/serving.py#L60-L73)

**Thinking 声明未传到 .98 的实际模板，是本次空参数复现的一个接入原因。** 同一请求只增加 `chat_template_kwargs.enable_thinking=true` 后，模型生成从行内赋值改为模板要求的参数标签，Messages 和 Chat Completions 均恢复完整的 `bash` 参数。

## 固定版本的请求和响应映射

- DeepSeek Harness 默认发 `thinking: {type: "enabled"}` 和 `output_config: {effort: "high"}`。vLLM `301d98647` 的 Messages 请求模型未声明这两个字段，转换也未读取它们。`chat_template_kwargs` 直接传入底层 Chat 请求。历史消息中的 `thinking` 内容块另行转换为 `reasoning`。[Harness `serialize.ts` 147–156 行](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/llm/llm-deepseek/src/serialize.ts#L147-L156) · [vLLM `protocol.py` 103–130 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/anthropic/protocol.py#L103-L130) · [`serving.py` 185–229 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/anthropic/serving.py#L185-L229)、[335–360 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/anthropic/serving.py#L335-L360)
- `tools[].input_schema` 映射为 `tools[].function.parameters`。请求带工具时，缺省 `tool_choice` 会补成 `auto`，可排除它是本次空参数的原因。[vLLM `serving.py` 377–431 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/anthropic/serving.py#L377-L431)
- Messages 非流式把 Chat 的 `message.tool_calls` 转为 `tool_use`，参数经 `json.loads` 写入 `input`。流式起始块固定发 `input: {}`，参数从 Chat 的 `delta.tool_calls[].function.arguments` 转为同一块的 `input_json_delta.partial_json`。流式空参数须在块结束后检查完整增量。[vLLM `serving.py` 473–507 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/anthropic/serving.py#L473-L507)、[718–791 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/anthropic/serving.py#L718-L791)

## 现场证据

无生成检查使用 `.98` 的 `/v1/chat/completions/render` 取 `token_ids` 和有效采样参数，再经 `/detokenize` 读模板。合成 `bash` 请求经 `/tokenize` 返回相同 token IDs。实际模板要求 `<tool_call>`、`<function=…>` 和 `<parameter=…>`，默认助手前缀已闭合 `<think>`。完整对照中的 Chat 实际推理 prompt IDs 与对应 render 逐项一致。[vLLM `render/serving.py` 120–183 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/serve/render/serving.py#L120-L183) · [`tokenize/serving.py` 68–121 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/serve/tokenize/serving.py#L68-L121)

| 对照 | 同一次 Chat 生成的原始 token | 两端结构化结果 |
| --- | --- | --- |
| 原请求经等价转换，`temperature=0`、31 工具、8192 输出预算、非流式 `auto` | `<function=bash>` 内是行内 `description="…" command="…"`，缺少 `<parameter=…>` | Chat `arguments="{}"`，Messages `input={}` |
| 仅增加 `chat_template_kwargs.enable_thinking=true` | `description` 和 `command` 均使用完整的 `<parameter=…>` 块 | 两端均返回同一份完整 `description` 和 `command` |

该开关同时打开助手前缀中的 `<think>` 并加入模板内置的 `xhigh` 提示。因果结论限于这次模板模式切换。`xhigh` 来自模板，SDK `output_config.effort=high` 的映射仍未实现。证据归档于提交 `4eb59e33993803629ad1fef60a9575843286bfbd` 的 `handoff/rm01-deployment-20261113/92–98`，其中 95 和 97 号 JSON 记录请求散列、采样和原始生成 token，96 和 98 号文档记录定位过程。

本组只观察 HTTP 输出，工具执行数为 0。结论覆盖这份固定请求的非流式复现。G05 仍待原生流式审批验收，历史其他空参数案例仍需各自的原始响应证据。
