# 给 D / root：DeepSeek 原生模型模态 patch

状态：仅交接，未部署。A 未改现场配置、重启服务或发推理。以下 `patches` 是建议的 Runner 宿主字段名，由 D 实现后确定；Python SDK 参数名称与类型已核实。

## 接口和格式

Runner `agents.deepseek` 宿主配置建议增加可选 `patches: list[str]`；元素是受控的绝对文件路径。例如：

```json
{
  "agents": {
    "deepseek": {
      "dsh_home": "/var/lib/chatraw-runner/deepseek",
      "patches": ["/etc/chatraw-runner/deepseek-rm01-models.patch.yml"]
    }
  }
}
```

此路径仅作部署方案，不代表文件已经存在。YAML 文件内容为官方 Cordis 顶层 patch 数组：

```yaml
- id: llm-deepseek
  config:
    models:
      - id: RM-01 VLM
        inputModalities: [text, image]
        contextWindow: 262144
```

已配置的公开 `max_tokens=8192` 保持原样；模型名称和 .98 endpoint 不改。不要将模型目录或任意 patch 路径加入网页 `settings_schema`。

现场 Python SDK 0.2.2rc2 的 `DeepSeekHarnessConfig.patches` 类型是 `tuple[str, ...]`，默认 `()`。调用形式：

```python
DeepSeekHarness(
    profile="sdk",
    patches=("/etc/chatraw-runner/deepseek-rm01-models.patch.yml",),
    # 其余既有参数原样传入
)
```

SDK client.py 611–616 对每项执行 expanduser/resolve，按顺序生成 `--patch ABS_PATH`，放在 `--profile sdk` 之后。官方定义其顺序晚于 profile/home patch。Runner 应在宿主配置边界校验绝对路径列表；省略字段时保持原调用默认行为，不补写任何模型目录。

## 会话边界

- probe 与新建会话使用当前宿主配置；已有会话恢复使用其冻结的宿主配置快照。
- 宿主配置新增 patch 不得反向覆盖旧快照、回写旧 native profile 或静默更换旧会话 ID。
- 该 patch 仅对明确新建的验收会话生效。旧 PNG 失败记录保留，不将新会话结果计为旧会话恢复成功。
- 已被会话引用的 patch 文件内容保持稳定；后续改版使用新文件路径，避免旧冻结快照指向被覆盖的内容。
- 正式 patch 文件由 A 在总控部署窗口管理。D 当前会话和用户原 Codex 会话不受本交接操作影响。

## 已观察的过滤证据

Runner session `f6523c63113f450db6cfb2a394166bf7` 绑定 native session `session-79f17d14b00249c18b580614fad63c37`。

原生 user/message seq8 含 image/jpeg 附件引用，284×80、4774 bytes；request/header seq12 选择 RM-01 VLM、maxTokens8192；assistant/message seq16 明确称图片因仅文本模型而被省略。原生 profile patch 是空数组。附件引用和模型回答见 [筛选原始记录](31-deepseek-image-evidence.json)，判定路径和源码链接见 [调查报告](31-deepseek-image-investigation.md)。当前没有配置后真实 PNG 通过证据。

官方 `modelInfo` 对未列入 models 的模型返回 text-only；配置 schema 支持 inputModalities=[text,image]。自定义 endpoint 不自动从 /v1/models 补齐模态。SDK 原生图片通道在 Files 不可用时有图片块内联路径，无需把 base64 当普通正文或安装转换代理。

## 最小验收要求

D 本地检查省略字段时行为不变、宿主字段不进入公共设置、新会话/旧冻结快照分离，并在真正的 SDK 调用端确认 patches 元组。A 获得总控部署窗口后才管理宿主文件与服务。现场在新会话执行随机像素数字挑战，核对真实图片块与结果，保留旧失败会话。无图片支持的配置不得因为 run=completed 就判 PNG 通过。
