# E 线首批交付

以 `0c14990` 的前端为接线基线。资源位于 `backend/static/vendor/`，Docker 原有静态目录复制规则会一并打包。浏览器使用随应用交付的核心和官方插件资源。Node 和 npm 用于构建、核验及测试。

## 合入顺序

1. 合入 E 线提交。B 在基线可直接应用 `git apply docs/agent-platform/handoffs/E/entrypoints.patch`。入口已有改动时，按补丁的四个文件逐项合入。
2. 先加载同源 Marked，再按 Collapse → Alpine 的顺序延迟执行。保留应用入口的脚本顺序，保证 Alpine 启动时 `app()` 已定义。Alpine 自动调用 `init()`，移除重复的 `x-init="init()"` 以防两轮插件加载争用注册状态。
3. 核心高亮复用 `loadHighlightJS()`。其 Promise 等待同源脚本，11.9.0 浏览器包已含原来并行加载的 Python、JavaScript、Bash、JSON，也含增强插件所用的十五种语法。使用 Marked 9 的 `renderer.code`，旧 `highlight` 参数从 v8 起已移除。已识别的语言保留 `language-*`，Mermaid、Markmap 及其他未识别语言继续交给默认 renderer。若 B 使用自定义流式 renderer，应保留高亮入口和代码块语言类名。 [Marked 文档](https://marked.js.org/using_advanced#old-options)
4. CSV manifest 走 `/vendor/papaparse/5.4.1/papaparse.min.js`。插件加载器只改写该插件已安装的旧 5.4.1 URL，并把 `window.Papa` 注册为 `papaparse`，否则旧插件会从 `ChatRaw.require` 取得布尔值。已安装 manifest 和配置可以保留。
5. 用 `npm run build` 生成 `app.min.js` 和 `styles.min.css`。总控发布时确认 HTML 中 preload 和 script 使用同一新 app 版本号，CSS 也用新版本号。当前静态服务器将 JS、CSS 和字体作为 immutable 缓存。版本目录用于固定第三方文件。
6. A/B 负责从随应用交付的市场目录完整安装官方插件和前端市场接线。旧安装只下载 manifest 中逐项列出的依赖，可能缺少 `markdown-enhancer/lib/fonts/`。A 的实现须覆盖已有的部分 `lib/` 安装，并保留用户配置。E 首批浏览器测试用完整本地目录模拟已安装状态。

## 资源和来源

| 用途 | 版本及来源 | 交付位置或运行条件 |
| --- | --- | --- |
| 核心脚本 | Alpine 和 Collapse 3.13.3，Marked 9.1.6，Highlight.js 11.9.0。来自 `package-lock.json` 锁定的 npm 发行包 | `backend/static/vendor/` |
| CSV 插件 | Papa Parse 5.4.1，来自锁定的 npm 发行包 | `backend/static/vendor/` |
| 图标 | Remix Icon 4.9.1，完整 CSS 和字体与 npm 发行包逐字节相符 | 原有 `backend/static/fonts/remixicon/`。精简 CSS 是仓库的派生产物 |
| Excel 插件 | SheetJS CE 0.20.1，与官方发行包逐字节相符 | 原有插件 `lib/`。 [SheetJS 官方发行包](https://cdn.sheetjs.com/xlsx-0.20.1/xlsx-0.20.1.tgz) |
| Markdown 增强 | KaTeX 0.16.9、Mermaid 10.6.1、Highlight.js 11.9.0 的十五个语言包，与发行包逐字节相符 | 原有插件 `lib/`。KaTeX 交付二十个 WOFF2 字体 |
| 思维导图 | 仓库已有 Markmap 组合包。新构建固定 `markmap-lib` 和 `markmap-view` 0.18.12，使用 `markmap-lib/no-plugins`，默认 Transformer 的插件集合为空 | 原有插件 `lib/`。保留现有字节，单独记录新锁下的可复现构建 |
| PDF 导出 | html2pdf.js 0.10.1，与 npm 发行包逐字节相符 | 原有插件 `lib/`。`save()` 路径使用本地包。包内还含 jsPDF 的 `pdfobjectnewwindow` 外链分支，ChatRaw 导出入口不调用它 |

`backend/static/vendor/SHA256SUMS` 记录这些文件和许可证。许可证包含 Alpine 及其 Vue Reactivity、Highlight.js、Marked、Papa Parse、Remix Icon、KaTeX 和字体、Mermaid、SheetJS CE、html2pdf.js 及发行包的合并声明、Markmap 及锁定构建输入的许可证。原有发行文件内的第三方版权声明照原样保留。

市场页的 GitHub 回退、URL 安装，以及模型、搜索、网页抓取、GitHub Skill 安装和 Web Speech 服务各有自己的联网条件。用户消息内嵌远程图片也可能产生外部请求。现有第三方插件的外部依赖仍按其 manifest 处理。五个 Agent 插件可直接用宿主同源入口和共享 renderer。

## 可复现构建

~~~sh
npm ci
npm run vendor:check
npm run build
~~~

`npm run vendor:sync` 从锁定的 npm 包复制新增 vendor 文件，再校验已提交的摘要。更新某个依赖时，应在确认新来源与版本后同时更新文件、许可证、摘要和接线地址。

`npm run build:markmap` 单独重建 Markmap。重复运行得到相同字节。该结果与仓库历史包不同，合入首批使用原历史包。未来如主动更新产物，应同时验证新包并更新摘要。

## 运行兼容检查

从已接线、已执行 `npm run build` 的工作树运行。先为 `PYTHON` 指定已安装 `backend/requirements.txt` 的 Python。

~~~sh
CHROME_PATH=/absolute/path/to/chromium109 PYTHON=/absolute/path/to/python npm run test:chrome109
CHROME_PATH=/absolute/path/to/modern-chrome PYTHON=/absolute/path/to/python npm run test:offline-ui
~~~

脚本启动临时的回环地址 ChatRaw、测试数据库和 OpenAI 格式的模拟 SSE 服务，在新浏览器上下文中拒绝外部请求。109 检查用 CDP `Browser.getVersion` 的产品版本判定，现代浏览器命令使用实际传入的浏览器。

macOS arm64 可从 Microsoft Playwright 官方存档获取 Chromium 109。临时目录解包即可直接运行 `chrome-mac/Chromium.app/Contents/MacOS/Chromium`。

- [Playwright v1.29.2 的版本和修订记录](https://github.com/microsoft/playwright/blob/v1.29.2/packages/playwright-core/browsers.json)
- [官方 Chromium 1041 macOS arm64 ZIP](https://cdn.playwright.dev/builds/chromium/1041/chromium-mac-arm64.zip)
- ZIP 实测 SHA-256 为 `309715c55f6d13ffbeef969cb3969ec792f2146c2dab95147439c633beb5d006`
- [Chromium 项目对旧版浏览器获取方式的说明](https://www.chromium.org/getting-involved/download-chromium/)

## 首批实测

测试输入为 `0c14990` 加 `entrypoints.patch` 和 E 线资源，重建并实际加载压缩产物。环境为 macOS 27.0.1 arm64、Node 24.10.0、npm 11.6.0。

| 检查 | 结果 |
| --- | --- |
| `npm ci`、`npm run vendor:check` | 通过。校验 70 个资源或许可证文件，npm 复制件另与锁定包比较 |
| 两次 `npm run build` | JS 和 CSS 分别逐字节一致。SHA-256 为 `cead0ad07e0e30b837a06af4f8c0a2b895ff0bb5ce4cbadfe10abe10af4b22e5` 和 `ca131c569c41fed286c3225404fc5447f7f510d2072f279bdc9d7caf7f68de31` |
| 两次 `npm run build:markmap` | 逐字节一致，重建包 SHA-256 为 `fc4c973dbd6a194c6a0f6b4623234e6deb14a70809e83fc5395e0ff20bf315fd` |
| `npm run test:chrome109` | 真实 Chromium `109.0.5414.46`，CDP 修订 `@6e36b77363ef3febbe792af680fa1367993ddcf0`。通过 |
| `npm run test:offline-ui` | 真实 Google Chrome `157.0.8103.39`，CDP 修订 `@9a31f0acec1854d44e49a73fbf8017598151a583`。通过。用此浏览器运行 109 命令时按预期失败 |
| 原有 Python unittest | 分别运行 `backend.test_context_compaction`、`backend.test_http_session_tls`、`backend.test_skills`、`backend.test_fonts_route`，20 + 4 + 57 + 2 项通过 |

两次浏览器检查均确认普通聊天流、Collapse 展开、Markdown 表格和转义、高亮、旧 CSV manifest 上传及真实下游内容、SheetJS 资源加载、KaTeX 字体、Mermaid、Markmap、PDF 下载、市场本地图标。测试中外部请求尝试、HTTP 错误和浏览器错误均为零。ChatRaw UI、后端与插件实际运行，模型只使用回环模拟 SSE。

G12 首批覆盖核心及已安装插件的运行。A/B 完整安装与部分安装修复完成后，应从空数据目录以及旧的部分 `lib/` 再测。G11 首批取得 macOS Chromium 109 证据，Windows 8、Google Chrome 品牌 109 和正式五 Agent 集成版本仍待验证。现有 Safari、Android、Firefox 和 IE 行为均未实测。
