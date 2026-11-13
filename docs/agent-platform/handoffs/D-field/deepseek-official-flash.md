# DeepSeek 官方 Flash 隔离验收

## 原生配置

在隔离 Runner 中使用以下配置。路径换成此次验收专用的绝对路径，目录由 Runner 账户管理。通过隔离服务环境提供 `DEEPSEEK_API_KEY`，Pi 的 `PI_CODING_AGENT_DIR` 指向此次新建的 agent 目录。Harness 使用官方 Messages 根地址 `https://api.deepseek.com/anthropic`。若隔离服务继承了 `DEEPSEEK_BASE_URL`，在隔离服务中将其设为该地址。Pi 内置 `deepseek` 路由使用 `https://api.deepseek.com`。

```yaml
agents:
  deepseek:
    dsh_home: /absolute/isolated/deepseek-sessions
    provider: deepseek-official
    model: deepseek-flash
    reasoning_effort: high
    max_tokens: 8192
  pi:
    executable: /absolute/pinned/pi
    session_root: /absolute/isolated/pi-sessions
    provider: deepseek
    model: deepseek-flash
    thinking: high
```

DeepSeek SDK 与 runtime 均为 `0.2.2rc2`，Pi 为 `1.5.2`。两个版本都原生登记了 Flash 的视觉和推理能力。无需模型注册 patch 或 Pi `models.json`。首轮总结复验沿用旧案例的 8192 输出上限。收到长度终止时登记为未获得完整总结。[官方型号与价格](https://api-docs.deepseek.com/quick_start/pricing/) · [Harness 模型目录](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.2/packages/llm/llm-deepseek/src/models.ts) · [Pi 1.5.2 模型目录](https://unpkg.com/@earendil-works/pi-ai@1.5.2/dist/providers/data/deepseek.json)

## 现场验收

先从空历史新建 DeepSeek managed 会话复验审批后总结。随后按隔离批次完成五个 Agent 和普通聊天验收。下表适用于 DeepSeek 和 Pi，每项记录公开 chat/session/run ID。原生记录由现场执行方按同一会话、调用 ID 和时间关联。

| 项目 | 验收证据 |
|---|---|
| 工具调用及允许一次 | 用新 managed 工作目录下的唯一文件名。要求原生 Bash 执行精确命令，写入前校验 `pwd -P`，用 `set -C` 防止覆盖，让成功写入无 stdout。核对公开审批的完整命令与绑定目录。DeepSeek 还应显示实际工具 cwd。回复一次允许后，查对应原生调用、审批、结果和文件内容。最终文本须如实说明获准和写入结果。若此前存在一次沙箱失败，也须正确归属到对应调用。模型没发起工具、没出现审批或没给出完整总结，分别记录实际停留点。 |
| 拒绝 | 使用另一枚唯一标记，检查完整命令后拒绝，核对对应调用的拒绝结果、文件始终缺失及最终文本。任何再次提出的不同命令独立核对。 |
| 运行中停止 | 用独立受控命令写 `started`，等待 30 秒后才写 `late`。看见 `started` 及工具开始后取消，等待已确认终态，经过完整延时仍无 `late`。Pi 以原生 `agent_settled` 为结算依据，DeepSeek 对照原生 tool abort、turn 结束及所属进程退出。 |
| 恢复与压缩 | 先建立包含随机识别码的历史，关闭并重新打开同一绑定，确认识别码及原生身份。执行原生 compact，留存 Pi `compaction` 或 DeepSeek `compaction/summary` 及完成事件，再确认同一绑定能复述识别码。 |
| 图片 | 将新的随机六位数仅编码在 PNG 像素中，通过 ChatRaw 上传。确认答案和数字一致，且没有用工具读取文件。关联上传记录及原生图像部分。Harness 可把 PNG 归一化为 JPEG 后走 Files 引用或内联，因此可核对归一化图像的哈希和引用关系。 |

总结复验可使用以下命令。替换绑定的实际目录和唯一标记后，将完整命令作为本次请求的一部分。DeepSeek 先正常调用 Bash，遇到沙箱不可用才请求对同一命令的一次授权。执行完成后请模型说明审批决定和实际写入结果。

```sh
test "$(pwd -P)" = '/absolute/managed/session' && set -C && printf '%s\n' 'UNIQUE_HEX_TOKEN' > 'flash-UNIQUE_HEX_TOKEN.ok'
```

已有 `verify.py` 的 `image`、`compact` 流程可指定本批隔离 `--base`。`stop` 中的 SSH 和 managed 目录对应旧 RM-01 环境，现场需按本批实际绑定核对标记与进程。[既有现场判据](README.md)

## 接收端证据与历史回送

- 用固定假凭据、本地回环接收端和原生程序验证。Harness `/anthropic/v1/messages` 在 `high` 发 `thinking.type=enabled` 和 `output_config.effort=high`，在 `off` 发 `thinking.type=disabled` 并省略 effort。请求保留 `max_tokens=8192`。Files 成功时引用实际上传的文件 ID，上传失败时内联同一归一化 JPEG。Pi `/chat/completions` 在 `high` 发 `thinking.type=enabled` 和 `reasoning_effort=high`，在 `off` 禁用 thinking 并省略 effort。接收端收到与输入 PNG 同 SHA-256 的图像字节。Pi 测试仅将内置路由的 `baseUrl` 改为回环地址。[官方 Messages](https://api-docs.deepseek.com/guides/anthropic_api/) · [官方 thinking 参数](https://api-docs.deepseek.com/guides/thinking_mode/)
- 通过 ChatRaw 的 DeepSeek 适配器、原生 SDK、真实本地 Bash 和假模型做了两次审批回环。接收端逐项确认 `tool_use.input.command` 等于公开审批的完整命令，且 `tool_use.id` 与 `tool_result.tool_use_id` 相同。拒绝的结果是 `is_error:true` 且文件缺失，允许一次的结果是 `is_error:false`、`(no output)` 且文件存在。正式复验用原生审批及进程记录和实际文件判定执行事实，再独立核对模型总结。`tool_result` 的 `is_error` 表示执行结果，审批决定由 Harness 原生审计记录。[Harness Messages 序列化](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.2/packages/llm/llm-deepseek/src/serialize.ts#L118-L128)
- 旧 seq54 重放带着 6 段原 Qwen reasoning，其中已经有错误自述。DeepSeek 的 Chat Completions 工具协议要求回送同一对话中模型返回的 reasoning。Harness Messages 仅在同模型且元数据有效时回送原生签名，跨模型或协议仍可能序列化已有 reasoning 文本。旧重放结果只说明该输入仍会得到错误总结。新官方会话从空历史发起真实工具调用和审批，旧记录完整保留供复盘。[官方工具回送规则](https://api-docs.deepseek.com/guides/thinking_mode/#tool-calls) · [Harness 签名校验](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.2/packages/llm/llm-deepseek/src/replay.ts#L33-L64) · [thinking 序列化](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.2/packages/llm/llm-deepseek/src/serialize.ts#L26-L38)

现有两套原生适配器测试共 9 项通过。官方认证、真实模型回复、Linux 副作用和全链验收由隔离现场批次确认。[本地接收端证据](evidence/deepseek-official-flash-loopback.json)
