# DeepSeek 官方 Flash 隔离复验（缩围收尾）

2026-11-14。用户中途明确缩小官方复验范围：DeepSeek继续覆盖不确定项；其它路由之前本地模型明确通过的项目沿用旧证据。没有把沿用本地证据写成官方实测通过。手机实机仍按用户要求暂缓。

本轮未修改产品运行源码，也没有发现足以确认、需要代码修复的新接入缺陷。以下真实失败和质量限制完整保留，没有为通过而改写历史或追加变体。

## 结果

|范围|结论|
|---|---|
|旧失败历史交官方Flash|仍错误否认提权；旧Qwen reasoning随历史保留，不代表官方全新会话|
|DeepSeek全新拒绝／允许|两条真实UI决定、原生结果、文件副作用及最终总结均一致|
|DeepSeek前台工具停止|cancelled；原bash/sleep两进程退出；完整30秒窗口后无late标记|
|DeepSeek续接／压缩／重启恢复|同一原生ID、正确回忆标记；真实compaction/start-summary-end，压缩16个历史项|
|DeepSeek多轮图片|失败：111978误读为119780；不能改判通过|
|原Files对象的单次空历史对照|正确读出111978，但附带解释，未遵守只输出数字；不覆盖上条失败|
|Codex官方Responses|真实apply_patch、单次文件批准、准确落盘及结果回送通过|
|Codex剩余、Claude、Pi、Hermes、普通聊天官方矩阵|按用户缩围未启动；仅沿用已明确通过的本地证据|

[小矩阵](summary.json)给出逐项证据入口。DeepSeek新会话拒绝和允许、Codex文件变更的实际页面由总控/E记录，E只读UI回放提交为`1a0306a`。

## 图片边界

输入PNG和原生归一化JPEG均为284×80，二值像素相同。native attachmentId、Files variantId、上传字节数与索引对应。官方只读metadata确认同一fileId、image/jpeg和3632bytes。没有公开受支持的图像content下载接口，未猜测下载路由；原多轮请求的HTTP图像body未捕获，因此不宣称已穷尽排除所有传输层。

最后一次已授权对照仍引用原fileId、不上传/换图，空历史、Flash/high、2048上限，不声明工具。3.892秒，输入234、输出699tokens，end_turn，正确识别111978。它说明该Files对象在这一次条件下可读；不能由单次成功推断原多轮失败已修复。

## 调用与费用

[usage-summary.json](usage-summary.json)及[逐组台账](usage-ledger.jsonl)：可核对17次生成，未缓存输入43650、缓存输入135808、输出15821tokens（reasoning已包含，不重复计入）。按当时非高峰官方单价估算US$0.01644752，约1.64美分。缓存和原生压缩用量均计入。

这些是有原生usage/直接API收据的模型生成数，不是全部SDK元数据/Files HTTP请求的逐包计数。没有调用付费搜索、网页抓取、OCR等无关服务；不以估算代替账单。[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)

## 隔离与停用

- ChatRaw：同主环境镜像`sha256:09bda4d9…580f`，独立容器`chatraw-official-test`、卷`chatraw_official_test_data`，仅绑定127.0.0.1:51211。
- Runner：独立`chatraw-official-test-runner`，127.0.0.1:51212；`/etc/chatraw-official-test`、`/var/lib/chatraw-official-test`和五Agent目录独立，运行源码逐文件与主Runner一致。
- Hermes只准备了独立home/lock目录，未创建或启动隔离Gateway，51213未使用。C的Codex/Claude配置仅写入隔离目录；所有主/辅助模型别名指向Flash，搜索禁用。未升级原生CLI。
- 8个隔离Agent run均终态；两个直接HTTP对照也已结束。仅停止本轮确切Runner服务和容器，状态分别inactive/exited。持久数据、配置和0600凭据保留，未为归档重启服务/隧道。
- 主51111容器仍运行，主Runner/Hermes仍active、PID保持3424/1378，boot ID未变；旧unknown保留。官方Key不在主服务进程环境或主配置中，未发往.98。未重启整机、未改.98、未覆盖原homes。

详见[native-final-and-isolation.json](native-final-and-isolation.json)。原始官方请求/响应在`/tmp/chatraw-official-flash-20261114`受限目录；仓库未收录Key、Authorization或reasoning正文。

## 旧聊天基线说明

旧“12条消息”基线已经过期，不能声称当前仍保留。主访问日志显示该chatId于北京时间01:16:49收到DELETE并返回200，早于本轮03:07:15首次官方认证请求；当前chat/messages不存在而binding保留。只读核对旧12个ID均缺失，没有恢复、清账或改写。日志不能确定操作者，也不能据此证明整个主数据库无变化。[有界旁证](main-old-chat-preexisting-deletion.json)
