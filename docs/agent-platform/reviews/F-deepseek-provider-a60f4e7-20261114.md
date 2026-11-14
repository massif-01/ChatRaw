# F：DeepSeek 宿主 provider 独立审查

提交：`1a03bdc4cd5da4074a4f0939d6e6e1a86ff7970c` + `a60f4e700f8c8e1373c10c6772e2d6ad27825238`。2026-11-14。

**结论：限定范围内未发现阻塞部署的 P0/P1，可交 A 部署版本化 v2 宿主 patch，并开展真实公开拒绝／单次允许验收。G05 仍未因本轮本地验证而关闭。**

|检查|结果|
|---|---|
|宿主边界|provider 仅 validate_config 接受，限 1–128 字符路由名；公开 schema 无此字段。真实 Runtime.set_settings 提交 provider、patches、baseURL、api_key 均返回 400。草稿中网页可编辑 provider 的表述已删除。|
|旧配置与默认路由|真实 Runtime/SQLite 重启检查：旧 binding/base_config 不变，旧 v1 路径及省略 provider 保持；新会话才取 rm01-qwen/v2。真实 SDK 默认初始化仍选择 deepseek-official，旧原生会话恢复仍走 Messages。|
|原生路由|真实 SDK 0.2.2rc2 本地接收端验证 Chat Completions、high/off → enable_thinking true/false、8192、31 个工具名称；未将自定义路由冒名为 deepseek-official。|
|审批与权限|源码 AST 比较仅 validate_config/probe/_make_harness 三方法变化；问答、审批、取消、执行、恢复方法未变，_make_harness 的 interactive callbacks/approval_requests 未变。新路由真实 SDK 测试显示完整长 command/cwd，拒绝未写，单次批准才写。|
|图片、压缩、恢复|接收端收到可解码图像字节；原生 compact 经相同路由生成摘要，恢复同一 native session ID 后请求包含持久摘要及早期标记。此为原生 SDK + loopback 模型证据，不代表真实模型质量。|
|健康状态|自定义 provider 初始化成功可 ready，但认证与模型请求明确 not_checked；有无官方 key 均不会伪称已鉴权，probe 无模型 HTTP 请求。默认路由原凭据检查保留。|

F 复现：[15 项定向测试全通过](provider-a60f4e7-evidence/targeted-tests.log)（13 项协议、2 项原生），另加[宿主冻结快照检查](provider-a60f4e7-evidence/host-snapshot.json)。[快照检查源码](provider-a60f4e7-evidence/host_snapshot_check.py.txt)使用 root `4eb59e33993803629ad1fef60a9575843286bfbd` 临时归档，仅覆盖本次 D adapter。[方法变化核对](provider-a60f4e7-evidence/source-boundary.json)、[版本与散列](provider-a60f4e7-evidence/manifest.json)。SDK 退出仍有既有管道 ResourceWarning，不将通过结果扩大为一般资源无泄漏保证。

D 的 Linux 离线[出站记录](provider-a60f4e7-evidence/D-linux-provider-wire.json)和[原生恢复记录](provider-a60f4e7-evidence/D-linux-provider-resume.json)亦已只读核对；出站记录中的 error 来自故意返回 400 的本地接收端，仅用于证明请求。其冒名路由探索项不属于本次提交 patch。F 未重复运行 Linux 或现场测试。

部署边界：保留旧 v1 文件，将 v2 安装为独立且普通 Agent 不可写的文件；仅新会话应用宿主 provider/patch。**公开 reasoning_effort 会覆盖宿主默认值，验收前应核对新会话有效值为 high。** 没有必要修改 .98、SDK、权限或审批回调，也不需要新增代理或商业密钥。

A97/98 支持 thinking 模板选择是固定请求错误格式的接入因素，不构成普遍工具可靠性保证。最终必须在真实 provider 上看到公开完整审批，并以文件实际副作用验证拒绝及单次允许；不得解析普通文本为可执行工具或跳过审批。本轮未调用 .98、未修改现场。
