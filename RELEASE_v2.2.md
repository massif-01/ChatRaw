# ChatRaw v2.2

## 重点更新

### ChatRaw for Mac
- 新增 macOS 版本第一版：`ChatRaw for Mac`。
- 采用 SwiftUI 外壳 + WKWebView + 本地后端 runtime 的桌面架构。
- macOS App 会自动启动本地后端，并通过本机 `127.0.0.1` 端口加载 ChatRaw 界面。
- 新增一键构建与运行脚本，Codex 开发环境可直接使用 Run 动作启动。

### macOS 交互修复
- 修复 RemixIcon 字体在 macOS 壳内显示为方块的问题。
- 修复 Logo、头像、插件、本地文件等上传入口在 WKWebView 中无法打开文件选择器的问题。
- 修复插件卸载、清空对话等 `confirm()` 确认弹窗在 WKWebView 中无法继续执行的问题。
- 修复 macOS 打包版后端在部分环境中无法校验 HTTPS 证书链的问题，模型验证、聊天请求和插件代理等外部 HTTPS 调用会使用打包内置的 CA bundle。
- App 可见名称调整为 `ChatRaw for Mac`。

### 发布包
- 本次 Release 附带 `ChatRaw-for-Mac-2.2.dmg`。
- DMG 内包含 `ChatRaw for Mac.app`，可拖入 Applications 使用。
- macOS 包当前面向 Apple Silicon（arm64），最低系统版本为 macOS 14。
- 本次重打包 DMG SHA256：`e152b3f48defd1c8f3fec24a692cddde1c4389ad931b0c76e91b3b982c07639a`。

## 使用说明

1. 下载 `ChatRaw-for-Mac-2.2.dmg`。
2. 打开 DMG，将 `ChatRaw for Mac.app` 拖入 Applications。
3. 首次启动如遇到 macOS 安全提示，请在系统设置中允许打开。

## 已知限制

- 这是 macOS 第一版桌面壳，后端核心仍以 Python runtime 方式运行。
- 目前尚未进行 Apple notarization；正式分发链路会在后续版本继续完善。
- Docker 版本仍按既有发布流程构建。

## Docker

```bash
docker pull massif01/chatraw:2.2
# 或
docker pull massif01/chatraw:latest
```

**平台**：linux/amd64, linux/arm64
