<div align="center">

# ChatRaw 🚀

**Lightweight AI Chat Interface with Plugin System | 轻量 AI 聊天界面与插件系统**

*Fast, Lightweight, Extensible | 快速、轻量、可扩展*

![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)

[English](#-part-1-core-features) / [中文](#-第一部分-核心功能)

</div>

---

## 📦 Part 1: Core Features | 第一部分：核心功能

*Fast, Lightweight, Convenient | 快速、轻量、便捷*

### Why ChatRaw? | 为什么选择 ChatRaw？

ChatRaw is designed for developers and AI hardware vendors who need a **minimal, ready-to-use chat interface** that can be deployed in seconds. No complex setup, no heavy dependencies—just a clean, fast AI chat experience.

ChatRaw 专为开发者和 AI 硬件厂商设计，提供**极简、开箱即用的聊天界面**，秒级部署。无需复杂配置，无重型依赖——只需一个干净、快速的 AI 聊天体验。

### Core Highlights | 核心亮点

- 🪶 **Ultra Lightweight** - ~60MB memory footprint, optimized binary embedding storage
- ⚡ **Instant Startup** - Ready in seconds with connection pooling for fast API calls
- 🎨 **Custom Branding** - Freely customize name, logo, and theme
- 🔌 **Universal API Support** - Works with any OpenAI-compatible API (Ollama, vLLM, LocalAI, LM Studio, etc.)
- 📄 **Document Parsing** - Native PDF, DOCX, TXT, MD parsing as chat context
- 🖼️ **Vision AI Ready** - Multimodal image understanding with auto-compression
- 🧠 **Thinking Mode** - Support for reasoning models (DeepSeek-R1, Qwen, o1, etc.)
- 📱 **Responsive Design** - Optimized for desktop, tablet, and mobile
- 🌍 **Bilingual UI** - English & Chinese with one-click switch
- 🔒 **Zero Registration** - Settings auto-saved locally
- 🐳 **One-Click Deploy** - Docker deployment in 30 seconds

- 🪶 **极致轻量** - 内存占用约 60MB，优化的二进制向量存储
- ⚡ **极速启动** - 秒级启动，连接池加速 API 调用
- 🎨 **自定义品牌** - 自由定制名称、Logo 和主题
- 🔌 **通用 API 支持** - 兼容任意 OpenAI 兼容 API（Ollama、vLLM、LocalAI、LM Studio 等）
- 📄 **文档解析** - 原生支持 PDF、DOCX、TXT、MD 解析作为聊天上下文
- 🖼️ **视觉 AI 就绪** - 多模态图片理解，自动压缩
- 🧠 **思考模式** - 支持推理模型（DeepSeek-R1、Qwen、o1 等）
- 📱 **响应式设计** - 完美适配桌面、平板和移动设备
- 🌍 **双语界面** - 中英文一键切换
- 🔒 **零注册** - 设置自动保存到本地
- 🐳 **一键部署** - Docker 30 秒部署

### Quick Start | 快速开始

**Option 1: One Command | 方式一：一行命令**
```bash
docker run -d -p 51111:51111 -v chatraw_data:/app/data --name chatraw massif01/chatraw:latest
```

**Option 2: Docker Compose | 方式二：Docker Compose**
```bash
git clone https://github.com/massif-01/ChatRaw.git
cd ChatRaw
docker compose up -d
```

**Option 3: From Source | 方式三：源代码部署**
```bash
git clone https://github.com/massif-01/ChatRaw.git
cd ChatRaw/backend
pip install -r requirements.txt
python main.py
```

**Visit | 访问 http://localhost:51111**

### Core Features Overview | 核心功能概览

<!-- TODO: Add screenshot of main interface showing clean, minimal design -->
*[Screenshot: Main chat interface - clean, minimal design]*

#### 1. Model Configuration | 模型配置
Configure multiple AI models with any OpenAI-compatible API endpoint. Switch between models instantly.

配置多个 AI 模型，支持任意 OpenAI 兼容 API 端点。即时切换模型。

<!-- TODO: Add screenshot of model settings page -->
*[Screenshot: Model configuration interface]*

#### 2. Document Context | 文档上下文
Upload documents (PDF, DOCX, TXT, MD) as chat context. AI can read and reference the document content.

上传文档（PDF、DOCX、TXT、MD）作为聊天上下文。AI 可以阅读和引用文档内容。

#### 3. Vision AI | 视觉 AI
Attach images for multimodal understanding. Automatic compression to WebP format (~2MB).

附加图片进行多模态理解。自动压缩为 WebP 格式（约 2MB）。

#### 4. Thinking Mode | 思考模式
Enable deep reasoning for models that support it. Collapsible thinking process display.

为支持的模型启用深度推理。可折叠的思考过程显示。

#### 5. Custom Branding | 自定义品牌
Customize your interface: name, logo, subtitle, avatars, and theme colors.

自定义界面：名称、Logo、副标题、头像和主题颜色。

---

## 🔌 Part 2: Plugin System | 第二部分：扩展插件

*Unlimited Freedom, Infinite Possibilities | 无限自由，无限可能*

### Plugin Architecture | 插件架构

ChatRaw features a **lightweight, JavaScript-based plugin system** that runs entirely in the browser. Plugins can extend functionality without modifying core code, giving you complete freedom to customize your AI chat experience.

ChatRaw 采用**轻量级、基于 JavaScript 的插件系统**，完全在浏览器中运行。插件可以扩展功能而无需修改核心代码，让您完全自由地定制 AI 聊天体验。

### Why Plugins? | 为什么需要插件？

- **Keep Core Lightweight** - Core remains minimal; add features only when needed
- **Community-Driven** - Share and discover plugins from the community
- **Easy Development** - Simple JavaScript API, no complex build process
- **Secure by Design** - API keys protected via backend proxy
- **Zero Overhead** - Plugins only load when enabled

- **保持核心轻量** - 核心保持极简；仅在需要时添加功能
- **社区驱动** - 分享和发现社区插件
- **易于开发** - 简单的 JavaScript API，无需复杂构建流程
- **安全设计** - API 密钥通过后端代理保护
- **零开销** - 插件仅在启用时加载

### Plugin Market | 插件市场

Browse and install plugins directly from the interface. No manual file management needed.

直接从界面浏览和安装插件。无需手动文件管理。

<!-- TODO: Add screenshot of plugin market interface -->
*[Screenshot: Plugin market with available plugins]*

### Available Plugins | 可用插件

#### Document Parsers | 文档解析器

- **Excel Parser** - Parse Excel files (.xlsx, .xls) into Markdown tables
- **CSV Parser** - Parse CSV/TSV files with auto-delimiter detection
- **Excel 解析器** - 将 Excel 文件（.xlsx、.xls）解析为 Markdown 表格
- **CSV 解析器** - 解析 CSV/TSV 文件，自动检测分隔符

#### Search Providers | 搜索提供商

- **Bocha Web Search** - Real-time web search with Web Search and AI Search modes, configurable result count and time range
- **博查联网搜索** - 实时联网搜索，支持通搜和 AI 搜两种模式，可配置结果数量和时间范围

#### RAG / Knowledge Base | RAG / 知识库

- **Lightweight RAG Demo** - Full-featured RAG with knowledge base, embedding model config, and reranker support
- **轻量 RAG 演示** - 功能完整的 RAG，包含知识库管理、嵌入模型配置和重排模型支持

### Plugin Development | 插件开发

Creating plugins is simple. Just JavaScript—no build tools required.

创建插件很简单。只需 JavaScript——无需构建工具。

**Basic Plugin Structure | 基本插件结构**
```
your-plugin/
├── manifest.json    # Plugin metadata
├── icon.png         # 128x128 icon
└── main.js          # Plugin code
```

**Example: Document Parser | 示例：文档解析器**
```javascript
ChatRaw.hooks.register('parse_document', {
    fileTypes: ['.xlsx', '.xls'],
    handler: async (file) => {
        // Parse file and return content
        return { success: true, content: parsedText };
    }
});
```

For complete documentation, see [Plugins/README.md](Plugins/README.md)

完整文档请参阅 [Plugins/README.md](Plugins/README.md)

### Plugin Installation | 插件安装

**From Market | 从市场安装**
1. Open Settings → Plugins
2. Browse Plugin Market
3. Click Install

1. 打开设置 → 插件
2. 浏览插件市场
3. 点击安装

**Local Upload | 本地上传**
1. Open Settings → Plugins → Install Local Plugin
2. Select plugin zip file
3. Plugin installed automatically

1. 打开设置 → 插件 → 本地安装
2. 选择插件 zip 文件
3. 插件自动安装

### Plugin Management | 插件管理

- Enable/disable plugins with one click
- Configure plugin settings
- View plugin details and version
- Uninstall unused plugins

- 一键启用/禁用插件
- 配置插件设置
- 查看插件详情和版本
- 卸载未使用的插件

---

## 🎨 Interface | 界面展示

| Light Mode | Dark Mode |
|:----------:|:---------:|
| ![Light](assets/interfacelight.png) | ![Dark](assets/interfacedark.png) |

---

## 🔄 Update | 更新

**Docker (One Command) | Docker（一行命令）**
```bash
docker pull massif01/chatraw:latest
docker stop chatraw && docker rm chatraw
docker run -d -p 51111:51111 -v chatraw_data:/app/data --name chatraw massif01/chatraw:latest
```

**Docker Compose | Docker Compose**
```bash
cd ChatRaw
git pull origin main
docker compose down && docker compose pull && docker compose up -d
```

**From Source | 源代码**
```bash
cd ChatRaw
git pull origin main
cd backend
pip install -r requirements.txt
python main.py
```

> 💡 **Note | 提示**: Your settings, documents, and installed plugins are preserved during updates. Data is stored in Docker volume (`chatraw_data`) or `data/` folder.

> 💡 **提示**：更新过程中您的设置、文档和已安装的插件都会保留。数据存储在 Docker volume（`chatraw_data`）或 `data/` 文件夹中。

---

## 📝 API Compatibility | API 兼容性

| Service | URL Example |
|---------|-------------|
| Ollama | `http://localhost:11434/v1` |
| vLLM | `http://localhost:8000/v1` |
| LocalAI | `http://localhost:8080/v1` |
| LM Studio | `http://localhost:1234/v1` |
| OpenAI | `https://api.openai.com/v1` |

---

## 📄 License

[Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0)

Copyright © 2026 massif-01, RMinte AI Technology Co., Ltd.

---

<div align="center">

**ChatRaw** - Making AI Chat Simple Again | 让 AI 聊天回归简单

</div>
