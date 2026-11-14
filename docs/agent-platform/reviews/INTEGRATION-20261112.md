# 总控分批集成记录

## M0：6874553

- 集成A骨架02b25bd，冻结CONTRACT v1，保存六任务书、F首轮报告及基线证据。
- 总控独立检查身份/私有binding/unknown/停止确认语义及契约测试；5项模拟测试通过，git diff --check通过。
- 无旧运行代码改动，不能视为Agent已接入。

## E首批资源集成

- 来源e8db0e0；70个资源/许可证SHA，固定npm依赖，可复现构建、入口patch及真实109验证脚本。
- 总控检查vendor复制与校验、测试临时DATA_DIR和回环模型、npm ci及vendor:check通过。
- npm audit报告PostCSS8.5.15在sourceMappingURL处理上的高/中危公告；只更新PostCSS到8.5.32并刷新lock，vendor:check和build通过。
- 依据：https://github.com/advisories/GHSA-r28c-9q8g-f849 、https://github.com/advisories/GHSA-fxqj-rqcc-2cmp 。该库仅在Node构建阶段使用，不由浏览器执行。本次不使用强制批量升级。
- 剩余4项low：esbuild开发服务器/KaTeX在已有原型污染前提下的trust限制。实际产品使用面与输出净化交后续F复核；不作无漏洞承诺。
- 入口patch交B合入，其新renderer和正式Agent界面仍待集成。总控此批不改入口，也不提交临时重建的min资源；最终B交付后统一生成。
- E的旧基线真实Chromium109/macOS证据保留原报告；不扩展成Win8或新五Agent版本已通过的结论。
