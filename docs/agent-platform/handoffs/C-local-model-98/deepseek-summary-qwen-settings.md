# DeepSeek 总结异常的 Qwen 设置核对

2026-11-14。`.98` 为 vLLM `0.21.1rc1.dev104+g301d98647`，服务名 `RM-01 VLM`，`/v1/models` 报告的本地权重目录末段为 `Qwen3.8-27B-NVFP4`。同一合成多轮工具历史在现场、Qwen 官方模板和 NVIDIA 量化版模板的渲染结果逐字节相同。此核对覆盖样本的模板行为，现场权重发布方、精确 revision 和模板文件哈希仍未确认。[Qwen 官方模板 `3756181`](https://huggingface.co/Qwen/Qwen3.8-27B/blob/37561816e66b5b9153b1b64c10968c18c1e6f4a0/chat_template.jinja) · [NVIDIA 模板 `482ca0f`](https://huggingface.co/nvidia/Qwen3.8-27B-NVFP4/blob/482ca0f3832238542f8f5295dde86b5f22711d80/chat_template.jinja)

## 官方规范与现场有效设置

- **档位。** Qwen3.8 原生 `reasoning_effort` 接受 `xhigh`（默认）、`medium`、`low`。原生 Chat API 使用顶层字段，vLLM `301d98647` 也会保留 `chat_template_kwargs.reasoning_effort`。Harness `0.2.2rc2` 的 `rm01-qwen` v2 配置将其 `high` 选项用于发送 `enable_thinking=true`，出站没有显式原生档位，现场采用默认 `xhigh`。[Qwen 模型卡](https://huggingface.co/Qwen/Qwen3.8-27B#api-usage) · [vLLM `protocol.py` 448–465 行](https://github.com/vllm-project/vllm/blob/301d986473a0ffc1df563422e01eac4a1efd59e0/vllm/entrypoints/openai/chat_completion/protocol.py#L448-L465)
- **采样。** 原始总结前重建请求省略采样字段。现场 render 的有效值为 `temperature=1.0`、`top_p=0.95`、`top_k=20`、`min_p=0.0`、`repetition_penalty=1.0`、`presence_penalty=0.0`，逐项符合 Qwen3.8-27B 官方 thinking 建议。输出预算为 8192。`temperature=0` 是 109–112 号诊断对照加的固定条件。[Qwen 采样建议](https://huggingface.co/Qwen/Qwen3.8-27B#best-practices)
- **历史推理。** 官方默认保留历史 thinking。`preserve_thinking=false` 只省略最后一条真实用户消息之前的 thinking。本例六段推理均在该消息之后，切换此字段后，现场提示 token IDs 和有效采样逐项相同。[Qwen 保留规则](https://huggingface.co/Qwen/Qwen3.8-27B#disable-preserved-thinking)

## 无生成渲染证据

103 号原生会话在 seq 54 后、最终总结前，由 `deriveMessages` 和保存的 header 重建请求，再由本地接收端捕获序列化 HTTP body。原回合现场 HTTP 字节未回录。对同一原始重建请求只设置 `/chat_template_kwargs/reasoning_effort`，用 `.98` 的 `/v1/chat/completions/render` 和 `/detokenize` 核对。五组均返回 HTTP 200，均保留 6 段历史推理、7 条工具结果。`high` 在现场没有独立的渲染效果，实际归一化层未核实。

| 模板字段 | 请求 SHA-256 | 提示 token 数 | Token IDs SHA-256 | 模板档位指令 |
| --- | --- | ---: | --- | --- |
| 省略 | `18dc97860fd6498f2e4e91fce18359ada52ed6bc29f322833e93344baaa3e11d` | 14,454 | `920c9f769a4c13b133a050e6f055f995ca5a9bd857827c29b786b5d9845889d2` | `xhigh` |
| `high` | `707298fba57afb038eef60f4add087187068518492a072f6114937094482d599` | 14,454 | 同省略 | `xhigh` |
| `xhigh` | `ff39150c0eb7c49e32d757fa90a181ebfa9c18fb8785ef6c6f6eb724ae671a3e` | 14,454 | 同省略 | `xhigh` |
| `medium` | `1c4828c1ebdb2d91d9805446988932deded2ae61364be6af030aa2e8fd343461` | 14,416 | `9f562db08db837e5a57fd669b2c32695d5cfeb8f3cf61f93d1accd7c83940b9b` | 无 |
| `low` | `4dfe8381860a5c48d5b50fe6da9b59e8448336ec39c25d8973154ab9fae8a7fc` | 14,442 | `40293c4603ebbae4655906daf4dc957c4a24ec826a5afbd9d2e58ab8e366ecdf` | 简短推理 |

请求按原始字节计算 SHA-256，token IDs 按紧凑 JSON 数组计算。省略、`high`、`xhigh` 的解码提示 UTF-8 SHA-256 也相同，为 `42a6ec1ef1ce92ed0e772076c5f4e2cb69821d4242a595cf4148460aa012f19b`。规范和渲染检查均无生成、无工具执行。

**处置结论。** 显式发送 `xhigh` 在此请求中不会改变模型提示，现有证据没有给出调整档位、采样或历史回送规则的依据。现场工具执行和审批事实已经验证，当前模型服务仍不能可靠归纳该历史中的批准与成功结果。补入成功退出码和审批事实的对照未得到正确总结。最终总结仍未修复，待候选模型替换后复验。执行证据见 `836822cc94c62712cd6b68013463e9265cea5572` 下的 103、107 号记录，生成对照见 `handoff/rm01-deployment-20261113/109–112`。
