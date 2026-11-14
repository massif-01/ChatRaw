# DeepSeek 原生模态部署、PNG 与压缩记录核验

2026-11-13。A 根据总控单独授权完成现场更新与一次真实 PNG 挑战；压缩记录核对均为只读，没有重新发送压缩或续接请求。模型窗口现已释放。

## 部署与会话边界

现场 `agent_runner/adapters/deepseek.py` 更新至 root 提交99616b9a289f30876aa949a174adccc25aefef72，SHA256为60daa18d32f38d9999970f2a2a1b71e4b227193308ed14c49afb2c4873840391。未部署待审 Codex e889688；Codex文件哈希仍为a7d89c869f46a83d2f30fa88a2fd80a7b346773f1ae0776139edd88c9f569b2b。

创建稳定版本文件 `/etc/chatraw-runner/deepseek-rm01-models-v1.patch.yml`，root:rm01、0440，只读内容为 llm-deepseek 的 RM-01 VLM 模型目录，inputModalities=[text,image]、contextWindow262144。Runner宿主config增加patches路径；公开max_tokens仍为8192。原config备份为 `/etc/chatraw-runner/config.pre-deepseek-patches-v1.json`。

重启前全局唯一非终态为旧Codex测试unknown，没有running/waiting/queued用户任务。核对现有代码：未知回合有stop_requested，恢复路径不会重发prompt或猜测终态。必要的Runner服务重启后该run仍unknown，恢复机制将错误记录由codex_tool_stop_unverified更新为recovery_unavailable（last_seq9→13），没有强制完成、取消或清除记录。C此前取证已完成；未直接操作用户原聊天。用户原聊天全部消息哈希和公开绑定前后完全一致。

所有既有DeepSeek会话的binding与base_config逐项比对一致。新PNG会话明确拥有新的patch路径快照，没有回填旧会话。主ChatRaw仍为2ba163e-ui镜像，Hermes未重启；未改.98或部署协议代理。

证据：39版本及更新前快照、40安装脚本/日志、41原快照比对输入、48用户聊天与最终状态。

## 新会话真实PNG挑战：PASS

重用D的既有公开API验收脚本，仅执行一次deepseek image，新建聊天9f29d3b8-1368-4adc-b6e1-4b6a7b26ae87。Runner session55512bdd173b496f8cc9be631380acbc，native session session-1e829c1aa4af44338cfdf30b60ad618a，run c87836f4a345490aa8e5f4eb5d9a290f。

PNG仅在像素中编码随机六位数719734，上传文件名D-vision.png，提示文本没有答案。PNG SHA256为b4b92ccee26c6ab81ff2dc8208ab1b89ac7b52412ad7d1c076e8b30f11d55b52。模型返回恰好719734，无工具调用，run=completed。

原生user/message seq8包含image/jpeg图片块（官方附件规范化），284×80、3841 bytes，attachmentId为sha256:d6391091093a06a5be7072b3448e14f6ec47896537d94506e96a688856a29a0a；request/header seq12为RM-01 VLM、maxTokens8192；原生assistant/message seq16返回719734，turn/end seq18为completed。新session的base_config包含版本化patch路径；旧失败图片会话原样保留。

这是公开API上传→原生图片块→真实模型像素答案的证据；未抓取原始HTTP请求体，不声称PNG原始字节未经原生规范化直接上网。

证据：[挑战文件和公开事件](42-deepseek-image-patched/result.json)、[原生图片记录](45-deepseek-image-native.json)、[交叉核验](48-image-verification.json)。D脚本原始outcome为native_evidence_pending，A补齐原生证据后在48号文件判PASS，不改写D脚本原始输出。

## D四种Agent压缩：原生操作已确认

|Agent|原生证据|身份与后续|
|---|---|---|
|Claude|同一JSONL中手动compact_boundary，preTokens12035→postTokens3196；紧随其后的isCompactSummary包含D-9A303258A7。|native session5b81ece9-6e27-44bf-8179-e5d4744deb53；D后续同聊天准确回显标记。|
|Pi|同一transcript中compaction ff225977，tokensBefore18817，firstKeptEntryId800f140f；持久摘要包含D-BE0B87B194。|native session01a1d537-c79a-70c9-a477-50a93b2aaaaf保持一致；后续标记匹配。|
|DeepSeek|原生command/run seq37→compaction/start38→summary40→end42→command/done43；done.kind=success并指向summary seq40，摘要包含D-F171D93450。|native session session-1625a242811e4e3abbc5166a0556e39b保持一致；后续标记匹配。|
|Hermes|state.db有active压缩摘要message28，_compressed_summary=1；旧10条消息被置为inactive/compacted，保留前段和尾部。不是noop或仅模型自述。|逻辑和物理session均为local-eb7920a203370c9e127f1dc4c30f8a8d004466af8691e1cfe5bc89b5ca7f122d；早期D-CC84954169位于保留首段，后续message34匹配该码。|

四项原生边界/成功回执的时间均落在对应Runner compact run的created_at与updated_at之间，且D提供的后续同会话连续性结果匹配。Hermes摘要本身没有早期码，该码由保留首段承载，不能描述为“摘要保留了码”。本例没有更换Hermes物理session。

证据：[绑定与时间窗口](43-compact-bindings.json)、[Claude/Pi/DeepSeek记录](44-compact-native-three.json)、[Hermes原生库记录](46-hermes-native-compact.json)、[最终逐项核验](47-native-compaction-verification.json)。

## 残余限制

- Codex旧工具停止run仍unknown并占活动位；本轮没有部署C修复，也没有把started存在/late缺失当作终态证明。
- Codex压缩后续接被.98模板拒绝的问题未在本轮修复；未安装兼容代理或修改模型服务。
- 旧DeepSeek会话保留旧宿主快照，不自动获得新增图片声明；使用该模态配置需要明确新建会话。
- DeepSeek工具执行中停止仍未完成D的验收条件。本轮只补PNG与压缩原生取证，不把基础生成停止通过扩大为工具中途停止通过。
- 未执行整机重启、断电恢复或额外模型负载。最终真实running/waiting为零，仅保留已知Codex unknown，/ready正常。
