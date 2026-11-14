# ChatRaw 回答朗读

为 ChatRaw 的助手回答添加小喇叭，点击后通过**阿里云百炼 Qwen-TTS**朗读正文。

**MIT 开源。源码和安装包均公开，下载无需登录 GitHub。** 使用云端语音需要自行配置百炼 API Key，并按阿里云用量计费。

## 下载

- [插件安装包 v1.0.1](https://github.com/wowalxa2-tech/ChatRaw-AnswerReadAloud/releases/download/v1.0.1/answer-read-aloud-1.0.1.zip)
- [SHA-256 校验文件](https://github.com/wowalxa2-tech/ChatRaw-AnswerReadAloud/releases/download/v1.0.1/SHA256SUMS)
- [全部版本](https://github.com/wowalxa2-tech/ChatRaw-AnswerReadAloud/releases)

## 安装

### 1. 升级旧版本

**v1.0.1 可以直接安装到原版 ChatRaw，无需修改主程序或应用补丁。** 已在上游 `b910c45d32c37b2f7cd0e5155163368f25baf6e9` 原版和带 `onCleanup` 的宿主上验证。

如果 v1.0.0 打开设置一直显示 `Loading...`，请下载本页的 v1.0.1 安装包，通过「本地安装」重新上传覆盖，刷新页面后确认插件版本为 **1.0.1**，并启用插件再打开设置。原有服务端密钥会保留；原版宿主重新上传 ZIP 会重置插件选项，升级后请重新确认地域、音色和倍速。

v1.0.0 错误地依赖主程序新增的清理接口；v1.0.1 取消了这一依赖，并处理原版主程序重复加载脚本与设置容器延迟挂载的情况。已经应用旧补丁的主程序也可以继续使用。

此插件面向 ChatRaw 前端插件架构，不保证适配其他同名分支或 Module / Companion Plugin 架构。宿主仍需提供插件 SDK、消息操作插槽和密钥代理接口。

### 2. 安装插件

打开 ChatRaw → **插件 → 本地安装**，上传下载的 `answer-read-aloud-1.0.1.zip`。

也可使用支持源地址安装的 ChatRaw 版本，从下面的公开目录安装：

```text
https://raw.githubusercontent.com/wowalxa2-tech/ChatRaw-AnswerReadAloud/v1.0.1
```

### 3. 配置并试听

打开 **已安装 → 回答朗读 → 设置**：

1. 选择服务地域：北京或新加坡，须与 API Key 所属地域一致。
2. 填入**阿里云百炼 Model Studio API Key**。
3. 选择音色、语言和播放倍速。
4. 点击 **保存并试听**，确认账号权限与实际声音。

使用的是百炼 Qwen-TTS，不是旧版「智能语音交互」的 AppKey / AccessToken，也不是阿里云账号 AccessKey。原来的聊天模型无需更换。

## 功能

- 回答生成结束后显示朗读按钮；播放中可暂停、继续或停止。
- 合成过程中再次点击按钮可取消等待。
- 长回答按句子优先分段，顺序合成与播放，避免超出单次输入限制。
- 当前页面缓存最多 100 段未过期的音频地址，重复朗读可减少重复合成。
- 同时只播放一条回答；切换对话、修改正在朗读的回答、停用插件时停止。原版宿主的生命周期检查间隔最多 500ms。
- 音色：Cherry / Serena / Ethan；语言：自动 / 中文 / 英文；播放倍速：0.75–2 倍。
- 中英文设置界面，支持手机布局。

## 数据与费用

只有点击朗读或试听时才会请求云端。朗读提交所选助手回答正文，不提交整段对话、用户问题或独立的思考与工具事件字段。代码块和 Markdown 标记会被清理，复杂公式和表格的朗读效果有限。

密钥使用 ChatRaw 现有后端存储与代理接口，不写入插件源码或 localStorage。浏览器播放云端返回的临时签名 OSS 音频地址。缓存仅存在当前页面内存，刷新或停用后清空。

停止会取消浏览器等待，并阻止后续片段提交；已到达阿里云的请求仍可能完成并计费。长文片段之间可能有等待。本插件不是实时双向语音对话。

## 验证情况

已完成本地 ZIP 安装、14 项模拟浏览器播放测试、2 项后端代理测试，以及设置保存、倍速、手机布局和新回答朗读流程检查。测试的云端响应和音频为模拟数据，**未用真实百炼密钥验收语音质量、账号权限或云端网络可达性**。安装者请通过「保存并试听」完成实际验证。

[测试说明](../../../docs/read-aloud-testing.md) · [阿里云 Qwen-TTS API](https://help.aliyun.com/zh/model-studio/qwen-tts-api)

## 从源码构建安装包

需要 Python 3，无额外依赖：

```sh
python3 -m zipfile -c answer-read-aloud-1.0.1.zip Plugins/Plugin_market/answer-read-aloud
```

从 ChatRaw 仓库根目录运行，安装包生成在当前目录。插件本身不需要新增 Python 后端依赖。

## 许可与上游

[MIT License](LICENSE)。适配 [ChatRaw](https://github.com/massif-01/ChatRaw)，保留其许可证及版权声明。
