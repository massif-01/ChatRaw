// Run against an isolated ChatRaw test instance using playwright-cli run-code.
// No real cloud requests or speech: the upstream and WAV audio are fixtures.
async (page) => {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => {
    const app = document.querySelector('[x-data]')._x_dataStack[0];
    app.lang = 'zh'; app.showPlugins = false; app.showPluginSettings = false;
    app.currentChatId = 'tts-qa';
    app.messages = [{ role: 'user', content: '请介绍这个朗读功能。' },
      { role: 'assistant', content: '## 回答朗读\n点击小喇叭，支持**暂停、继续和停止**。' },
      { role: 'assistant', content: '第二条测试回答。' }];
  });
  const requests = [];
  const results = [];
  let mode = 'ok';
  await page.route('https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/**', route => route.fulfill({
    status: 200, contentType: 'audio/wav', path: 'output/playwright/read-aloud-silence.wav'
  }));
  await page.route('**/api/proxy/request', async route => {
    const body = route.request().postDataJSON();
    requests.push(body);
    const requestMode = mode;
    if (requestMode === 'delay') await page.waitForTimeout(500);
    if (requestMode === 'error') return route.fulfill({ status: 401, json: { success: false, error: { message: 'InvalidApiKey (test fixture)' } } });
    await route.fulfill({ json: { success: true, data: { output: { audio: {
      url: `http://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/qa/${requests.length}.wav`,
      expires_at: Math.floor(Date.now() / 1000) + 3600
    } } } } });
  });
  const check = (condition, label) => { if (!condition) throw new Error(label); results.push(label); };
  const read = () => page.getByRole('button', { name: '朗读（AI 合成语音）', exact: true });
  const pause = () => page.getByRole('button', { name: '暂停朗读', exact: true });
  const stop = () => page.getByRole('button', { name: '停止朗读', exact: true });
  await page.evaluate(() => {
    window.__ttsAudio = [];
    const NativeAudio = window.__ttsNativeAudio || window.Audio;
    window.__ttsNativeAudio = NativeAudio;
    window.Audio = function () { const audio = new NativeAudio(); window.__ttsAudio.push(audio); return audio; };
  });
  await page.waitForFunction(() => document.querySelectorAll('[aria-label="朗读（AI 合成语音）"]').length === 2);
  check(await read().count() === 2, 'Exactly one read button per assistant answer');
  await read().first().click(); await pause().waitFor();
  check(requests.length === 1 && requests[0].body.model === 'qwen3-tts-flash', 'Uses Qwen-TTS request contract');
  check(!requests[0].body.input.text.includes('**') && !requests[0].body.input.text.includes('##'), 'Markdown cleaned before synthesis');
  check(!JSON.stringify(requests[0]).includes('api_key') && !requests[0].headers, 'No cloud credentials in browser synthesis request');
  await pause().click(); await page.getByRole('button', { name: '继续朗读', exact: true }).waitFor();
  check(await page.evaluate(() => window.__ttsAudio.at(-1).paused), 'Pause stops actual HTMLAudioElement');
  await page.getByRole('button', { name: '继续朗读', exact: true }).click(); await pause().waitFor();
  await stop().click();
  check(await page.evaluate(() => window.__ttsAudio.every(a => a.paused && !a.getAttribute('src'))), 'Stop releases audio sources');
  await read().first().click(); await pause().waitFor();
  check(requests.length === 1, 'Replay reuses unexpired cached audio');
  await read().click(); await pause().waitFor();
  check(await page.evaluate(() => window.__ttsAudio.filter(a => !a.paused).length === 1), 'Switching answers leaves one audio playing');
  await page.evaluate(() => { document.querySelector('[x-data]')._x_dataStack[0].currentChatId = 'tts-other'; });
  await page.waitForFunction(() => window.__ttsAudio.every(a => a.paused));
  check(await read().count() === 2, 'Changing chat stops playback without duplicate buttons');
  mode = 'delay';
  await page.evaluate(() => { document.querySelector('[x-data]')._x_dataStack[0].messages[2].content = '延迟合成测试'; });
  await read().last().click(); await page.getByRole('button', { name: '正在合成，点击取消', exact: true }).waitFor();
  await page.getByRole('button', { name: '正在合成，点击取消', exact: true }).click();
  mode = 'ok';
  await page.waitForTimeout(600);
  check(await page.evaluate(() => window.__ttsAudio.every(a => a.paused)), 'Canceled synthesis never starts late playback');
  mode = 'error';
  await read().last().click(); await page.getByText('InvalidApiKey (test fixture)', { exact: true }).waitFor();
  check(await read().count() === 2, 'Cloud error is shown and read control recovers');
  mode = 'ok';
  const before = requests.length;
  const longText = Array.from({length: 100}, (_, i) => `第${i}段长回答包含数字123和中文。`).join('');
  await page.evaluate(text => { document.querySelector('[x-data]')._x_dataStack[0].messages[2].content = text; }, longText);
  await read().last().click(); await pause().waitFor();
  for (let n = 0; n < 5; n++) {
    if (await pause().count() === 0) break;
    await page.evaluate(() => window.__ttsAudio.at(-1).dispatchEvent(new Event('ended')));
    await page.waitForFunction(() => !document.querySelector('[aria-label="正在合成，点击取消"]'));
  }
  const chunks = requests.slice(before).map(r => r.body.input.text);
  check(chunks.length > 1 && chunks.every(s => s.length <= 500) && chunks.join('') === longText, 'Long answer is read completely in ordered bounded chunks');
  await read().first().click(); await pause().waitFor();
  await page.evaluate(async () => {
    const app = document.querySelector('[x-data]')._x_dataStack[0];
    await app.togglePlugin(app.installedPlugins.find(p => p.id === 'answer-read-aloud'));
  });
  await page.waitForFunction(() => document.querySelectorAll('.answer-read-aloud-controls').length === 0);
  check(await page.locator('.answer-read-aloud-controls').count() === 0 && await page.evaluate(() => window.__ttsAudio.every(a => a.paused)), 'Disable removes controls and stops audio');
  await page.evaluate(async () => {
    const app = document.querySelector('[x-data]')._x_dataStack[0];
    await app.togglePlugin(app.installedPlugins.find(p => p.id === 'answer-read-aloud'));
  });
  await read().first().waitFor();
  check(await read().count() === 2, 'Re-enable registers exactly one control per answer');
  return { passed: results.length, results };
};
