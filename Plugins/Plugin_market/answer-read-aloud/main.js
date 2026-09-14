/** Answer Read Aloud — Aliyun Model Studio Qwen-TTS. MIT license. */
(function (ChatRaw) {
  'use strict';
  if (!ChatRaw?.utils || !ChatRaw?.settings) {
    console.error('[AnswerReadAloud] ChatRaw plugin SDK is unavailable.');
    return;
  }
  // Older hosts can execute plugin scripts twice during startup. Own one runtime.
  window._chatrawAnswerReadAloudPlugin?.destroy();
  const ID = 'answer-read-aloud';
  const SERVICE = 'aliyun-qwen-tts';
  const DEFAULTS = { region: 'beijing', voice: 'Cherry', language: 'Auto', speed: '1' };
  const ENDPOINTS = {
    beijing: 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation',
    singapore: 'https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation'
  };
  const TEXT = {
    zh: {
      title: '回答朗读', read: '朗读（AI 合成语音）', loading: '正在合成，点击取消',
      pause: '暂停朗读', resume: '继续朗读', stop: '停止朗读', empty: '这条回答没有可朗读的正文。',
      failed: '语音合成失败', audioError: '音频加载失败，请重新点击朗读。',
      blocked: '浏览器暂停了自动播放，请点击继续朗读。',
      key: '百炼 API Key', keyHint: '留空保留现有密钥；输入的新密钥仅保存到后端。',
      keyMissing: '请先填写并保存阿里云百炼 API Key。', region: '服务地域（须与 API Key 一致）',
      voice: '音色', language: '朗读语言', speed: '播放倍速',
      save: '保存', cancel: '取消', test: '保存并试听', saved: '设置已保存',
      sample: '你好，这是回答朗读的语音测试。', busy: '正在处理…',
      notice: '点击朗读才会向阿里云发送该条回答正文，按云服务用量计费。试听也会产生一次合成请求。',
      configured: '已配置', unset: '未配置', error: '操作失败，请检查网络后重试。'
    },
    en: {
      title: 'Answer Read Aloud', read: 'Read aloud (AI-generated voice)', loading: 'Generating; click to cancel',
      pause: 'Pause reading', resume: 'Resume reading', stop: 'Stop reading', empty: 'No readable text in this answer.',
      failed: 'Speech synthesis failed', audioError: 'Audio failed to load. Click read aloud to retry.',
      blocked: 'Playback requires a click. Click resume to continue.',
      key: 'Model Studio API Key', keyHint: 'Leave blank to keep the saved key. New keys are stored only on the backend.',
      keyMissing: 'Save an Aliyun Model Studio API key first.', region: 'Service region (must match API key)',
      voice: 'Voice', language: 'Speech language', speed: 'Playback speed',
      save: 'Save', cancel: 'Cancel', test: 'Save and preview', saved: 'Settings saved',
      sample: 'Hello, this is a read aloud voice test.', busy: 'Working…',
      notice: 'Only the selected answer is sent to Aliyun when clicked. Cloud usage charges apply, including previews.',
      configured: 'Configured', unset: 'Not configured', error: 'Request failed. Check your connection and retry.'
    }
  };
  const t = key => TEXT[ChatRaw.utils.getLanguage() === 'zh' ? 'zh' : 'en'][key];
  const toast = message => setTimeout(() => { if (!disposed) ChatRaw.utils.showToast(message, 'error'); }, 0);
  let disposed = false;
  let active = null;
  let settingsController = null;
  let pendingSettings = false;
  let settings = { ...DEFAULTS, ...ChatRaw.settings(ID) };
  const cache = new Map(); // Expiring signed URLs, memory-only, at most 100 chunks.
  const controls = new Map();

  function readableText(markdown) {
    // Never use rendered HTML: it can include thinking, tool output, or plugin UI.
    return String(markdown || '')
      .replace(/<think\b[^>]*>[\s\S]*?(?:<\/think>|$)/gi, '')
      .replace(/^\s*(`{3,}|~{3,})[^\n]*\n[\s\S]*?^\s*\1\s*$/gm, '')
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
      .replace(/^\s*\[[^\]]+\]:\s+\S+.*$/gm, '')
      .replace(/<https?:\/\/[^>]+>/g, '')
      .replace(/<[^>]+>/g, '')
      .replace(/^\s{0,3}(?:#{1,6}\s+|>\s*|[-+*]\s+|\d+[.)]\s+)/gm, '')
      .replace(/^\s*\|?[\s:|-]+\|[\s:|-]*$/gm, '')
      .replace(/[*_`~]/g, '')
      .replace(/\|/g, '，')
      .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&nbsp;/g, ' ')
      .replace(/\n{3,}/g, '\n\n').trim();
  }

  function splitText(text) {
    // Qwen3-TTS supports 600 characters. Use 500 UTF-16 units, sentence boundaries first.
    const parts = [];
    while (text.length > 500) {
      const prefix = text.slice(0, 500);
      let cut = Math.max(prefix.lastIndexOf('。'), prefix.lastIndexOf('！'), prefix.lastIndexOf('？'),
        prefix.lastIndexOf('\n'), prefix.lastIndexOf('. '), prefix.lastIndexOf('! '), prefix.lastIndexOf('? ')) + 1;
      if (cut < 150) cut = 500;
      if (/[\uD800-\uDBFF]/.test(text[cut - 1])) cut--;
      parts.push(text.slice(0, cut));
      text = text.slice(cut);
    }
    if (text) parts.push(text);
    return parts;
  }

  async function jsonRequest(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok || data.success === false) {
      const detail = data.error;
      throw new Error(typeof detail === 'string' ? detail : detail?.message || data.message || `${t('failed')} (HTTP ${response.status})`);
    }
    return data;
  }
  const post = (body, signal) => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal });

  async function synthesize(text, config, signal) {
    const key = JSON.stringify([config.region, config.voice, config.language, text]);
    const hit = cache.get(key);
    if (hit && hit.expires > Date.now() + 60000) return hit.url;
    cache.delete(key);
    const result = await jsonRequest('/api/proxy/request', post({
      service_id: SERVICE, url: ENDPOINTS[config.region],
      body: { model: 'qwen3-tts-flash', input: { text, voice: config.voice, language_type: config.language } }
    }, signal));
    const audio = result.data?.output?.audio;
    if (!audio?.url) throw new Error(result.data?.message || t('failed'));
    const url = new URL(audio.url);
    // Qwen returns signed OSS URLs, sometimes with HTTP. OSS supports HTTPS with the same signature.
    if (!['http:', 'https:'].includes(url.protocol) || !/^dashscope-result-[a-z0-9-]+\.oss-[a-z0-9-]+\.aliyuncs\.com$/.test(url.hostname)) {
      throw new Error(t('audioError'));
    }
    url.protocol = 'https:';
    if (cache.size >= 100) cache.delete(cache.keys().next().value);
    cache.set(key, { url: url.href, expires: Number(audio.expires_at) * 1000 || Date.now() + 3600000 });
    return url.href;
  }

  function messageAt(slot) {
    const index = Number(slot.dataset.msgIndex);
    return Number.isInteger(index) ? ChatRaw.utils.getMessages()[index] : null;
  }
  function paint() {
    for (const [slot, buttons] of controls) {
      const state = active?.slot === slot ? active.state : 'idle';
      const label = t({ idle: 'read', loading: 'loading', playing: 'pause', paused: 'resume' }[state]);
      const icon = { idle: 'volume-up', loading: 'loader-4', playing: 'pause', paused: 'play' }[state];
      if (buttons.main.title !== label) {
        buttons.main.title = label;
        buttons.main.setAttribute('aria-label', label);
        buttons.main.firstChild.className = `ri-${icon}-line`;
        buttons.main.setAttribute('aria-busy', String(state === 'loading'));
      }
      buttons.stop.hidden = state === 'idle';
    }
  }
  function stop() {
    const previous = active;
    active = null;
    if (previous) {
      previous.controller.abort();
      previous.audio.onended = previous.audio.onerror = null;
      previous.audio.pause();
      previous.audio.removeAttribute('src');
      previous.audio.load();
    }
    paint();
  }
  async function play(session) {
    try {
      await session.audio.play();
      if (active !== session) return;
      session.state = 'playing';
    } catch (error) {
      if (active !== session) return;
      if (error.name === 'NotAllowedError') {
        session.state = 'paused';
        toast(t('blocked'));
      } else { stop(); toast(t('audioError')); }
    }
    paint();
  }
  async function nextChunk(session) {
    if (active !== session) return;
    if (session.index >= session.parts.length) { stop(); return; }
    session.state = 'loading';
    paint();
    try {
      const url = await synthesize(session.parts[session.index], session.config, session.controller.signal);
      if (active !== session) return;
      session.audio.src = url;
      await play(session);
    } catch (error) {
      if (active !== session) return;
      stop();
      if (error.name !== 'AbortError') toast(error.message);
    }
  }
  function start(text, slot = null, content = null) {
    stop();
    const parts = splitText(readableText(text));
    if (!parts.length) { toast(t('empty')); return; }
    const session = {
      slot, content, chatId: ChatRaw.utils.getCurrentChatId(), parts, index: 0,
      config: { ...settings, ...ChatRaw.settings(ID) }, state: 'loading',
      audio: new Audio(), controller: new AbortController()
    };
    active = session;
    session.audio.defaultPlaybackRate = Number(session.config.speed) || 1;
    session.audio.playbackRate = session.audio.defaultPlaybackRate;
    session.audio.onended = () => { session.index++; nextChunk(session); };
    session.audio.onerror = () => {
      if (active !== session) return;
      cache.clear(); // A revoked/expired cached URL must not trap retries.
      stop(); toast(t('audioError'));
    };
    nextChunk(session);
  }
  function clickRead(slot) {
    if (active?.slot === slot) {
      if (active.state === 'loading') stop();
      else if (active.state === 'playing') { active.audio.pause(); active.state = 'paused'; paint(); }
      else play(active);
      return;
    }
    const message = messageAt(slot);
    if (message?.role === 'assistant') start(message.content, slot, message.content);
  }
  function suspend() {
    stop(); cache.clear();
    for (const [slot, { wrap }] of controls) {
      slot.parentElement?.classList.remove('answer-read-aloud-actions');
      wrap.remove();
    }
    controls.clear();
  }
  function scan() {
    if (disposed) return;
    const app = appState();
    const plugin = app?.installedPlugins?.find(p => p.id === ID);
    if (Array.isArray(app?.installedPlugins) && !plugin) { destroy(); return; }
    renderPendingSettings();
    if (plugin?.enabled === false) { suspend(); return; }
    if (active && (ChatRaw.utils.getCurrentChatId() !== active.chatId || (active.slot &&
            (!active.slot.isConnected || messageAt(active.slot)?.content !== active.content)))) stop();
    for (const [slot] of controls) if (!slot.isConnected) controls.delete(slot);
    document.querySelectorAll('.message-actions-plugin-slot').forEach(slot => {
      if (controls.has(slot) || messageAt(slot)?.role !== 'assistant') return;
      const wrap = document.createElement('span');
      wrap.className = 'answer-read-aloud-controls';
      const main = document.createElement('button');
      main.type = 'button';
      main.className = 'btn-copy';
      main.appendChild(document.createElement('i'));
      main.onclick = () => clickRead(slot);
      const stopButton = document.createElement('button');
      stopButton.type = 'button';
      stopButton.className = 'btn-copy';
      stopButton.title = t('stop');
      stopButton.setAttribute('aria-label', t('stop'));
      stopButton.innerHTML = '<i class="ri-stop-line"></i>';
      stopButton.onclick = stop;
      stopButton.hidden = true;
      wrap.append(main, stopButton);
      slot.appendChild(wrap);
      slot.parentElement.classList.add('answer-read-aloud-actions');
      controls.set(slot, { main, stop: stopButton, wrap });
    });
    paint();
  }

  function appState() {
    const root = document.querySelector('[x-data]');
    return root?._x_dataStack?.[0] || root?.__x?.$data;
  }
  function requestSettings(event) {
    if (event.detail?.pluginId !== ID) return;
    pendingSettings = true;
    renderPendingSettings();
  }
  function renderPendingSettings() {
    if (!pendingSettings || disposed) return;
    const app = appState();
    if (!app?.showPluginSettings || app.currentPluginSettings?.id !== ID) {
      pendingSettings = false;
      return;
    }
    // The host event and Alpine's x-if mount need not happen in the same frame.
    const area = document.getElementById('plugin-custom-settings-area');
    if (!area) return;
    pendingSettings = false;
    openSettings(area).catch(error => {
      if (!disposed && area.isConnected) area.textContent = error.message || t('error');
    });
  }
  async function openSettings(area) {
    settingsController?.abort();
    settingsController = new AbortController();
    const signal = settingsController.signal;
    area.replaceChildren();
    const form = document.createElement('form');
    form.className = 'answer-read-aloud-settings';
    area.appendChild(form);
    const heading = document.createElement('h3'); heading.textContent = t('title'); form.appendChild(heading);
    const note = document.createElement('p'); note.textContent = t('notice'); form.appendChild(note);
    const status = document.createElement('p'); status.setAttribute('role', 'status'); status.textContent = t('busy');
    const fields = {};
    function field(name, label, options) {
      const row = document.createElement('label'); row.textContent = label;
      const input = document.createElement(options ? 'select' : 'input');
      input.name = name;
      if (options) for (const [value, text] of options) input.add(new Option(text, value));
      else { input.type = 'password'; input.autocomplete = 'new-password'; }
      row.appendChild(input); form.appendChild(row); fields[name] = input;
    }
    field('region', t('region'), [['beijing', '北京 / Beijing'], ['singapore', '新加坡 / Singapore']]);
    field('voice', t('voice'), [['Cherry', 'Cherry'], ['Serena', 'Serena'], ['Ethan', 'Ethan']]);
    field('language', t('language'), [['Auto', 'Auto'], ['Chinese', '中文'], ['English', 'English']]);
    field('speed', t('speed'), ['0.75', '1', '1.25', '1.5', '2'].map(v => [v, `${v}×`]));
    field('key', t('key'));
    const hint = document.createElement('p'); hint.textContent = t('keyHint'); form.appendChild(hint);
    form.appendChild(status);
    const footer = document.createElement('div'); footer.className = 'answer-read-aloud-footer';
    function button(label, action) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'btn-secondary';
      b.textContent = label; b.onclick = action; footer.appendChild(b); return b;
    }
    button(t('cancel'), () => { settingsController.abort(); stop(); const app = appState(); if (app) app.showPluginSettings = false; });
    const preview = button(t('test'), () => save(true));
    const saveButton = button(t('save'), () => save(false));
    form.appendChild(footer);
    form.onsubmit = e => { e.preventDefault(); save(false); };
    preview.disabled = saveButton.disabled = true;
    let hasKey = false;
    try {
      const [plugin, keys] = await Promise.all([
        jsonRequest(`/api/plugins/${ID}/manifest`, { signal }), jsonRequest('/api/plugins/api-keys', { signal })
      ]);
      if (signal.aborted || disposed || !form.isConnected) return;
      settings = { ...DEFAULTS, ...plugin.settings_values };
      for (const name of Object.keys(DEFAULTS)) fields[name].value = settings[name];
      hasKey = Boolean(keys.api_keys?.[SERVICE]);
      fields.key.placeholder = t(hasKey ? 'configured' : 'unset');
      status.textContent = '';
      preview.disabled = saveButton.disabled = false;
    } catch (error) { if (!signal.aborted) status.textContent = error.message; }
    async function save(withPreview) {
      if (saveButton.disabled) return;
      preview.disabled = saveButton.disabled = true;
      status.textContent = t('busy');
      try {
        const newKey = fields.key.value.trim();
        if (!hasKey && !newKey) throw new Error(t('keyMissing'));
        if (newKey) {
          await jsonRequest('/api/plugins/api-key', post({ service_id: SERVICE, api_key: newKey }, signal));
          hasKey = true; fields.key.value = ''; fields.key.placeholder = t('configured'); cache.clear();
        }
        const values = Object.fromEntries(Object.keys(DEFAULTS).map(name => [name, fields[name].value]));
        await jsonRequest(`/api/plugins/${ID}/settings`, post({ settings: values }, signal));
        if (signal.aborted || disposed) return;
        stop(); settings = values;
        const app = appState();
        const installed = app?.installedPlugins.find(p => p.id === ID);
        if (installed) installed.settings_values = { ...values };
        status.textContent = t('saved');
        if (withPreview) start(t('sample'));
        else if (app) app.showPluginSettings = false;
      } catch (error) { if (!signal.aborted) status.textContent = error.message || t('error'); }
      finally { preview.disabled = saveButton.disabled = false; }
    }
  }
  const style = document.createElement('style');
  style.textContent = '.answer-read-aloud-actions{opacity:1}.answer-read-aloud-controls{display:inline-flex;align-items:center;gap:4px}.answer-read-aloud-controls [hidden]{display:none!important}.answer-read-aloud-settings{padding:24px;display:flex;flex-direction:column;gap:14px;max-height:70vh;overflow:auto}.answer-read-aloud-settings p{font-size:13px;color:var(--text-secondary);line-height:1.6;margin:0}.answer-read-aloud-settings label{display:flex;flex-direction:column;gap:6px;font-size:14px}.answer-read-aloud-settings input,.answer-read-aloud-settings select{width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--border-color);border-radius:8px;background:var(--bg-primary);color:var(--text-primary)}.answer-read-aloud-footer{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}';
  document.head.appendChild(style);
  const observer = new MutationObserver(scan);
  observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-msg-index'] });
  // Chat changes can preserve identical DOM nodes; check the host chat identity as well.
  const timer = setInterval(scan, 500);
  window.addEventListener('plugin-settings-open', requestSettings);
  window.addEventListener('pagehide', stop);
  function destroy() {
    if (disposed) return;
    disposed = true; suspend(); observer.disconnect(); clearInterval(timer);
    settingsController?.abort(); cache.clear();
    window.removeEventListener('plugin-settings-open', requestSettings);
    window.removeEventListener('pagehide', stop);
    style.remove();
    if (window._chatrawAnswerReadAloudPlugin === runtime) delete window._chatrawAnswerReadAloudPlugin;
  }
  const runtime = { destroy };
  window._chatrawAnswerReadAloudPlugin = runtime;
  // New hosts stop synchronously. Original hosts are monitored by scan() (<=500ms).
  // Keep the settings listener while disabled; replacement/uninstall destroys it.
  ChatRaw.onCleanup?.(suspend);
  if (appState()?.showPluginSettings && appState()?.currentPluginSettings?.id === ID) pendingSettings = true;
  scan();
})(window.ChatRawPlugin);
