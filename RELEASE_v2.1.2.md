# ChatRaw v2.1.2

## 插件相关修复 / Plugin Fixes

### Excel 解析器 (v1.0.2)
- 修复从插件市场安装时 lib/ 文件 404 问题
- 安装流程会下载 manifest dependencies 中的 lib 文件
- 修复 BUNDLED_PLUGINS_DIR 路径（支持本地开发）
- 增加 cellNF、raw 解析选项以提升表格读取准确性

### Markdown 渲染增强 (v1.0.1)
- 添加 manifest dependencies，解决从市场安装时 KaTeX/Mermaid/lib 404
- 安装时自动下载全部 18 个 lib 文件
- 修复：CSS 依赖用 loadCSS 加载（不再误用 loadScript）
- 修复：hljs 语言包在 hljs 核心加载后再加载，避免 "hljs is not defined"

### 插件设置
- 修复 select 类型 options 为对象数组时的 Alpine x-for key 警告
- 支持 `{value, label}` 格式的选项

## 文档上下文持久化 / Document Context Persistence

- 上传的表格/网页内容现会保存到对话历史
- 后续追问时模型仍可访问之前的文档内容

## 其他修复 / Other Fixes

- 修复点击「停止」时的 AbortError（流式响应）
- 开发者文档：补充 lib/dependencies 在插件市场安装中的说明

## Docker

多平台镜像（linux/amd64, linux/arm64）发布至 Docker Hub：
- `massif01/chatraw:v2.1.2`

## 如何更新 / How to Update

```bash
docker pull massif01/chatraw:v2.1.2
docker stop chatraw && docker rm chatraw
docker run -d -p 51111:51111 -v chatraw-data:/app/data --name chatraw massif01/chatraw:v2.1.2
```

---

Full Changelog: [v2.1.1...v2.1.2](https://github.com/massif-01/ChatRaw/compare/v2.1.1...v2.1.2)
