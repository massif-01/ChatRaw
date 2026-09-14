# 测试说明

测试需要一个单独运行的、原版或已应用兼容补丁的 ChatRaw 实例，并已安装本插件。不要在真实聊天数据所在页面运行浏览器测试；测试会替换页面消息并启停插件。

## 后端代理测试

使用 ChatRaw 的 Python 环境，将 ChatRaw 源码根目录加入 `PYTHONPATH`，执行ChatRaw 仓库的测试文件。例如将下面的路径替换为实际路径：

```sh
PYTHONPATH=/path/to/ChatRaw /path/to/ChatRaw/.venv/bin/python backend/test_read_aloud_proxy.py -v
```

两个测试使用临时 DATA_DIR 和模拟云端响应，验证服务端追加密钥、音频元数据透传、错误透传，不请求真实云端。

## 浏览器测试

从ChatRaw 仓库根目录生成测试用静音 WAV：

```sh
mkdir -p output/playwright
python3 - <<'PY'
import wave
with wave.open('output/playwright/read-aloud-silence.wav', 'wb') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(8000)
    f.writeframes(b'\0' * (8000 * 2 * 30))
PY
```

用 Playwright CLI 打开隔离的 ChatRaw 页面，等待插件加载，然后使用 `run-code` 执行 `script/read_aloud_browser_smoke.js` 的完整内容。每次从新刷新过的页面运行。

测试拦截语音代理和 OSS 音频请求，验证 14 项：按钮唯一性、请求模型、Markdown 清理、浏览器请求不带密钥、暂停、停止释放资源、缓存重播、单音频播放、切换对话停止、迟到响应不会恢复已取消的播放、云端错误恢复、长文完整分段、停用清理、重新启用。

测试结束请关闭测试浏览器；页面内的模拟路由会影响真实试听。

## 真实云端验收

需要自己的百炼 API Key，在插件设置点击「保存并试听」，再朗读实际回答。确认声音、发音、首段等待、段间停顿和云端计费。模拟测试不能代替此项，v1.0.1 尚未用真实密钥验收。

## v1.0.1 兼容性回归

在上游 b910c45 原版（没有 onCleanup）上复现 v1.0.0 的 Loading，再用相同实例安装 v1.0.1。`script/read_aloud_settings_smoke.js` 验证设置表单出现、保存、延迟挂载、重复加载与停用后设置可用。
