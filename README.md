<div align="center">

![ChatRaw Template](assets/chatrawtemplate.png)

**Lightweight AI Chat Interface with Plugin System | 轻量 AI 聊天界面与插件系统**

*Fast, Lightweight, Extensible | 快速、轻量、可扩展*

![Lighthouse Performance](https://img.shields.io/badge/Lighthouse-100%2F100%2F100%2F100-brightgreen?logo=lighthouse)
![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)
![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![Docker Pulls](https://img.shields.io/docker/pulls/massif01/chatraw?logo=docker)
![Memory](https://img.shields.io/badge/Memory-~60MB-green?logo=microsoftedge)
![Startup](https://img.shields.io/badge/Startup-Seconds-brightgreen?logo=rocket)
![OpenAI Compatible](https://img.shields.io/badge/OpenAI-Compatible-412991?logo=openai)

[English](#english) | [中文](#中文)

</div>

---

# English

## Interface Preview

### Main Chat Interface
![Main Interface](assets/main-interface.png)

### Model Configuration
![Model Configuration](assets/model-configuration.png)

### Plugin Market
![Plugin Market](assets/plugin-market.png)

---

## Why ChatRaw?

Many developers, AI hardware vendors, and users just need a simple, lightweight application that can quickly demonstrate their model capabilities. That's why we created ChatRaw - a minimal, ready-to-use chat interface that deploys in seconds. No complex configuration, no heavy dependencies—just a clean, fast AI chat experience.

---

## Part 1: Core Features

*Fast, Lightweight, Convenient*

### Core Highlights

- **Ultra Lightweight** - ~60MB memory footprint, optimized binary embedding storage
- **Instant Startup** - Ready in seconds with connection pooling for fast API calls
- **Custom Branding** - Freely customize name, logo, and theme
- **Universal API Support** - Works with any OpenAI-compatible API (Ollama, vLLM, LocalAI, LM Studio, etc.)
- **Document Parsing** - Native PDF, DOCX, TXT, MD parsing as chat context
- **Vision AI Ready** - Multimodal image understanding with auto-compression
- **Thinking Mode** - Support for reasoning models (DeepSeek-R1, Qwen, o1, etc.)
- **Responsive Design** - Optimized for desktop, tablet, and mobile with touch-friendly UI
- **One-Click Copy** - Copy AI responses instantly (text only, no metadata)
- **Bilingual UI** - English & Chinese with one-click switch
- **Zero Registration** - Settings auto-saved locally
- **One-Click Deploy** - Docker deployment in 30 seconds

### Key Features

**Multi-Model Configuration**
- Supports unlimited chat, embedding, and reranking models
- Automatic API key rotation to bypass rate limits
- Built-in endpoint validation and testing

**Thinking Mode**
- Deep reasoning for supported models
- Collapsible thought process display

**Custom Branding**
- Customize interface: name, Logo, subtitle, avatar, and theme colors

**Document & Image Support**
- Upload documents (PDF, DOCX, TXT, MD) as chat context. AI can read and reference document content
- Attach images for multimodal understanding. Automatically compressed to WebP format (~2MB)

---

## Part 2: Extension Plugins

*Flexible, Free, Community-Driven*

ChatRaw features a complete **plugin system** to extend functionality:

### Official Plugins

- **Lightweight RAG Demo** — Knowledge base retrieval
- **Bocha Search** — Web / AI search
- **Tavily Search** — Web search with AI answers
- **Excel Parser** — Parse .xlsx/.xls for chat
- **CSV Parser** — Parse CSV/TSV for chat
- **Enhanced Web Parsing** — Parse web pages (browser / Firecrawl / Jina)
- **Multi-Model Manager** — Manage and switch models
- **Markdown Renderer Plus** — Math (KaTeX), Mermaid, code copy, offline
- **Toolbar Extension Demo** — Demo plugin showcasing UI Extension API

### Toolbar Extension
> Plugins can add custom buttons to the input toolbar with active/loading states, overflow menu for many buttons, and fullscreen modal for complex interactions.

### Plugin Development
- Complete development documentation
- Rich hook system (including new UI Extension API)
- Custom settings UI
- One-click packaging and distribution

**Plugin Development Guide**: [Plugins/README.md](Plugins/README.md)

---

## Performance

> **Note**: Performance tests conducted using Google Lighthouse on localhost deployment

|                    Desktop                    |                    Mobile                    |
| :-------------------------------------------: | :------------------------------------------: |
|     ![Desktop Performance][perf-desktop]      |     ![Mobile Performance][perf-mobile]       |
| [Lighthouse Report][perf-desktop-report]   | [Lighthouse Report][perf-mobile-report]   |

**Desktop**: Performance 100 | Accessibility 100 | Best Practices 100 | SEO 100

**Mobile**: Performance 96 | Accessibility 93 | Best Practices 100 | SEO 100

[perf-desktop]: assets/lighthouse-desktop.png
[perf-mobile]: assets/lighthouse-mobile.png
[perf-desktop-report]: https://htmlpreview.github.io/?https://github.com/massif-01/ChatRaw/blob/main/docs/lighthouse/desktop.html
[perf-mobile-report]: https://htmlpreview.github.io/?https://github.com/massif-01/ChatRaw/blob/main/docs/lighthouse/mobile.html

---

## Quick Start

### Option 1: Docker (Recommended)

**Prerequisites**: [Docker](https://docs.docker.com/get-docker/) installed.

Docker images are published to **Docker Hub** and **GitHub Container Registry**. To get the **latest** image (not a cached old one), always run `docker pull` with the tag you want before creating the container. Use `:latest` for the current release, or a version tag (e.g. `v2.1.2`) from [Releases](https://github.com/massif-01/ChatRaw/releases) for a fixed version.

**Supported platforms**: linux/amd64 (Intel/AMD), linux/arm64 (Apple Silicon, Raspberry Pi 4/5).

---

#### Method A: `docker run` (no project files)

Run these commands in a terminal. Data is stored in a Docker volume `chatraw-data`.

```bash
# 1. Pull the latest image (run this again whenever you want to update)
docker pull massif01/chatraw:latest

# 2. Start the container (creates volume chatraw-data if needed)
docker run -d -p 51111:51111 -v chatraw-data:/app/data --name chatraw massif01/chatraw:latest
```

- **Access**: http://localhost:51111  
- **To access LAN services** (e.g. local LLM at 192.168.x.x), use host network instead:
  ```bash
  docker run -d --network host -v chatraw-data:/app/data -e PORT=51111 --name chatraw massif01/chatraw:latest
  ```

---

#### Method B: docker-compose (host network, good for LAN)

Clone the project and run from the repo root. The included `docker-compose.yml` uses host network so the app can reach LAN services (e.g. 192.168.x.x) without extra config.

```bash
# 1. Clone the repository
git clone https://github.com/massif-01/ChatRaw.git
cd ChatRaw

# 2. Pull the latest image and start the service
docker compose pull
docker compose up -d
```

- **Access**: http://localhost:51111 (or http://\<your-ip\>:51111 from other devices).

---

### Option 2: From Source

**Requirements**: Python 3.12+

```bash
# Clone repository
git clone https://github.com/massif-01/ChatRaw.git
cd ChatRaw/backend

# Install dependencies
pip install -r requirements.txt

# Run
python main.py
```

**Access**: http://localhost:51111

---

## Docker image sources

| Source | Pull command |
|--------|----------------|
| Docker Hub | `docker pull massif01/chatraw:latest` |
| GitHub Container Registry | `docker pull ghcr.io/massif-01/chatraw:latest` |

Use the same tag for a specific version, e.g. `massif01/chatraw:v2.1.2` (see [Releases](https://github.com/massif-01/ChatRaw/releases)).

---

## Update Guide

### Docker (docker run)

```bash
# Stop and remove the current container
docker stop chatraw && docker rm chatraw

# Pull the latest image (important: otherwise the old image is reused)
docker pull massif01/chatraw:latest

# Start again (same volume keeps your data)
docker run -d -p 51111:51111 -v chatraw-data:/app/data --name chatraw massif01/chatraw:latest
```

### Docker Compose

```bash
cd ChatRaw
git pull origin main
docker compose pull
docker compose up -d
```

### From Source

```bash
cd ChatRaw
git pull origin main
cd backend
pip install -r requirements.txt --upgrade
python main.py
```

### Important changes in v2.0.0 (if upgrading from v1.x)

- RAG is now a plugin: install **Lightweight RAG Demo** from Plugin Market if you need it.
- Default theme is light (changeable in Settings).
- Chat history and settings are preserved.

---

## Configuration

### Initial Setup

1. Open http://localhost:51111
2. Click the **Settings** button in the bottom-left corner
3. Go to **Model Settings**
4. Add your API configuration:
   - API Base URL (e.g., `https://api.openai.com/v1`)
   - Model ID (e.g., `gpt-4`)
   - API Key
5. Click **Verify** to test the connection
6. Click **Save**

### Custom Branding

In **Settings** → **Interface**, you can customize:
- Application name and logo
- User and AI avatars
- Theme mode (light/dark)

### Install Plugins

1. Click the **Plugins** button in the bottom-left corner
2. Browse the **Plugin Market** tab
3. Click **Install** on any plugin
4. After installation, enable the plugin in the **Installed** tab

---

## Use Cases

- **Developers**: Quickly test and demo your AI models
- **AI Hardware Vendors**: Showcase device capabilities with a ready-to-use interface
- **Researchers**: Experiment with RAG, embeddings, and reranking
- **Students**: Learn AI applications hands-on
- **Enterprises**: Internal AI tools and knowledge bases

---

## Contributing

Contributions are welcome! Please submit issues or pull requests.

### Development Guidelines

1. Fork this repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## License

Apache License 2.0

© 2026 ChatRaw by massif-01, RMinte® AI Technology Co., Ltd.

---

## Links

- **GitHub**: https://github.com/massif-01/ChatRaw
- **Docker Hub**: https://hub.docker.com/r/massif01/chatraw
- **Plugin Development**: [Plugins/README.md](Plugins/README.md)
- **Issue Tracker**: https://github.com/massif-01/ChatRaw/issues

---

<br><br>

---

<br><br>

# 中文

## 界面展示

### 主聊天界面
![主界面](assets/main-interface.png)

### 模型配置
![模型配置](assets/model-configuration.png)

### 插件市场
![插件市场](assets/plugin-market.png)

---

## 为什么选择 ChatRaw？

很多开发者、AI 硬件厂商，甚至是用户只需要一个简洁轻量，能够快速展示自己模型使用的应用，于是我们提供了极简、开箱即用的聊天界面，秒级部署。无需复杂配置，无重型依赖——只需一个干净、快速的 AI 聊天体验。

---

## 第一部分：核心功能

*快速、轻量、便捷*

### 核心亮点

- **极致轻量** - 内存占用约 60MB，优化的二进制向量存储
- **极速启动** - 秒级启动，连接池加速 API 调用
- **自定义品牌** - 自由定制名称、Logo 和主题
- **通用 API 支持** - 兼容任意 OpenAI 兼容 API（Ollama、vLLM、LocalAI、LM Studio 等）
- **文档解析** - 原生支持 PDF、DOCX、TXT、MD 解析作为聊天上下文
- **视觉 AI 就绪** - 多模态图片理解，自动压缩
- **思考模式** - 支持推理模型（DeepSeek-R1、Qwen、o1 等）
- **响应式设计** - 完美适配桌面、平板和移动设备，触控友好
- **一键复制** - 一键复制 AI 回复内容（纯文本，不含元数据）
- **双语界面** - 中英文一键切换
- **零注册** - 设置本地自动保存
- **一键部署** - Docker 30 秒部署

### 主要功能

**多模型配置**
- 支持无限数量的聊天、嵌入和重排模型
- 自动 API Key 轮换以绕过速率限制
- 内置端点验证和测试

**思考模式**
- 为支持的模型启用深度推理
- 可折叠的思考过程显示

**自定义品牌**
- 自定义界面：名称、Logo、副标题、头像和主题颜色

**文档与图片支持**
- 上传文档（PDF、DOCX、TXT、MD）作为聊天上下文。AI 可以阅读和引用文档内容
- 附加图片进行多模态理解。自动压缩为 WebP 格式（约 2MB）

---

## 第二部分：扩展插件

*灵活、自由、社区驱动*

ChatRaw 拥有完整的**插件系统**以扩展功能：

### 官方插件

- **轻量 RAG 演示** — 知识库检索
- **博查搜索** — Web / AI 搜索
- **Tavily 搜索** — Web 搜索 + AI 答案
- **Excel 解析器** — 解析 .xlsx/.xls 供对话使用
- **CSV 解析器** — 解析 CSV/TSV 供对话使用
- **增强网页解析** — 解析网页（浏览器 / Firecrawl / Jina）
- **多模型管理** — 管理并切换模型
- **Markdown 渲染增强** — 数学公式、Mermaid、代码复制，离线可用
- **工具栏扩展演示** — 展示 UI 扩展 API 的演示插件

### 工具栏扩展
> 插件可以在输入框工具栏添加自定义按钮，支持激活态/加载态、按钮溢出折叠菜单，以及全屏模态框实现复杂交互。

### 插件开发
- 完整的开发文档
- 丰富的 Hook 系统（包含全新 UI 扩展 API）
- 自定义设置界面
- 一键打包分发

**插件开发指南**: [Plugins/README.md](Plugins/README.md)

---

## 性能测试

> **说明**: 使用 Google Lighthouse 对本地部署进行性能测试

|                    桌面端                     |                    移动端                     |
| :-------------------------------------------: | :-------------------------------------------: |
|     ![桌面端性能][perf-desktop]               |     ![移动端性能][perf-mobile]                |
| [Lighthouse 测试报告][perf-desktop-report] | [Lighthouse 测试报告][perf-mobile-report]  |

**桌面端**: 性能 100 | 无障碍 100 | 最佳做法 100 | SEO 100

**移动端**: 性能 96 | 无障碍 93 | 最佳做法 100 | SEO 100

---

## 快速开始

### 方式一：Docker（推荐）

**前置条件**：已安装 [Docker](https://docs.docker.com/get-docker/)。

镜像发布在 **Docker Hub** 和 **GitHub Container Registry**。若想用**最新**镜像（避免用到本地缓存的旧镜像），在创建容器前请先执行一次 `docker pull`。使用 `:latest` 表示当前最新版本；如需固定版本，可使用 [Releases](https://github.com/massif-01/ChatRaw/releases) 中的版本号标签（如 `v2.1.2`）。

**支持平台**：linux/amd64（Intel/AMD）、linux/arm64（Apple Silicon、树莓派 4/5）。

---

#### 方式 A：`docker run`（无需项目文件）

在终端依次执行。数据保存在 Docker 卷 `chatraw-data` 中。

```bash
# 1. 拉取最新镜像（每次要更新时重新执行此命令）
docker pull massif01/chatraw:latest

# 2. 启动容器（若卷 chatraw-data 不存在会自动创建）
docker run -d -p 51111:51111 -v chatraw-data:/app/data --name chatraw massif01/chatraw:latest
```

- **访问**：http://localhost:51111  
- **如需访问局域网服务**（例如本机 LLM 在 192.168.x.x），可改用 host 网络：
  ```bash
  docker run -d --network host -v chatraw-data:/app/data -e PORT=51111 --name chatraw massif01/chatraw:latest
  ```

---

#### 方式 B：docker-compose（host 网络，适合访问局域网）

克隆项目后在仓库根目录执行。项目内的 `docker-compose.yml` 使用 host 网络，可直接访问局域网服务（如 192.168.x.x），无需额外配置。

```bash
# 1. 克隆仓库
git clone https://github.com/massif-01/ChatRaw.git
cd ChatRaw

# 2. 拉取最新镜像并启动服务
docker compose pull
docker compose up -d
```

- **访问**：http://localhost:51111（或本机 IP http://\<你的IP\>:51111 从其他设备访问）。

---

### 方式二：源码部署

**环境要求**：Python 3.12+

```bash
# 克隆仓库
git clone https://github.com/massif-01/ChatRaw.git
cd ChatRaw/backend

# 安装依赖
pip install -r requirements.txt

# 运行
python main.py
```

**访问**：http://localhost:51111

---

## Docker 镜像来源

| 来源 | 拉取命令 |
|------|----------|
| Docker Hub | `docker pull massif01/chatraw:latest` |
| GitHub Container Registry | `docker pull ghcr.io/massif-01/chatraw:latest` |

需要固定版本时使用相同标签格式，例如 `massif01/chatraw:v2.1.2`，版本号见 [Releases](https://github.com/massif-01/ChatRaw/releases)。

---

## 更新指南

### Docker（docker run）

```bash
# 停止并删除当前容器
docker stop chatraw && docker rm chatraw

# 拉取最新镜像（重要：否则会继续用旧镜像）
docker pull massif01/chatraw:latest

# 再次启动（使用同一卷，数据保留）
docker run -d -p 51111:51111 -v chatraw-data:/app/data --name chatraw massif01/chatraw:latest
```

### Docker Compose

```bash
cd ChatRaw
git pull origin main
docker compose pull
docker compose up -d
```

### 源码部署

```bash
cd ChatRaw
git pull origin main
cd backend
pip install -r requirements.txt --upgrade
python main.py
```

### v2.0.0 重要变更（从 v1.x 升级时）

- RAG 已改为插件：需要 RAG 时请在插件市场中安装 **轻量 RAG 演示**。
- 默认主题为亮色（可在设置中修改）。
- 对话历史与设置会保留。

---

## 配置说明

### 初始设置

1. 打开 http://localhost:51111
2. 点击左下角的**设置**按钮
3. 进入**模型设置**
4. 添加你的 API 配置：
   - API Base URL（例如：`https://api.openai.com/v1`）
   - Model ID（例如：`gpt-4`）
   - API Key
5. 点击**验证**测试连接
6. 点击**保存**

### 自定义品牌

在**设置** → **界面**中，你可以自定义：
- 应用名称和 Logo
- 用户和 AI 头像
- 主题模式（亮色/暗色）

### 安装插件

1. 点击左下角的**插件**按钮
2. 浏览**插件市场**标签页
3. 点击任意插件的**安装**按钮
4. 安装后，在**已安装**标签页中启用插件

---

## 使用场景

- **开发者**：快速测试和演示你的 AI 模型
- **AI 硬件厂商**：用即插即用的界面展示设备能力
- **研究人员**：实验 RAG、嵌入和重排技术
- **学生**：动手学习 AI 应用
- **企业**：内部 AI 工具和知识库

---

## 贡献

欢迎贡献！请提交 issue 或 pull request。

### 开发指南

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

---

## 开源协议

Apache License 2.0

© 2026 ChatRaw by massif-01, RMinte® AI Technology Co., Ltd.

---

## 相关链接

- **GitHub**: https://github.com/massif-01/ChatRaw
- **Docker Hub**: https://hub.docker.com/r/massif01/chatraw
- **插件开发**: [Plugins/README.md](Plugins/README.md)
- **问题反馈**: https://github.com/massif-01/ChatRaw/issues
