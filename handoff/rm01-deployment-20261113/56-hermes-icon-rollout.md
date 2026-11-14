# Hermes 图标持久化上线

2026-11-13。仅部署B提交b5cafcde302c33535f4359faf005fc8150b94734的icon.png；没有模型调用、Runner/Hermes重启、插件重装或其他产品改动。

当前镜像tag：`chatraw-agent-integration:b5cafcd-icon`。镜像ID：`sha256:5e1ae59dfa5c07ffbfcdf1ed38441ad57bfe5f867405a2e747d6ffe68214d026`。以现用2ba163e-ui为基底，仅新增市场icon.png COPY层，保留全部原镜像层、Env、Cmd、已上线任务详情修复和依赖。

新图标128×128、2103 bytes，SHA256 `84dc1a015ab2055e774f1b0425e16d7f6a7611face26dfb186378f78f28b8d65`。镜像市场源是 `/app/Plugins/Plugin_market/hermes/icon.png`；持久安装副本是命名卷chatraw_chatraw_data中的 `/app/data/plugins/installed/hermes/icon.png`。

使用新镜像启动一次无网络的维护容器，仅挂载原数据卷，以临时文件加原子rename替换已安装icon，保留原owner/mode。未触碰插件manifest、main.js或config.json。随后更新活动compose.prebuilt.yml并仅重建ChatRaw；旧overlay保存为compose.prebuilt.2ba163e-ui.yml。没有将市场图标热拷贝进旧容器充当最终镜像。

宿主构建包位于 `/home/rm01/chatraw/hermes-icon-b5cafcd`。活动overlay仍在 `/home/rm01/chatraw/deployment-e91d32f/compose.prebuilt.yml`；项目名chatraw、原卷和只读token挂载保持不变。

## 验证

- `/api/plugins/hermes/icon` 与 `/api/plugins/market/hermes/icon` 均返回200、image/png、新文件精确SHA256。两请求携带旧ETag，仍正确收到新图标且ETag已变。
- `/ready` 返回ready/database connected。
- 全局插件config.json哈希前后一致；Hermes manifest.json/main.js哈希一致，未删除或重置设置。
- 用户原Codex聊天12条消息的完整序列哈希、绑定一致；模型配置和普通设置哈希一致。
- Runner PID62709、Hermes PID34685未变；原Codex unknown run快照原样保留。
- 部署前没有其他真实执行中任务；未取消会话、提交prompt或操作原生Agent。

缓存策略未扩展修改：两个端点仍有ETag/Last-Modified、无显式Cache-Control，前端URL不带版本。已有页面需刷新才能获取新图标；若浏览器继续显示缓存可强制刷新。本轮HTTP取回在原URL上验证，没有通过改URL掩盖旧资源。

证据：50号路径/缓存调查；51号源文件哈希和Dockerfile；52号前后快照；53构建日志；54部署脚本/日志；55两端点和数据保留检查；56-icon-image-proof.json镜像继承证明。
