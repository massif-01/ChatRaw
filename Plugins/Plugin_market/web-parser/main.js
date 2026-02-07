/**
 * Enhanced Web Parsing Plugin for ChatRaw
 * Parse web pages for chat context: browser parsing, Firecrawl API, or Jina Reader
 *
 * @version 1.0.0
 * @author ChatRaw
 * @license Apache-2.0
 */
(function(ChatRaw) {
    'use strict';

    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[WebParser] ChatRawPlugin not available');
        return;
    }

    const PLUGIN_ID = 'web-parser';
    const FIRECRAWL_SERVICE = 'firecrawl';
    const JINA_SERVICE = 'jina';

    let pluginSettings = {
        parser_mode: 'browser'
    };

    const i18n = {
        en: {
            parserMode: 'Parsing mode',
            parserModeHint: 'Choose how to extract content from web pages.',
            browserMode: 'Browser parsing',
            browserModeDesc: 'No API key. Parses in browser (lightweight).',
            firecrawlMode: 'Firecrawl API',
            firecrawlModeDesc: 'High quality, headless. Requires API key.',
            jinaMode: 'Jina Reader',
            jinaModeDesc: 'Markdown output. API key optional for higher limit.',
            firecrawlKeyLabel: 'Firecrawl API Key',
            firecrawlKeyHint: 'Get your API key from firecrawl.dev',
            firecrawlKeyPlaceholder: 'Enter API Key',
            jinaKeyLabel: 'Jina Reader API Key',
            jinaKeyHint: 'Optional. Get from jina.ai for higher rate limit.',
            jinaKeyPlaceholder: 'Enter API Key (optional)',
            verify: 'Verify',
            verifying: 'Verifying...',
            verifySuccess: 'API Key is valid!',
            verifyFailed: 'Verification failed',
            save: 'Save',
            cancel: 'Cancel',
            settingsSaved: 'Settings saved',
            saveFailed: 'Save failed',
            apiKeySet: 'API Key is set',
            apiKeyNotSet: 'API Key not set'
        },
        zh: {
            parserMode: '解析方式',
            parserModeHint: '选择如何从网页提取正文。',
            browserMode: '浏览器解析',
            browserModeDesc: '无需 API Key，在浏览器内解析（轻量）。',
            firecrawlMode: 'Firecrawl API',
            firecrawlModeDesc: '高质量、无头渲染，需配置 API Key。',
            jinaMode: 'Jina Reader',
            jinaModeDesc: '输出 Markdown，API Key 可选以提高限额。',
            firecrawlKeyLabel: 'Firecrawl API Key',
            firecrawlKeyHint: '从 firecrawl.dev 获取 API Key',
            firecrawlKeyPlaceholder: '输入 API Key',
            jinaKeyLabel: 'Jina Reader API Key',
            jinaKeyHint: '可选。从 jina.ai 获取以提高限额。',
            jinaKeyPlaceholder: '输入 API Key（可选）',
            verify: '验证',
            verifying: '验证中...',
            verifySuccess: 'API Key 有效！',
            verifyFailed: '验证失败',
            save: '保存',
            cancel: '取消',
            settingsSaved: '设置已保存',
            saveFailed: '保存失败',
            apiKeySet: 'API Key 已设置',
            apiKeyNotSet: 'API Key 未设置'
        }
    };

    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }

    async function loadSettings() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin && plugin.settings_values) {
                    pluginSettings = { ...pluginSettings, ...plugin.settings_values };
                }
            }
        } catch (e) {
            console.error('[WebParser] Failed to load settings:', e);
        }
    }

    async function saveSettings() {
        try {
            const res = await fetch(`/api/plugins/${encodeURIComponent(PLUGIN_ID)}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: pluginSettings })
            });
            if (res.ok) {
                ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                return true;
            }
            const err = await res.json().catch(() => ({}));
            throw new Error(err.error || 'Save failed');
        } catch (e) {
            console.error('[WebParser] Failed to save settings:', e);
            ChatRaw.utils?.showToast?.(t('saveFailed') + ': ' + e.message, 'error');
            return false;
        }
    }

    async function saveApiKey(serviceId, apiKey) {
        try {
            const res = await fetch('/api/plugins/api-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service_id: serviceId, api_key: apiKey })
            });
            return res.ok;
        } catch (e) {
            console.error('[WebParser] Failed to save API key:', e);
            return false;
        }
    }

    async function checkApiKeyStatus(serviceId) {
        try {
            const res = await fetch('/api/plugins/api-keys');
            if (res.ok) {
                const data = await res.json();
                return !!data.api_keys?.[serviceId];
            }
        } catch (e) {}
        return false;
    }

    async function verifyFirecrawlKey(apiKey) {
        await saveApiKey(FIRECRAWL_SERVICE, apiKey);
        const result = await ChatRaw.proxy.request({
            serviceId: FIRECRAWL_SERVICE,
            url: 'https://api.firecrawl.dev/v2/scrape',
            method: 'POST',
            body: { url: 'https://example.com', formats: ['markdown'], onlyMainContent: true }
        });
        if (result.success) {
            return { success: true };
        }
        await saveApiKey(FIRECRAWL_SERVICE, '');
        return { success: false, error: result.error };
    }

    async function verifyJinaKey(apiKey) {
        await saveApiKey(JINA_SERVICE, apiKey);
        const result = await ChatRaw.proxy.request({
            serviceId: JINA_SERVICE,
            url: 'https://r.jina.ai/https%3A%2F%2Fexample.com',
            method: 'GET',
            headers: { 'Accept': 'application/json', 'X-Respond-With': 'markdown' }
        });
        if (result.success) {
            return { success: true };
        }
        await saveApiKey(JINA_SERVICE, '');
        return { success: false, error: result.error };
    }

    function parseHtmlInBrowser(html, url) {
        if (!html || typeof html !== 'string') return null;
        let text = html
            .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
            .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
            .replace(/<[^>]+>/g, ' ')
            .replace(/\s+/g, ' ')
            .trim();
        if (!text) return null;
        const titleMatch = html.match(/<title[^>]*>([^<]+)<\/title>/i);
        const title = titleMatch ? titleMatch[1].trim() : (url ? new URL(url).hostname : '');
        const maxLen = 8000;
        if (text.length > maxLen) text = text.slice(0, maxLen) + '\n\n[内容已截断]';
        return { title: title || 'Untitled', content: text };
    }

    async function fetchViaFirecrawl(url, settings) {
        const result = await ChatRaw.proxy.request({
            serviceId: FIRECRAWL_SERVICE,
            url: 'https://api.firecrawl.dev/v2/scrape',
            method: 'POST',
            body: {
                url: url,
                formats: ['markdown'],
                onlyMainContent: true
            }
        });
        if (!result.success || !result.data) return null;
        const data = result.data;
        const content = data.markdown || data.content || '';
        const title = (data.metadata && data.metadata.title) || '';
        if (!content) return null;
        const maxLen = 8000;
        const trimmed = content.length > maxLen ? content.slice(0, maxLen) + '\n\n[内容已截断]' : content;
        return { title: title || 'Untitled', content: trimmed };
    }

    async function fetchViaJina(url, settings) {
        const encodedUrl = encodeURIComponent(url);
        const result = await ChatRaw.proxy.request({
            serviceId: JINA_SERVICE,
            url: 'https://r.jina.ai/' + encodedUrl,
            method: 'GET',
            headers: { 'Accept': 'application/json', 'X-Respond-With': 'markdown' }
        });
        if (!result.success) return null;
        const data = result.data;
        let content = '';
        let title = '';
        if (typeof data === 'string') {
            content = data;
        } else if (data && typeof data.data === 'string') {
            content = data.data;
            if (data.meta && data.meta.title) title = data.meta.title;
        } else if (data && data.content) {
            content = data.content;
            title = data.title || '';
        }
        if (!content) return null;
        const maxLen = 8000;
        const trimmed = content.length > maxLen ? content.slice(0, maxLen) + '\n\n[内容已截断]' : content;
        return { title: title || 'Untitled', content: trimmed };
    }

    function createSettingsUI() {
        const mode = pluginSettings.parser_mode || 'browser';
        return `
            <div class="web-parser-settings" style="display:flex; flex-direction:column; height:100%; max-height:70vh;">
                <div style="flex:1; overflow-y:auto; min-height:0;">
                    <div class="web-parser-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                        <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('parserMode')}</h3>
                        <p style="margin:0 0 12px 0; font-size:0.85rem; color:var(--text-secondary);">${t('parserModeHint')}</p>
                        <div style="display:flex; flex-direction:column; gap:12px;">
                            <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                                <input type="radio" name="web-parser-mode" value="browser" ${mode === 'browser' ? 'checked' : ''}
                                    onchange="window._webParserPlugin.updateSetting('parser_mode', 'browser')" style="margin-right:10px;">
                                <div>
                                    <span style="font-weight:500;">${t('browserMode')}</span>
                                    <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:4px;">${t('browserModeDesc')}</div>
                                </div>
                            </label>
                            <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                                <input type="radio" name="web-parser-mode" value="firecrawl" ${mode === 'firecrawl' ? 'checked' : ''}
                                    onchange="window._webParserPlugin.updateSetting('parser_mode', 'firecrawl')" style="margin-right:10px;">
                                <div>
                                    <span style="font-weight:500;">${t('firecrawlMode')}</span>
                                    <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:4px;">${t('firecrawlModeDesc')}</div>
                                </div>
                            </label>
                            <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                                <input type="radio" name="web-parser-mode" value="jina" ${mode === 'jina' ? 'checked' : ''}
                                    onchange="window._webParserPlugin.updateSetting('parser_mode', 'jina')" style="margin-right:10px;">
                                <div>
                                    <span style="font-weight:500;">${t('jinaMode')}</span>
                                    <div style="font-size:0.85rem; color:var(--text-secondary); margin-top:4px;">${t('jinaModeDesc')}</div>
                                </div>
                            </label>
                        </div>
                    </div>
                    <div id="web-parser-firecrawl-section" class="web-parser-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color); display:${mode === 'firecrawl' ? 'block' : 'none'};">
                        <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('firecrawlKeyLabel')}</h3>
                        <p style="margin:0 0 12px 0; font-size:0.85rem; color:var(--text-secondary);">${t('firecrawlKeyHint')}</p>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <input type="password" id="web-parser-firecrawl-key" class="input-minimal" placeholder="${t('firecrawlKeyPlaceholder')}"
                                style="flex:1; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                            <button type="button" id="web-parser-firecrawl-verify" class="btn-primary" onclick="window._webParserPlugin.verifyFirecrawlKey()"
                                style="padding:10px 20px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500; white-space:nowrap;">${t('verify')}</button>
                        </div>
                        <div id="web-parser-firecrawl-status" style="margin-top:10px; font-size:0.85rem;"></div>
                    </div>
                    <div id="web-parser-jina-section" class="web-parser-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color); display:${mode === 'jina' ? 'block' : 'none'};">
                        <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('jinaKeyLabel')}</h3>
                        <p style="margin:0 0 12px 0; font-size:0.85rem; color:var(--text-secondary);">${t('jinaKeyHint')}</p>
                        <div style="display:flex; gap:12px; align-items:center;">
                            <input type="password" id="web-parser-jina-key" class="input-minimal" placeholder="${t('jinaKeyPlaceholder')}"
                                style="flex:1; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                            <button type="button" id="web-parser-jina-verify" class="btn-primary" onclick="window._webParserPlugin.verifyJinaKey()"
                                style="padding:10px 20px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500; white-space:nowrap;">${t('verify')}</button>
                        </div>
                        <div id="web-parser-jina-status" style="margin-top:10px; font-size:0.85rem;"></div>
                    </div>
                </div>
                <div style="flex-shrink:0; display:flex; justify-content:flex-end; gap:12px; padding:16px 24px; border-top:1px solid var(--border-color); background:var(--bg-primary);">
                    <button type="button" class="btn-secondary" onclick="window._webParserPlugin.closeSettings()"
                        style="padding:10px 24px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">${t('cancel')}</button>
                    <button type="button" class="btn-primary" onclick="window._webParserPlugin.saveAllSettings()"
                        style="padding:10px 24px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500;">${t('save')}</button>
                </div>
            </div>
        `;
    }

    function toggleModeSections() {
        const mode = pluginSettings.parser_mode || 'browser';
        const firecrawlSection = document.getElementById('web-parser-firecrawl-section');
        const jinaSection = document.getElementById('web-parser-jina-section');
        if (firecrawlSection) firecrawlSection.style.display = mode === 'firecrawl' ? 'block' : 'none';
        if (jinaSection) jinaSection.style.display = mode === 'jina' ? 'block' : 'none';
    }

    async function updateApiKeyStatus() {
        const firecrawlStatus = document.getElementById('web-parser-firecrawl-status');
        const firecrawlInput = document.getElementById('web-parser-firecrawl-key');
        if (firecrawlStatus) {
            const has = await checkApiKeyStatus(FIRECRAWL_SERVICE);
            firecrawlStatus.innerHTML = has ? `<span style="color:var(--success-color);">✓ ${t('apiKeySet')}</span>` : `<span style="color:var(--text-secondary);">${t('apiKeyNotSet')}</span>`;
            if (firecrawlInput) firecrawlInput.placeholder = has ? '••••••••' : t('firecrawlKeyPlaceholder');
        }
        const jinaStatus = document.getElementById('web-parser-jina-status');
        const jinaInput = document.getElementById('web-parser-jina-key');
        if (jinaStatus) {
            const has = await checkApiKeyStatus(JINA_SERVICE);
            jinaStatus.innerHTML = has ? `<span style="color:var(--success-color);">✓ ${t('apiKeySet')}</span>` : `<span style="color:var(--text-secondary);">${t('apiKeyNotSet')}</span>`;
            if (jinaInput) jinaInput.placeholder = has ? '••••••••' : t('jinaKeyPlaceholder');
        }
    }

    function closeSettings() {
        const app = document.querySelector('[x-data]');
        if (app && app.__x) app.__x.$data.showPluginSettings = false;
        else if (app && app._x_dataStack) app._x_dataStack[0].showPluginSettings = false;
    }

    async function saveAllSettings() {
        const success = await saveSettings();
        if (success) closeSettings();
    }

    window._webParserPlugin = {
        updateSetting: (key, value) => {
            pluginSettings[key] = value;
            toggleModeSections();
        },
        verifyFirecrawlKey: async () => {
            const input = document.getElementById('web-parser-firecrawl-key');
            const btn = document.getElementById('web-parser-firecrawl-verify');
            const status = document.getElementById('web-parser-firecrawl-status');
            if (!input || !input.value.trim()) {
                if (status) status.innerHTML = `<span style="color:var(--error-color);">${t('firecrawlKeyPlaceholder')}</span>`;
                return;
            }
            if (btn) btn.textContent = t('verifying');
            if (status) status.innerHTML = '';
            const result = await verifyFirecrawlKey(input.value.trim());
            if (result.success) {
                if (status) status.innerHTML = `<span style="color:var(--success-color);">✓ ${t('verifySuccess')}</span>`;
                input.value = '';
                input.placeholder = '••••••••';
            } else {
                const err = typeof result.error === 'object' ? JSON.stringify(result.error) : result.error;
                if (status) status.innerHTML = `<span style="color:var(--error-color);">✗ ${t('verifyFailed')}: ${err}</span>`;
            }
            if (btn) btn.textContent = t('verify');
            setTimeout(updateApiKeyStatus, 100);
        },
        verifyJinaKey: async () => {
            const input = document.getElementById('web-parser-jina-key');
            const btn = document.getElementById('web-parser-jina-verify');
            const status = document.getElementById('web-parser-jina-status');
            if (!input) return;
            if (btn) btn.textContent = t('verifying');
            if (status) status.innerHTML = '';
            const result = await verifyJinaKey(input.value.trim() || ' ');
            if (result.success) {
                if (status) status.innerHTML = `<span style="color:var(--success-color);">✓ ${t('verifySuccess')}</span>`;
                input.value = '';
                input.placeholder = '••••••••';
            } else {
                const err = typeof result.error === 'object' ? JSON.stringify(result.error) : result.error;
                if (status) status.innerHTML = `<span style="color:var(--error-color);">✗ ${t('verifyFailed')}: ${err}</span>`;
            }
            if (btn) btn.textContent = t('verify');
            setTimeout(updateApiKeyStatus, 100);
        },
        closeSettings,
        saveAllSettings
    };

    function injectSettingsUI() {
        const container = document.getElementById('plugin-custom-settings-area');
        if (!container) return;
        container.innerHTML = createSettingsUI();
        toggleModeSections();
        setTimeout(updateApiKeyStatus, 100);
    }

    function setupSettingsListener() {
        window.addEventListener('plugin-settings-open', async (event) => {
            if (event.detail?.pluginId !== PLUGIN_ID) return;
            await loadSettings();
            setTimeout(injectSettingsUI, 100);
        });
    }

    ChatRaw.hooks.register('parse_url', {
        priority: 10,
        handler: async (url, html, settings) => {
            const mode = (settings && settings.parser_mode) || 'browser';
            try {
                if (mode === 'browser' && html) {
                    const out = parseHtmlInBrowser(html, url);
                    if (out) return { success: true, title: out.title, content: out.content };
                    return { success: false };
                }
                if (mode === 'firecrawl') {
                    const out = await fetchViaFirecrawl(url, settings);
                    if (out) return { success: true, title: out.title, content: out.content };
                    return { success: false };
                }
                if (mode === 'jina') {
                    const out = await fetchViaJina(url, settings);
                    if (out) return { success: true, title: out.title, content: out.content };
                    return { success: false };
                }
            } catch (e) {
                console.error('[WebParser] parse_url error:', e);
            }
            return { success: false };
        }
    });

    loadSettings();
    setupSettingsListener();
    console.log('[WebParser] Plugin loaded');
})(window.ChatRawPlugin);
