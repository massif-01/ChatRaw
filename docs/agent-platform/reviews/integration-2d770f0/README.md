# 总控集成接收端验证

源码固定在 `2d770f0e079652d2dc99b49124d60f3305c8c393`；2026-11-12，macOS arm64。
本记录不代替 E/F 的独立验收，也不代表 RM-01 已部署。

## 真实网关与两个浏览器

运行：

```sh
PYTHON=/Users/massif/.codex/worktrees/04ec/ChatRaw/.venv/bin/python \
CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
node scripts/test-agent-gateway-ui.mjs
```

Python 3.12.4，Chrome 157.0.8103.51。真实 ChatRaw ASGI、Runner HTTP 和 SQLite，
原生端使用 ControlledAdapter。通过本地插件安装、设置保存、附件传递、首个浏览器关闭后
继续运行、第二个独立浏览器审批、工作目录文件副作用、最终文本替换与刷新后单条落库。
测试结束清理临时服务和数据。这里没有发起真实模型服务请求。

## 最终 Docker 镜像与持久卷

```sh
docker build -t chatraw-agent-integration:local .
python3 scripts/test-docker-persistence.py
```

镜像 `sha256:d7c7c969d43bdaf41c70a6e9d60001ad50139afa212029fa41e5feeb82d45bf7`，
linux/arm64。镜像未配置 Runner；容器使用 `--network none`，请求由容器内部 loopback 发出。

通过结果：

- 无 Runner 时普通界面和 API 可启动，实际提供的四个前端文件与集成工作树逐字节一致。
- 五 Agent 插件及 Markdown 增强插件全部经本地市场 API 安装；嵌套 KaTeX 字体与包内原件一致。
- 移除首个容器，再用同一个命名数据卷创建新容器，聊天记录 ID、六插件及嵌套字体均保留。
- 五 Agent 显示已安装但不可就绪；主镜像找不到五款原生 CLI，没有把 Agent 执行程序混入主容器。

自动化仅移除本次随机命名的测试容器和数据卷。详细镜像与前端摘要见
[docker-persistence.json](docker-persistence.json)。复现脚本另记录实际镜像平台。

这是容器替换与数据卷的验证，不是整机重启、宿主 Runner 原生进程恢复或 RM-01 x86_64 验收。

## 标题与 Claude 答案增量后的复验

在 `165a509d1eb6acf1c2f1f3ad55b6bc56f34c38b6` 再次通过同一真实网关双浏览器脚本，
并重建镜像、重跑无网络及持久卷替换检查。最终镜像为
`sha256:862d9554ea8783098c34e7aace2e020fea40bc7937d96aff432f1e54c46d0b9e`。
四个前端文件摘要与原固定版本一致。记录见
[docker-persistence-165a509.json](docker-persistence-165a509.json)。
这次只针对已合入的两个增量复核集成，不重复五款原生程序的无关测试。
