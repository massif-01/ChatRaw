# DeepSeek 本地 VLM 图片省略：只读调查

2026-11-13。未修改现场配置、服务、数据库或 .98，未启动原生进程、重启或发推理。

结论：有官方原生配置入口。当前问题是 `RM-01 VLM` 未被加入 DeepSeek provider 的图片能力目录，不是 Python SDK 完全不支持原生图片。无需伪装模型名、文本化 base64 或另加协议代理。

## 现场证据

总控给出的 `f6523c63113f450db6cfb2a394166bf7` 实为 Runner session ID；它绑定的 native session 是 `session-79f17d14b00249c18b580614fad63c37`。完整筛选记录见 [31-deepseek-image-evidence.json](31-deepseek-image-evidence.json)。

原生 `user/message` seq8 已保存图片引用：规范化为 image/jpeg，284×80，4774 bytes，attachment ID `sha256:8d35d061e637b42fd113eaa7de302accf7a5b52e3760f0487375babf5518af7b`。所以不能归因为浏览器或 Runner 丢失附件。原生 request/header seq12 选择 `provider=deepseek-official`、`model=RM-01 VLM`、`maxTokens=8192`。assistant/message seq16 回答图片因模型仅接收文本而省略，未给出挑战数字。

该 native home 的 `profiles/sdk/cordis.patch.yml` 只有注释和 `[]`；profile 由 `@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-sdk-app` 组成。现场 SDK 0.2.2rc2 的 `DeepSeekHarnessConfig` 明确包含 `patches: tuple[str, ...]`，client.py 611–616 将其转换为绝对路径的 `--patch` 参数，位于 `--profile sdk` 之后。ChatRaw 当前 `_make_harness` 没有传 patches，也未提供 models 模态配置。

## 官方实现依据

按项目 D 文档所引用的源码提交 `e8f7b93a344964de3dca1ace9e72b6e4d6de87cb` 核对：

- [model-info.ts](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/llm/llm-deepseek/src/model-info.ts)：用精确 model ID 查询 connection.models；找不到时明确返回仅 text 的 inputModalities。
- [config.ts](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/llm/llm-deepseek/src/config.ts)：模型目录支持 inputModalities，允许 text/image；省略该字段默认 text。也支持该模型的 contextWindow、maxTokens。
- [API-key provider 说明](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/llm/llm-deepseek-api-key/README.md)：非官方 endpoint 使用配置的 models，不从该 endpoint 自动获取模型目录，所以 `.98 /v1/models` 存在不能自动补齐模态。
- [Messages transport 说明](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/packages/llm/llm-deepseek/README.md)：未声明/仅文本模型收到附件占位文本，持久历史仍保留图片引用；图片模型走原生图片通道，Files 不可用时由官方适配器改用消息中的图片块，不是把 base64 当普通正文。
- [Python SDK 说明](https://github.com/deepseek-ai/deepseek-harness/blob/e8f7b93a344964de3dca1ace9e72b6e4d6de87cb/python/sdk/README.md)：原生 `$DSH_HOME/profiles/sdk/cordis.patch.yml` 是持久 profile patch；也支持 `DeepSeekHarness(patches=(...))` 的逐启动配置。

原生附件、空目录覆盖和模型回答与上述解析路径一致；本轮没有抓取原始 HTTP body，也没有修改配置后复测，因此“已修复图片识别”尚未成立。

## 给总控的最小方案（尚未实施）

候选官方配置为：

```yaml
- id: llm-deepseek
  config:
    models:
      - id: RM-01 VLM
        inputModalities: [text, image]
        contextWindow: 262144
```

继续保留已经通过公开 settings API 设置的 max_tokens=8192，模型 ID 和 endpoint 不变。

官方也支持直接编辑每个 native home 的 profile patch，但本次正式方案不回写既有会话文件。SDK profile 禁用了 HMR；既有会话保留冻结宿主配置，结构性 patch 仅用于后续新会话。

覆盖后续所有会话的正式方案，建议 D 为 adapter 增加仅宿主管理的原生 patch 路径透传，在 `_make_harness` 的 probe/create/resume 路径一致传入已审查的绝对路径，现场由 A 管理共享只读 YAML。该路径涉及原生执行配置，应留在 Runner 宿主配置，不能开放为网页普通设置。这样不需要复制每个 session 的配置，也不改变用户原模型名称。具体接口及安全校验由 D/root 决定，本轮只给方案。

验收必须继续使用无文字答案泄漏的随机像素挑战，在明确标注的新会话中确认真实图片内容抵达模型并返回正确数字。保留旧失败会话及其原 native ID，不将新会话伪装成旧会话恢复。若正式方案暂不实施，当前 DeepSeek/RM-01 配置的图片能力应明确显示不可用，不能仅凭通用 images=true 判通过。
