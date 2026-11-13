# Hermes 图标更新：只读确认与部署准备

2026-11-13。仅只读检查，等待 B 的新图标及精确 SHA256；尚未构建或更新资产。

已安装图标为 `/app/data/plugins/installed/hermes/icon.png`，位于命名数据卷 `chatraw_chatraw_data`。市场源为当前镜像中的 `/app/Plugins/Plugin_market/hermes/icon.png`。二者当前均为128×128 PNG、6786 bytes，SHA256 e441d6860d5e4621811dcb3a242ce37583d8b44d6fc7724fcf9cf0989069656e。

HTTP端点分别是 `/api/plugins/hermes/icon` 和 `/api/plugins/market/hermes/icon`。两者200，Content-Type image/png，ETag和Last-Modified存在；未设置Cache-Control/Expires。现有Last-Modified是2026-06-11，前端使用无版本参数的相同URL。浏览器可能沿用旧缓存，已有页面不会因宿主文件替换自动换图；部署验证应显式no-cache取回原URL并比较新哈希，用户页面需要刷新，必要时强制刷新。此次资产范围不自动扩展成缓存代码修改。

收到B资产后的最小持久化步骤：

1. 校验精确文件、PNG尺寸/哈希，以现用 `chatraw-agent-integration:2ba163e-ui` 为基底构建只COPY市场icon.png的派生镜像，保留已验前端修复与全部依赖。不使用旧图标提前构建。
2. 记录插件config.json与Hermes目录非icon文件哈希、用户聊天/配置摘要、容器挂载和Runner/Hermes PID。确认部署窗口，不取消任何Agent任务。
3. 从新镜像取同一图标原子替换命名卷里的 `plugins/installed/hermes/icon.png`。只替换该文件，不调用卸载/重装API，不覆盖manifest/main.js或插件config.json。
4. 更新预构建image overlay，仅重建ChatRaw容器，保留项目chatraw、原卷和只读token挂载。镜像内市场源必须属于新镜像，不能仅热拷贝旧容器充当最终交付。Runner和Hermes服务不动。
5. 验证两个原HTTP端点均返回新SHA256、ETag改变、/ready正常；检查插件设置和其他文件哈希、原消息及原生服务PID保持一致。没有模型调用。

安装副本随原卷持久化，市场副本随派生镜像持久化。原图可从现用2ba163e-ui镜像取回，回退也只针对这两个副本，不通过重装恢复。

响应原始元数据见 [50-hermes-icon-before-http.json](50-hermes-icon-before-http.json)。
