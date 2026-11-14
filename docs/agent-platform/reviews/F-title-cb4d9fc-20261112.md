# F：Agent 标题增量复验

**通过，`cb4d9fc786d3284bcaebaadfb1d670d49f931315` 无新增阻塞，可集成。**

保留原 `2d770f0` 快照不动；新建 `/private/tmp/chatraw-f-title-cb4d9fc.fok5OD`，基于 `2d770f0` 仅叠加该提交的 `backend/agent_storage.py` 和 `backend/test_agent_titles.py`。其他主实现未变。

核对结果：只在首条用户显示消息的同一 SQLite 事务中，将默认 `New Chat` 初始化为输入前 30 字符，超长加 `...`；不调用模型。有用户消息后不再命名，既有/手工标题保留，重复投影不重命名，compact 不命名。

使用 A 的 Python 3.12.4 venv，运行 **4 项标题存储测试＋1 项网关离线投影/幂等回归，5/5 通过**。没有重跑无关叶模块或全量验收。

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/massif/.codex/worktrees/04ec/ChatRaw/.venv/bin/python -B -m unittest -v \
  backend.test_agent_titles \
  backend.test_agent_gateway.GatewayTests.test_native_context_and_offline_completion_are_persisted_once
```

在新快照目录执行。证据：[tests.log](title-cb4d9fc-evidence/tests.log)。本轮没有浏览器截图验收，没有修改业务代码、推送或部署。

本项不关闭 [F-PLAT-01](F-platform-2d770f0-20261112.md) 的 Claude 多选＋自定义文本阻塞；该项待 C 修复提交到达后单独复验。
