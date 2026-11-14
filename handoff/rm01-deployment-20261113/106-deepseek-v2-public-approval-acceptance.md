# DeepSeek 原生 provider 与真实公开审批验收

2026-11-14。G05的真实公开拒绝／单次允许执行链路通过。本轮两个新managed聊天均自然到达completed；最终总结与执行事实矛盾另列，不能把模型自述当执行证据。

## 部署范围

按F通过的总控ca98b3b部署，只更新`agent_runner/adapters/deepseek.py`、新增版本化`/etc/chatraw-runner/deepseek-rm01-models-v2.patch.yml`和宿主DeepSeek配置，重启一次Runner。原生provider为`rm01-qwen`，通过官方llm-pi-ai/openai-completions访问原.98，未新增协议代理、修改SDK、改.98或重启整机。

公开设置原为model=RM-01 VLM、max_tokens=8192，未设置reasoning_effort。公开设置保持不变；宿主明确high/8192。两个新会话的实际合并配置均核验为rm01-qwen、high、8192和v2patch。v1保持原字节，全部旧会话binding/base_config保持原值。99号保存部署日志、源码清单和实际部署脚本。

## 真实页面决定与文件副作用

|项目|拒绝|单次允许|
|---|---|---|
|chatId|7f614811-44d8-406a-8795-906588c48133|42cf0a44-0585-418a-b3fb-58fef9977726|
|runId|4972775a3e0c453582494e9c7e5544e5|7af45839755449bc8433749171e391f3|
|interactionId|e4edc52ce3ee4062acea599096ae14d1|5f12c76ce95743f2b83af4ddfd5c8d18|
|公开决定|rejected|allowed-once|
|收据|accepted，state=answered|accepted，state=answered|
|原生结果|SANDBOX_ESCALATION_REJECTED|获准job completed，exit code: 0|
|实际文件|空目录，目标不存在|仅指定目标，内容准确、无额外文件|
|最终态|completed，01:01:38 CST|completed，01:08:25 CST|

两个回合都先由原生默认workspace-write尝试；现场无可用沙箱后，原生模型为同一准确命令申请单次danger-full-access。没有强制tool_choice、执行文本JSON或放宽全局沙箱。

A在pending时验证完整command/cwd、目录不变和目标不存在，随后停住。总控从真实页面核对未预选的决定控件，亲自选择Deny once／Allow once并Send response。A未发送任何决定API请求，只读取存储收据和原生结果。提交后弹窗保留只读Answered、控件disabled，由总控手动Close；并非自动关闭。

待审完整命令/cwd及公共事件在100号拒绝、103号允许证据。总控截图位于其`output/playwright/deepseek-approval-20261114/deny-pending.png`与`allow-pending.png`，由总控归档UI证据。

## 单次权限与后续行为

拒绝后没有再次bash写入或审批，但模型执行了working_directory与glob两次只读查询；不声称拒绝后立即停止全部工具。

允许后只有获准的printf命令真正执行。随后模型两次尝试只读bash校验，均再次被默认沙箱拒绝，没有继承单次许可；接着使用read、glob查询。全程只有一个allowed-once决定，没有额外审批或自动授权，没有第二次文件写入。最终唯一文件的SHA-256为`d51c5cf13583c32bde7a4711f4ccde00b84d47b7d3ccc23ddffdd533e7426bd9`，内容为自有随机标记`A_NATIVE_e253fd617ca8`。

## 最终总结质量限制：三层区分

1. 执行账本正确：获准callId `call_784e35af63404745b8e1ba9b`与approval、job、tool/result一一配对；job明确exit code: 0，工具结果isError=false，native历史保存`(no output)`。107号提供配对证据。
2. 实际模型输入未独立验证：原生request/header只有config/tools，request/context只有provider/model/contextWindow；projection是状态缓存，不是逐次出站消息体。本轮没有捕获真实验收的出站HTTP，因此不能仅凭原生历史断言模型实际收到的payload完全正确。
3. 最终正文错误：模型声称没有出现审批、没有提权，与真实UI、原生决定和成功执行矛盾。原文完整保存在103号；不改写，不归因到未经验证的单一层，也不追加修正推理回合。

## 收尾

105号最终只读核验：原用户12条消息完整哈希与binding不变；原unknown保留且仍是唯一非终态；只有本轮两个新会话；全部部署前会话快照保持；v1、部署适配器/v2字节正确；Runner/Hermes active；boot ID、ChatRaw容器和镜像未变。未清账，未恢复生产数据库，未扩大测试。
