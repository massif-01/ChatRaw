# HTML Renderer / HTML 网页渲染

Add a **Render / 渲染** button below HTML code blocks in assistant messages. It opens an interactive preview in a browser tab; the generated HTML supplies the page's own styles.

## Installation

Install **HTML Renderer** from the bundled plugin market, or upload a ZIP containing this directory. The bundled-market and ZIP installers copy the included macOS helper files. The legacy raw-directory URL installer downloads only the manifest, entry script and icon, so it is not sufficient for the macOS helper.

For **ChatRaw for Mac**, enable the bundled helper once after installing the plugin:

```sh
sh "$HOME/Library/Application Support/ChatRawMac/data/plugins/installed/html-renderer/install-mac.sh"
```

The command requires Python 3 and installs a user-level LaunchAgent. The helper runs at login and listens only on `127.0.0.1:38479`. Requests are accepted only while the plugin is enabled and originate from a running, same-user ChatRaw for Mac backend. This also supports multiple running ChatRaw for Mac instances. The helper opens the system default browser without modifying the ChatRaw application.

Origin checks protect against requests from unrelated browser pages; they are not an authentication boundary against other processes already running as the same local user.

Before uninstalling the plugin, remove its helper:

```sh
sh "$HOME/Library/Application Support/ChatRawMac/data/plugins/installed/html-renderer/install-mac.sh" --remove
```

After updating the plugin, run the enable command again to restart the helper with the updated code.

When ChatRaw is already running in a normal browser, Render opens a new tab in that browser and does not need the helper. The current browser is not necessarily the system default browser.

## Preview behavior and limits

- Assistant code blocks tagged `html`, `htm`, or `xhtml` are recognized. An untagged or XML-tagged block is recognized when it begins with an HTML doctype or `<html>`.
- Previews run in a sandboxed iframe. Scripts and keyboard/mouse interaction work, but `fetch`, WebSocket, form submission, navigation and browser storage are unavailable. Self-contained HTML with inline CSS and JavaScript is recommended. External script, stylesheet and image URLs may still load and depend on the network.
- The helper keeps up to eight previews in memory for 30 minutes and accepts requests up to 8 MB. Reopen the preview from the chat after it expires or the helper restarts.
- The helper intentionally accepts only the bundled macOS application layout (`ChatRawMac` with its child `ChatRawBackend`). It does not claim support for development servers, custom desktop wrappers, or mobile apps.

## 中文说明

安装后，助手回复的 HTML 代码块下方会出现 **渲染** 按钮。点击后在浏览器新标签页运行网页，小游戏可使用鼠标和键盘。

从内置插件市场安装，或上传包含本目录的 ZIP。旧版的原始目录 URL 安装方式只下载三个基础文件，无法安装 Mac 辅助模块。

ChatRaw for Mac 需要在安装插件后，在终端运行一次：

```sh
sh "$HOME/Library/Application Support/ChatRawMac/data/plugins/installed/html-renderer/install-mac.sh"
```

该命令需要 Python 3，会安装用户级后台服务，之后登录时自动启动。服务只监听本机，并检查请求是否来自当前用户运行的 ChatRaw for Mac；无需修改客户端程序。更新插件后需重新运行一次启用命令。卸载插件前可使用同一命令加 `--remove` 移除服务。

在普通浏览器里使用 ChatRaw 时，预览会在当前浏览器中新建标签页，无需 Mac 辅助模块。预览采用隔离方式，不能使用 `fetch`、WebSocket、表单提交、页面跳转或浏览器本地存储；建议让模型输出 CSS 和 JavaScript 均内嵌的单文件 HTML。
