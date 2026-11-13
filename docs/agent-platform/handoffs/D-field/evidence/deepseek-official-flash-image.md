# 官方 Flash 图片挑战取证

2026-11-14，隔离 Runner，原生 `deepseek-official` / `deepseek-flash`。公开 run `4d0e74249aa2432c9fb2595245181a0e` 对应原生会话 `session-eb6033e1b1374f98b704ef06b2e92b2d`。模型正确回忆了同会话标记，图片预期 `111978`，返回 `119780`，图片项失败。

| 现场证据 | 值 |
|---|---|
| 上传 PNG，317 字节 | SHA-256 `91182c48ae8e2fb35132d6d39e01bd8e74346b1f0a55a0032f535e7b349ab0d1` |
| Harness 归一化 JPEG，3632 字节 | SHA-256 `23299d96829b230fdc5c6acde3e9701c666a092bfe1e2a80eb0d73bad82fdeb4`，与原生用户消息 seq 64 的 `attachmentId` 一致 |
| 本会话 Files 索引唯一匹配记录 | `attachmentId` 为上述 JPEG 哈希，`variantId` 为 `sha256:8788bb247e7cbb44756c0dc9423167e7893e23ce2b4cbd07e4629695e3358a52`，`fileId` 为 `file-api-e63dd479-82f8-422a-87c9-db1936de82c3`，`bytes` 为 `3632`，`createdAt` 为 `1794598377000` |

两张图均为 284×80，目视均为 `111978`。灰度阈值 128 下 22,720 个像素逐项相同。索引变体 ID 与按默认参数重建的转换标识一致，现场无该变体的独立缓存。按原生实现，尺寸及字节数在预算内时直接复用归一化 JPEG。[Harness 请求图像实现](https://github.com/deepseek-ai/deepseek-harness/blob/dsh-v0.2.2-rc.2/packages/attachment/attachment-local/src/request-image.ts#L98-L118)

本地附件和上传索引未见错配，证据指向识别错误。原轮 Messages HTTP 未录制，实际请求中的 `file_id` 与服务端解码无法直接核验。本记录来自已完成的只读取证。
