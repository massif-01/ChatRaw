# thinking 单变量对照：工具格式与参数恢复

2026-11-14。只读诊断结果，未修改生产代码、Agent配置或.98服务；未执行工具、未提交审批，G05仍未验收。

## 对照不变量

紧邻95号对照，复用相同prompt、system、消息顺序、31个工具及全部schema、8192预算、temperature=0、stream=false、auto工具选择。Messages和等价Chat各只增加`chat_template_kwargs.enable_thinking=true`，去掉这个键后与各自基线body逐字段相同；没有改提示或强制命名工具。两条请求串行，各一次。

## 生成前的渲染核对

有效采样参数完全相同。prompt由9209变为9245tokens。模板变化只有：助手前缀不再预先闭合think；模板另加入其内置的`Reasoning effort is set to xhigh...`提示。实际Chat推理返回的prompt_token_ids与本组render逐项一致。

这不是声称仅开放think前缀就单独产生效果；受控变量是enable_thinking选择，模板的两处变化均属于它的结果。SDK原请求output_config.effort=high保持原值，现场模板出现xhigh不应误报为该字段已被正确映射。

## 结果

|观测|基线|enable_thinking=true|
|---|---|---|
|Messages工具输入|bash input={}|description与command完整|
|Chat工具参数|bash arguments="{}"|同一description与command完整|
|输出token数|两端均40|两端均94|
|Messages终止|tool_use|tool_use|
|Chat终止|tool_calls|tool_calls|
|推理内容|无独立thinking/reasoning|Messages有thinking块，Chat有reasoning|
|Chat原始工具语法|行内description="…" command="…"|模板要求的parameter块，完整闭合tool_call|

本组Chat同一次生成的原始工具后缀：

```text
<tool_call>
<function=bash>
<parameter=description>
Write and read diagnostic marker file
</parameter>
<parameter=command>
printf %s DIAG_FIXED_MARKER > diagnostic-marker.txt && cat diagnostic-marker.txt
</parameter>
</function>
</tool_call><|im_end|>
```

Messages和Chat均自动选择bash并保留上述两项参数；没有解析或执行文本工具、没有绕过SDK审批。

## 因果边界与交接

本组受控对照支持：SDK原本要求的thinking语义未落实到现场模板，是这份固定请求产生错误工具格式的一个可修复接入因素。按模板实际开关落实后，原始生成语法与两种协议的结构化参数同时恢复。不能由单组推断所有提示都可靠，也未完成原生流式审批链路验收。

完整raw HTTP/entity/body仍在.99受限目录`/home/rm01/chatraw-diagnostics/deepseek-wire-20261114-01/thinking-control/protocol-compare`；97号JSON保存哈希、原始生成token IDs、工具后缀、字段不变量及采样核对。

本组实模型请求2条，累计诊断6条，均串行；工具执行0。等待D提出原生正式接线方案后再由总控决定生产改动；本轮到证据交付为止。
