# HTML Renderer / HTML 网页渲染

Add a **Render / 渲染** button below HTML code blocks in assistant messages. It opens an interactive preview in a new tab of the current browser; the generated HTML supplies the page's own styles.

## Installation and use

Install **HTML Renderer** from the bundled plugin market or upload a ZIP containing this directory. The plugin works when ChatRaw is opened in a browser. If the browser blocks the new tab, allow pop-ups for the ChatRaw site and click **Render** again.

The embedded view in the current ChatRaw for Mac client does not provide an API to open the preview in an external browser. Use ChatRaw in a regular browser for this version of the plugin.

If you installed an earlier experimental Mac helper, remove it before replacing or uninstalling that version:

```sh
sh "$HOME/Library/Application Support/ChatRawMac/data/plugins/installed/html-renderer/install-mac.sh" --remove
```

This browser-only version does not install a background service.

## Preview behavior and limits

- Assistant code blocks tagged `html`, `htm`, or `xhtml` are recognized. An untagged or XML-tagged block is recognized when it begins with an HTML doctype or `<html>`.
- Previews run in a sandboxed iframe. Scripts and keyboard/mouse interaction work, but `fetch`, WebSocket, form submission, navigation and browser storage are unavailable. Self-contained HTML with inline CSS and JavaScript is recommended. External script, stylesheet and image URLs may still load and depend on the network.

## 中文说明

从内置插件市场安装，或上传包含本目录的 ZIP。安装后，助手回复的 HTML 代码块下方会出现 **渲染** 按钮；点击后在当前浏览器的新标签页中运行，小游戏可使用鼠标和键盘。若浏览器拦截新标签页，请允许该 ChatRaw 网站打开弹窗后重试。

此版本适用于浏览器中的 ChatRaw。当前 Mac 客户端内置网页视图没有提供调用外部浏览器的接口，请使用浏览器版。此版本不会安装后台服务。

如果曾安装过实验版 Mac 辅助模块，请在覆盖安装或卸载旧版插件前，先运行上面的 `--remove` 命令清理后台服务。

预览采用隔离方式，不能使用 `fetch`、WebSocket、表单提交、页面跳转或浏览器本地存储；建议让模型输出 CSS 和 JavaScript 均内嵌的单文件 HTML。
