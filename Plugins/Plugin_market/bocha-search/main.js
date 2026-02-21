/**
 * Bocha Web Search Plugin for ChatRaw
 * Enables web search to enhance AI responses with real-time information
 * Supports both Web Search (通搜) and AI Search (AI搜) modes
 * 
 * @version 1.1.0
 * @author ChatRaw
 * @license MIT
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[BochaSearch] ChatRawPlugin not available');
        return;
    }
    
    const PLUGIN_ID = 'bocha-search';
    const SERVICE_ID = 'bocha';
    
    // API endpoints
    const API_URLS = {
        web: 'https://api.bocha.cn/v1/web-search',
        ai: 'https://api.bocha.cn/v1/ai-search'
    };
    
    // Plugin settings (stored locally)
    let pluginSettings = {
        searchType: 'web',
        resultCount: '10',
        freshness: 'noLimit'
    };
    
    // i18n
    const i18n = {
        en: {
            searchResults: 'Web Search Results',
            source: 'Source',
            time: 'Time',
            link: 'Link',
            aiAnswer: 'AI Generated Answer',
            relatedQuestions: 'Related Questions',
            weather: 'Weather',
            encyclopedia: 'Encyclopedia',
            noResults: 'No search results found',
            // Settings UI
            apiKeyLabel: 'Bocha API Key',
            apiKeyHint: 'Get your API key from bocha.cn',
            apiKeyPlaceholder: 'Enter API Key',
            searchType: 'Search Type',
            webSearch: 'Web Search (通搜)',
            aiSearch: 'AI Search (AI搜)',
            resultCount: 'Result Count',
            freshness: 'Time Range',
            noLimit: 'No Limit',
            day: 'Past Day',
            week: 'Past Week',
            month: 'Past Month',
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
            searchResults: '联网搜索结果',
            source: '来源',
            time: '时间',
            link: '链接',
            aiAnswer: 'AI 生成答案',
            relatedQuestions: '相关问题',
            weather: '天气',
            encyclopedia: '百科',
            noResults: '未找到搜索结果',
            // Settings UI
            apiKeyLabel: '博查 API Key',
            apiKeyHint: '从 bocha.cn 获取您的 API Key',
            apiKeyPlaceholder: '输入 API Key',
            searchType: '搜索类型',
            webSearch: '通搜（Web Search）',
            aiSearch: 'AI搜（AI Search）',
            resultCount: '结果数量',
            freshness: '时间范围',
            noLimit: '不限',
            day: '一天内',
            week: '一周内',
            month: '一月内',
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
    
    // ============ Settings Management ============
    
    async function loadSettings() {
        try {
            // Load plugin settings from backend
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin && plugin.settings_values) {
                    pluginSettings = { ...pluginSettings, ...plugin.settings_values };
                }
            }
        } catch (e) {
            console.error('[BochaSearch] Failed to load settings:', e);
        }
    }
    
    async function saveSettings() {
        try {
            console.log('[BochaSearch] Saving settings:', pluginSettings);
            const res = await fetch(`/api/plugins/${encodeURIComponent(PLUGIN_ID)}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: pluginSettings })
            });
            console.log('[BochaSearch] Save response status:', res.status);
            if (res.ok) {
                ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                return true;
            }
            const errorData = await res.json().catch(() => ({}));
            console.error('[BochaSearch] Save error:', errorData);
            throw new Error(errorData.error || 'Save failed');
        } catch (e) {
            console.error('[BochaSearch] Failed to save settings:', e);
            ChatRaw.utils?.showToast?.(t('saveFailed') + ': ' + e.message, 'error');
            return false;
        }
    }
    
    async function saveApiKey(apiKey) {
        try {
            const res = await fetch('/api/plugins/api-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ service_id: SERVICE_ID, api_key: apiKey })
            });
            return res.ok;
        } catch (e) {
            console.error('[BochaSearch] Failed to save API key:', e);
            return false;
        }
    }
    
    async function checkApiKeyStatus() {
        try {
            const res = await fetch('/api/plugins/api-keys');
            if (res.ok) {
                const data = await res.json();
                return !!data.api_keys?.[SERVICE_ID];
            }
        } catch (e) {
            console.error('[BochaSearch] Failed to check API key:', e);
        }
        return false;
    }
    
    async function verifyApiKey(apiKey) {
        try {
            // First save the API key temporarily
            await saveApiKey(apiKey);
            
            // Try a simple search to verify
            const result = await ChatRaw.proxy.request({
                serviceId: SERVICE_ID,
                url: API_URLS.web,
                method: 'POST',
                body: {
                    query: 'test',
                    count: 1
                }
            });
            
            console.log('[BochaSearch] Verify result:', result);
            
            if (result.success) {
                return { success: true };
            } else {
                // If failed, clear the API key
                await saveApiKey('');
                return { success: false, error: result.error };
            }
        } catch (e) {
            console.error('[BochaSearch] Verify failed:', e);
            await saveApiKey('');
            return { success: false, error: e.message };
        }
    }
    
    // ============ Search Functions ============
    
    function formatWebSearchResults(data) {
        const webPages = data.webPages;
        if (!webPages || !webPages.value || webPages.value.length === 0) {
            return '';
        }
        
        const results = webPages.value;
        const lines = [`## ${t('searchResults')}\n`];
        
        results.forEach((item, index) => {
            lines.push(`### ${index + 1}. ${item.name || 'Untitled'}`);
            
            if (item.snippet) {
                lines.push(item.snippet);
            }
            
            const meta = [];
            if (item.siteName) {
                meta.push(`${t('source')}: ${item.siteName}`);
            }
            if (item.datePublished || item.dateLastCrawled) {
                const date = item.datePublished || item.dateLastCrawled;
                meta.push(`${t('time')}: ${date.split('T')[0]}`);
            }
            if (item.url) {
                meta.push(`${t('link')}: ${item.url}`);
            }
            
            if (meta.length > 0) {
                lines.push(`*${meta.join(' | ')}*`);
            }
            
            lines.push('');
        });
        
        return lines.join('\n');
    }
    
    function formatAISearchResults(data) {
        const lines = [`## ${t('searchResults')}\n`];
        
        // Process modal cards (weather, encyclopedia, etc.)
        if (data.cards && data.cards.length > 0) {
            data.cards.forEach(card => {
                if (card.type === 'weather' && card.data) {
                    lines.push(`### ${t('weather')}`);
                    const w = card.data;
                    if (w.location) lines.push(`**${w.location}**`);
                    if (w.temperature) lines.push(`温度: ${w.temperature}`);
                    if (w.weather) lines.push(`天气: ${w.weather}`);
                    if (w.humidity) lines.push(`湿度: ${w.humidity}`);
                    if (w.wind) lines.push(`风力: ${w.wind}`);
                    lines.push('');
                } else if (card.type === 'encyclopedia' && card.data) {
                    lines.push(`### ${t('encyclopedia')}`);
                    const e = card.data;
                    if (e.title) lines.push(`**${e.title}**`);
                    if (e.description) lines.push(e.description);
                    if (e.url) lines.push(`[${t('link')}](${e.url})`);
                    lines.push('');
                } else if (card.type && card.data) {
                    lines.push(`### ${card.type}`);
                    if (typeof card.data === 'object') {
                        Object.entries(card.data).forEach(([key, value]) => {
                            if (value && typeof value !== 'object') {
                                lines.push(`- **${key}**: ${value}`);
                            }
                        });
                    }
                    lines.push('');
                }
            });
        }
        
        // Process web pages
        if (data.webPages && data.webPages.value && data.webPages.value.length > 0) {
            const results = data.webPages.value;
            
            results.forEach((item, index) => {
                lines.push(`### ${index + 1}. ${item.name || 'Untitled'}`);
                
                if (item.snippet) {
                    lines.push(item.snippet);
                }
                
                const meta = [];
                if (item.siteName) {
                    meta.push(`${t('source')}: ${item.siteName}`);
                }
                if (item.datePublished || item.dateLastCrawled) {
                    const date = item.datePublished || item.dateLastCrawled;
                    meta.push(`${t('time')}: ${date.split('T')[0]}`);
                }
                if (item.url) {
                    meta.push(`${t('link')}: ${item.url}`);
                }
                
                if (meta.length > 0) {
                    lines.push(`*${meta.join(' | ')}*`);
                }
                
                lines.push('');
            });
        }
        
        // Process AI-generated answer if available
        if (data.answer) {
            lines.push(`### ${t('aiAnswer')}`);
            lines.push(data.answer);
            lines.push('');
        }
        
        // Process related questions
        if (data.relatedQuestions && data.relatedQuestions.length > 0) {
            lines.push(`### ${t('relatedQuestions')}`);
            data.relatedQuestions.forEach(q => {
                lines.push(`- ${q}`);
            });
            lines.push('');
        }
        
        return lines.join('\n');
    }
    
    async function getPluginStatus() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin) {
                    return {
                        enabled: plugin.enabled ?? false,
                        settings: plugin.settings_values || {}
                    };
                }
            }
        } catch (e) {
            console.error('[BochaSearch] Error getting status:', e);
        }
        return { enabled: false, settings: {} };
    }
    
    async function performSearch(query, settings) {
        const searchType = settings.searchType || 'web';
        const resultCount = parseInt(settings.resultCount) || 10;
        const freshness = settings.freshness || 'noLimit';
        
        const apiUrl = API_URLS[searchType] || API_URLS.web;
        
        const body = {
            query: query,
            freshness: freshness,
            count: resultCount
        };
        
        if (searchType === 'web') {
            body.summary = true;
        } else if (searchType === 'ai') {
            body.answer = false;
            body.stream = false;
        }
        
        try {
            console.log(`[BochaSearch] Performing ${searchType} search for:`, query);
            
            const result = await ChatRaw.proxy.request({
                serviceId: SERVICE_ID,
                url: apiUrl,
                method: 'POST',
                body: body
            });
            
            console.log('[BochaSearch] Proxy response:', result);
            
            if (result.success && result.data) {
                const data = result.data.data || result.data;
                
                if (searchType === 'ai') {
                    return formatAISearchResults(data);
                } else {
                    return formatWebSearchResults(data);
                }
            }
            
            if (result.error) {
                console.warn('[BochaSearch] API error:', result.error);
            }
            
            return '';
        } catch (e) {
            console.error('[BochaSearch] Search failed:', e);
            return '';
        }
    }
    
    // ============ Settings UI ============
    
    function createSettingsUI() {
        return `
            <div class="bocha-settings" style="padding:0;">
                <!-- API Key Section -->
                <div class="bocha-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('apiKeyLabel')}</h3>
                    <p style="margin:0 0 12px 0; font-size:0.85rem; color:var(--text-secondary);">${t('apiKeyHint')}</p>
                    
                    <div style="display:flex; gap:12px; align-items:center;">
                        <input type="password" id="bocha-api-key" class="input-minimal" 
                            placeholder="${t('apiKeyPlaceholder')}"
                            style="flex:1; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                        <button id="bocha-verify-btn" class="btn-primary" onclick="window._bochaPlugin.verifyApiKey()"
                            style="padding:10px 20px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500; white-space:nowrap;">
                            ${t('verify')}
                        </button>
                    </div>
                    <div id="bocha-api-status" style="margin-top:10px; font-size:0.85rem;"></div>
                </div>
                
                <!-- Search Settings -->
                <div class="bocha-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('searchType')}</h3>
                    <div style="display:flex; gap:12px;">
                        <label style="flex:1; display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                            <input type="radio" name="bocha-search-type" value="web" ${pluginSettings.searchType === 'web' ? 'checked' : ''}
                                onchange="window._bochaPlugin.updateSetting('searchType', 'web')"
                                style="margin-right:10px;">
                            <span>${t('webSearch')}</span>
                        </label>
                        <label style="flex:1; display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                            <input type="radio" name="bocha-search-type" value="ai" ${pluginSettings.searchType === 'ai' ? 'checked' : ''}
                                onchange="window._bochaPlugin.updateSetting('searchType', 'ai')"
                                style="margin-right:10px;">
                            <span>${t('aiSearch')}</span>
                        </label>
                    </div>
                </div>
                
                <div class="bocha-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                        <div>
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('resultCount')}</label>
                            <select id="bocha-result-count" class="input-minimal"
                                onchange="window._bochaPlugin.updateSetting('resultCount', this.value)"
                                style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                                <option value="5" ${pluginSettings.resultCount === '5' ? 'selected' : ''}>5</option>
                                <option value="10" ${pluginSettings.resultCount === '10' ? 'selected' : ''}>10</option>
                                <option value="20" ${pluginSettings.resultCount === '20' ? 'selected' : ''}>20</option>
                            </select>
                        </div>
                        <div>
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('freshness')}</label>
                            <select id="bocha-freshness" class="input-minimal"
                                onchange="window._bochaPlugin.updateSetting('freshness', this.value)"
                                style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                                <option value="noLimit" ${pluginSettings.freshness === 'noLimit' ? 'selected' : ''}>${t('noLimit')}</option>
                                <option value="day" ${pluginSettings.freshness === 'day' ? 'selected' : ''}>${t('day')}</option>
                                <option value="week" ${pluginSettings.freshness === 'week' ? 'selected' : ''}>${t('week')}</option>
                                <option value="month" ${pluginSettings.freshness === 'month' ? 'selected' : ''}>${t('month')}</option>
                            </select>
                        </div>
                    </div>
                </div>
                
                <!-- Actions Bar -->
                <div style="display:flex; justify-content:flex-end; gap:12px; padding:16px 24px; border-top:1px solid var(--border-color);">
                    <button class="btn-secondary" onclick="window._bochaPlugin.closeSettings()" 
                        style="padding:10px 24px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">
                        ${t('cancel')}
                    </button>
                    <button class="btn-primary" onclick="window._bochaPlugin.saveAllSettings()"
                        style="padding:10px 24px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500;">
                        ${t('save')}
                    </button>
                </div>
            </div>
        `;
    }
    
    async function updateApiKeyStatus() {
        const statusEl = document.getElementById('bocha-api-status');
        const inputEl = document.getElementById('bocha-api-key');
        if (!statusEl) return;
        
        const hasKey = await checkApiKeyStatus();
        if (hasKey) {
            statusEl.innerHTML = `<span style="color:var(--success-color);">✓ ${t('apiKeySet')}</span>`;
            if (inputEl) inputEl.placeholder = '••••••••';
        } else {
            statusEl.innerHTML = `<span style="color:var(--text-secondary);">${t('apiKeyNotSet')}</span>`;
        }
    }
    
    function closeSettings() {
        const app = document.querySelector('[x-data]');
        if (app && app.__x) {
            app.__x.$data.showPluginSettings = false;
        } else if (app && app._x_dataStack) {
            app._x_dataStack[0].showPluginSettings = false;
        }
    }
    
    async function saveAllSettings() {
        const success = await saveSettings();
        if (success) {
            closeSettings();
        }
    }
    
    // ============ Global Plugin API ============
    
    window._bochaPlugin = {
        updateSetting: (key, value) => {
            pluginSettings[key] = value;
        },
        
        verifyApiKey: async () => {
            const input = document.getElementById('bocha-api-key');
            const btn = document.getElementById('bocha-verify-btn');
            const status = document.getElementById('bocha-api-status');
            
            if (!input || !input.value.trim()) {
                if (status) status.innerHTML = `<span style="color:var(--error-color);">${t('apiKeyPlaceholder')}</span>`;
                return;
            }
            
            if (btn) btn.textContent = t('verifying');
            if (status) status.innerHTML = '';
            
            const result = await verifyApiKey(input.value.trim());
            
            if (result.success) {
                if (status) status.innerHTML = `<span style="color:var(--success-color);">✓ ${t('verifySuccess')}</span>`;
                input.value = '';
                input.placeholder = '••••••••';
            } else {
                const errorMsg = typeof result.error === 'object' ? JSON.stringify(result.error) : result.error;
                if (status) status.innerHTML = `<span style="color:var(--error-color);">✗ ${t('verifyFailed')}: ${errorMsg}</span>`;
            }
            
            if (btn) btn.textContent = t('verify');
        },
        
        closeSettings,
        saveAllSettings
    };
    
    // ============ Settings UI Injection ============
    
    function injectSettingsUI() {
        const container = document.getElementById('plugin-custom-settings-area');
        if (!container) {
            console.error('[BochaSearch] Settings container not found');
            return;
        }
        
        container.innerHTML = createSettingsUI();
        
        // Update API key status
        setTimeout(updateApiKeyStatus, 100);
    }
    
    function setupSettingsListener() {
        window.addEventListener('plugin-settings-open', async (event) => {
            if (event.detail?.pluginId === PLUGIN_ID) {
                // Reload settings first
                await loadSettings();
                
                // Wait for DOM to be ready
                setTimeout(() => {
                    injectSettingsUI();
                }, 100);
            }
        });
    }
    
    // ============ Register Hooks ============
    
    ChatRaw.hooks.register('before_send', {
        priority: 1,
        
        handler: async (body) => {
            console.log('[BochaSearch] before_send hook triggered');
            
            try {
                const { enabled, settings } = await getPluginStatus();
                console.log('[BochaSearch] Plugin enabled:', enabled);
                
                if (!enabled) {
                    return { success: false };
                }
                
                const message = body.message;
                if (!message || message.trim().length < 2) {
                    return { success: false };
                }
                
                // Use local pluginSettings merged with backend settings
                const mergedSettings = { ...pluginSettings, ...settings };
                
                const searchContent = await performSearch(message, mergedSettings);
                
                if (searchContent) {
                    console.log('[BochaSearch] Search completed, found results');
                    
                    let webContent = searchContent;
                    if (body.web_content) {
                        webContent = body.web_content + '\n\n---\n\n' + searchContent;
                    }
                    
                    const searchTypeName = (mergedSettings.searchType || 'web') === 'ai' ? '博查AI搜' : '博查通搜';
                    
                    return {
                        success: true,
                        body: {
                            web_content: webContent,
                            web_url: body.web_url ? body.web_url + ', ' + searchTypeName : searchTypeName
                        }
                    };
                }
                
                return { success: false };
            } catch (e) {
                console.error('[BochaSearch] Hook error:', e);
                return { success: false };
            }
        }
    });
    
    // ============ Initialize ============
    
    loadSettings();
    setupSettingsListener();
    
    console.log('[BochaSearch] Plugin loaded successfully');
    
})(window.ChatRawPlugin);
