# DeepSeek 最终总结前的无生成渲染核对

2026-11-14。`.98` 为 vLLM `0.21.1rc1.dev104+g301d98647`。D 用原生 Harness `0.2.2rc2` 的 `deriveMessages` 和保存的请求头重建了 103 号会话中、seq 54 后的 Chat Completions 请求，出站体由本地接收端捕获。原回合现场 HTTP 字节仍未回录。原生执行证据见 `836822cc94c62712cd6b68013463e9265cea5572` 中的 `handoff/rm01-deployment-20261113/103-deepseek-v2-allow-native.json` 和 `107-deepseek-v2-result-pairing.json`。

原生重建体加 `temperature: 0` 得到 control。explicit-exit0 仅在 `/messages/8/content` 的 `(no output)` 后追加一行 `[exit code: 0]`，对应同一获准调用的原生 job 结果。两组均保留 31 个工具、8192 输出预算、`enable_thinking: true` 和流式请求设置，有效采样参数相同。

两组经 `.98` 的 `/v1/chat/completions/render` 和 `/detokenize` 后，7 组调用参数和结果文本逐项按原顺序保留，6 段助手 `reasoning` 完整保留。模型提示中同时可见获准重试参数、成功结果、助手原文 “The approved run completed. Let me verify the actual result:” 及后续读回内容。调用 ID 在出站 HTTP 中逐项配对，模板通过顺序呈现调用和结果。两份解码提示的唯一文本差异是成功工具回执内新增的退出码行，提示长度由 14,454 增至 14,462 tokens。

## SHA-256

请求按原始文件字节计算。Token IDs 按紧凑 JSON 数组计算，解码提示按 UTF-8 文本计算。

```text
reconstructed request  18dc97860fd6498f2e4e91fce18359ada52ed6bc29f322833e93344baaa3e11d
control request        1ebfe6d08f93d611d430f6cacb72971734445f2110b628dfe98477f702da4c73
control token IDs      920c9f769a4c13b133a050e6f055f995ca5a9bd857827c29b786b5d9845889d2
control decoded prompt 42a6ec1ef1ce92ed0e772076c5f4e2cb69821d4242a595cf4148460aa012f19b
explicit request       1047507976b2edb230821200cbeac9e001babfb9f804cbfa68cdaf770b37913b
explicit token IDs     1d3321206bc240bea994f4a9c3049ca1ee566f45b062e95caa3faec72c3db804
explicit decoded prompt c2a0d59b8caeab86ae6f5a4cf98121d49eb1b51d92bb41b271bd8075e791c093
```

[复核脚本](verify-deepseek-summary-render.py) 接收服务地址、D 的受限重建请求目录和 103 号原生执行记录文件。脚本只访问 `/version`、`/render` 和 `/detokenize`，输出哈希与计数。原始请求、解码提示和历史 `reasoning` 正文均留在受限证据范围内。本组生成和工具执行均为 0，结论限于两份重建请求的渲染，退出码对最终总结的影响需由生成对照另行判断。
