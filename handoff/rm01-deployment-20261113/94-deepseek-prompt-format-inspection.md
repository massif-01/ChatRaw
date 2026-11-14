# 原始请求工具格式检查及D离线材料

2026-11-14。只读扫描已捕获请求的system、messages以及tools字段，没有新增模型请求。

三个字段均没有`<tool>`、`<parameter>`或它们的闭合/HTML实体形式；宽匹配tool/parameter前缀标签也没有命中。`tool_use`、`tool_calls`、`input_json_delta`字面量均为0。因此本轮非流式响应的XML样式工具标签，没有在这些Harness入站字段中发现对应格式示范。此结论不覆盖模型服务追加的chat template。

相关短片段：

- `system`：`you write a JavaScript script (the tool description documents the exact format)`。上下文是多Agent工作流JavaScript，不是XML工具调用格式。
- `tools[12].description`：`before a tool call that waits for their answer`。是文件交付时机说明。
- `tools[28].description`：`args — the tool call's args input, verbatim`。是JavaScript工作流钩子说明。

D的本地离线材料目录：`/tmp/chatraw-deepseek-wire-20261114-01`，目录0700、文件0600。

- `messages-stream.sse`：真实SSE实体1366字节，无HTTP头，SHA-256 `2619f4c23210e7836694b1f1afabfe9d4f3d61319108a434ae7ea0704e4b5f92`。
- `messages-nonstream.json`：非流式真实实体510字节，SHA-256 `726c188c0b3ae273bb961cf5bbccaef536ee2d8e10af4599f61b45ea40204c60`。
- `evidence.json`：92号脱敏证据副本。
- `README.md`：版本、Content-Type、来源和离线边界。

复制后逐项匹配.99采集SHA-256。未复制完整请求body、凭据或用户聊天。保持等待C提供确定的协议对照参数，不继续采样。
