# 旧验收会话清理及删除提示上线回执

2026-11-14 23:16:04 CST，目标会话 `2ed4de0d-ef0f-4dbf-9f97-7ec9d0eaab8a` 经公开 DELETE API 删除成功（HTTP 200、success=true）；其他会话和数据库记录比较一致。

- 原 run `e05b8525931c4d1585cae79770c7be3d` 保留为 `interrupted`，未改为 completed。final_text 保留原值 null。
- 原生 turn 于 2026-11-13 13:55:54.717 UTC 明确 turn_aborted/interrupted；后续主机已重启；本次 root /proc 检查无所属进程、无无法读取的进程、无对应工作区或日志文件描述符。started 标记存在，late 不存在。
- 无其他非终态任务。通过已部署 Store.settle 核销，原 1–41 事件保留，新增 seq42 interrupted 状态和 seq43 done 审计，错误代码 operator_verified_interrupted。原生日志和工作目录保留。
- Runner 共短停两次：首次 0.651 秒，因正常 shutdown 追加事件导致快照一致性检查拒绝，未执行人工核销且服务恢复；第二次停后刷新证据并成功核销，0.363 秒。最终 Runner PID12337、Hermes PID1378 均 active。时间包括维护执行和 start 返回，并非精确不可用时长。
- 私有完整账本快照：`/var/lib/chatraw-runner/operator-cleanup-e05b-20261114/runner.before.db`，同目录保存原核验及核销、删除记录；未收入 Git。

2026-11-14 23:16:27 CST，删除反馈修复 `4f7b550b830c87abb525850a3192aa7293c9461e` 已上线。仅在原 fcc75be-phone-v82 镜像上 COPY backend/agent_gateway.py 与 agents.js、app.js、app.min.js、index.html 五文件；版本 v8.3，agents.js?v=4。仅重建 Web；保留旧镜像供回退。

五文件容器哈希与指定提交一致，四个前端文件从 .99:51111 外部 HTTP 读取均 200 且哈希一致。/ready 200。部署后目标会话仍不存在，非终态任务 0。模型、设置、绑定、插件配置、Runner 配置、环境、挂载、CSS、主机 boot_id 及 Runner/Hermes 服务状态保持一致。容器环境的数组顺序发生改变，但原始环境条目逐项相同（排列重建匹配部署前哈希）。无模型请求，未重启 Hermes 或主机。

本回执证明现场清理、交付文件和服务状态；不替代用户真机 iPhone 验收。精确哈希与 API 结果见 manifest.json。
