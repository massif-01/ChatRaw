/**
 * Tavily Web Search Plugin for ChatRaw
 * Advanced web search with AI-generated answers, images, and multiple search modes
 * Powered by Tavily API (https://tavily.com)
 * 
 * @version 1.0.0
 * @author ChatRaw
 * @license MIT
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[TavilySearch] ChatRawPlugin not available');
        return;
    }
    
    const PLUGIN_ID = 'tavily-search';
    const SERVICE_ID = 'tavily';
    const API_URL = 'https://api.tavily.com/search';
    
    // Plugin settings (stored locally)
    let pluginSettings = {
        searchDepth: 'basic',
        maxResults: '5',
        includeAnswer: 'basic',
        includeImages: false,
        topic: 'general',
        timeRange: ''
    };
    
    // i18n
    const i18n = {
        en: {
            searchResults: 'Web Search Results',
            aiAnswer: 'AI Generated Answer',
            source: 'Source',
            score: 'Relevance',
            images: 'Related Images',
            noResults: 'No search results found',
            // Settings UI
            apiKeyLabel: 'Tavily API Key',
            apiKeyHint: 'Get your free API key from tavily.com',
            apiKeyPlaceholder: 'Enter API Key (tvly-...)',
            searchDepth: 'Search Depth',
            basic: 'Basic (1 credit)',
            advanced: 'Advanced (2 credits)',
            fast: 'Fast (1 credit)',
            ultraFast: 'Ultra-Fast (1 credit)',
            maxResults: 'Max Results',
            includeAnswer: 'AI Answer',
            noAnswer: 'Disabled',
            basicAnswer: 'Basic',
            advancedAnswer: 'Advanced',
            includeImages: 'Include Images',
            topic: 'Search Topic',
            general: 'General',
            news: 'News',
            finance: 'Finance',
            timeRange: 'Time Range',
            noLimit: 'No Limit',
            pastDay: 'Past Day',
            pastWeek: 'Past Week',
            pastMonth: 'Past Month',
            pastYear: 'Past Year',
            verify: 'Verify',
            verifying: 'Verifying...',
            verifySuccess: 'API Key is valid!',
            verifyFailed: 'Verification failed',
            save: 'Save',
            cancel: 'Cancel',
            settingsSaved: 'Settings saved',
            saveFailed: 'Save failed',
            apiKeySet: 'API Key is set',
            apiKeyNotSet: 'API Key not set',
            searchDepthHint: 'Advanced mode uses 2 credits per search, others use 1 credit'
        },
        zh: {
            searchResults: '搜索结果',
            aiAnswer: 'AI 生成答案',
            source: '来源',
            score: '相关性',
            images: '相关图片',
            noResults: '未找到搜索结果',
            // Settings UI
            apiKeyLabel: 'Tavily API Key',
            apiKeyHint: '从 tavily.com 获取您的免费 API Key',
            apiKeyPlaceholder: '输入 API Key (tvly-...)',
            searchDepth: '搜索深度',
            basic: '基础（1 积分）',
            advanced: '高级（2 积分）',
            fast: '快速（1 积分）',
            ultraFast: '超快（1 积分）',
            maxResults: '结果数量',
            includeAnswer: 'AI 答案',
            noAnswer: '关闭',
            basicAnswer: '基础',
            advancedAnswer: '高级',
            includeImages: '包含图片',
            topic: '搜索主题',
            general: '通用',
            news: '新闻',
            finance: '财经',
            timeRange: '时间范围',
            noLimit: '不限',
            pastDay: '一天内',
            pastWeek: '一周内',
            pastMonth: '一月内',
            pastYear: '一年内',
            verify: '验证',
            verifying: '验证中...',
            verifySuccess: 'API Key 有效！',
            verifyFailed: '验证失败',
            save: '保存',
            cancel: '取消',
            settingsSaved: '设置已保存',
            saveFailed: '保存失败',
            apiKeySet: 'API Key 已设置',
            apiKeyNotSet: 'API Key 未设置',
            searchDepthHint: '高级模式每次搜索消耗 2 积分，其他模式消耗 1 积分'
        }
    };
    
    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // ============ Settings Management ============
    
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
            console.error('[TavilySearch] Failed to load settings:', e);
        }
    }
    
    async function saveSettings() {
        try {
            console.log('[TavilySearch] Saving settings:', pluginSettings);
            const res = await fetch(`/api/plugins/${encodeURIComponent(PLUGIN_ID)}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: pluginSettings })
            });
            console.log('[TavilySearch] Save response status:', res.status);
            if (res.ok) {
                ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                return true;
            }
            const errorData = await res.json().catch(() => ({}));
            console.error('[TavilySearch] Save error:', errorData);
            throw new Error(errorData.error || 'Save failed');
        } catch (e) {
            console.error('[TavilySearch] Failed to save settings:', e);
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
            console.error('[TavilySearch] Failed to save API key:', e);
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
            console.error('[TavilySearch] Failed to check API key:', e);
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
                url: API_URL,
                method: 'POST',
                body: {
                    query: 'test',
                    max_results: 1
                }
            });
            
            console.log('[TavilySearch] Verify result:', result);
            
            if (result.success) {
                return { success: true };
            } else {
                // If failed, clear the API key
                await saveApiKey('');
                return { success: false, error: result.error };
            }
        } catch (e) {
            console.error('[TavilySearch] Verify failed:', e);
            await saveApiKey('');
            return { success: false, error: e.message };
        }
    }
    
    // ============ Plugin Status ============
    
    async function getPluginStatus() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin) {
                    return {
                        enabled: plugin.enabled,
                        settings: plugin.settings_values || {}
                    };
                }
            }
        } catch (e) {
            console.error('[TavilySearch] Failed to get plugin status:', e);
        }
        return { enabled: false, settings: {} };
    }
    
    // ============ Search Functions ============
    
    function formatSearchResults(data) {
        if (!data || !data.results || data.results.length === 0) {
            return '';
        }
        
        const lines = [`## ${t('searchResults')}\n`];
        
        // Add AI answer if available
        if (data.answer) {
            lines.push(`### ${t('aiAnswer')}\n`);
            lines.push(data.answer);
            lines.push('\n---\n');
        }
        
        // Format search results
        data.results.forEach((item, index) => {
            lines.push(`### ${index + 1}. ${item.title || 'Untitled'}`);
            
            if (item.content) {
                lines.push(item.content);
            }
            
            const meta = [];
            if (item.url) {
                // Extract domain from URL
                try {
                    const domain = new URL(item.url).hostname;
                    meta.push(`${t('source')}: ${domain}`);
                } catch (e) {
                    meta.push(`${t('source')}: ${item.url}`);
                }
            }
            if (item.score) {
                meta.push(`${t('score')}: ${(item.score * 100).toFixed(0)}%`);
            }
            if (item.url) {
                meta.push(`[Link](${item.url})`);
            }
            
            if (meta.length > 0) {
                lines.push(`*${meta.join(' | ')}*`);
            }
            
            lines.push('');
        });
        
        // Add images if available
        if (data.images && data.images.length > 0) {
            lines.push(`\n### ${t('images')}\n`);
            data.images.slice(0, 5).forEach((img, index) => {
                if (img.url) {
                    const desc = img.description || `Image ${index + 1}`;
                    lines.push(`![${desc}](${img.url})`);
                }
            });
            lines.push('');
        }
        
        return lines.join('\n');
    }
    
    async function performSearch(query, settings) {
        try {
            console.log('[TavilySearch] Performing search:', query, settings);
            
            // Build request body
            const body = {
                query: query,
                search_depth: settings.searchDepth || 'basic',
                max_results: parseInt(settings.maxResults) || 5,
                topic: settings.topic || 'general'
            };
            
            // Add include_answer if not disabled
            if (settings.includeAnswer && settings.includeAnswer !== 'false') {
                body.include_answer = settings.includeAnswer;
            }
            
            // Add include_images if enabled
            if (settings.includeImages) {
                body.include_images = true;
                body.include_image_descriptions = true;
            }
            
            // Add time_range if specified
            if (settings.timeRange && settings.timeRange !== '') {
                body.time_range = settings.timeRange;
            }
            
            console.log('[TavilySearch] Request body:', body);
            
            // Call through proxy
            const result = await ChatRaw.proxy.request({
                serviceId: SERVICE_ID,
                url: API_URL,
                method: 'POST',
                body: body
            });
            
            console.log('[TavilySearch] Proxy response:', result);
            
            if (result.success && result.data) {
                return formatSearchResults(result.data);
            } else {
                console.warn('[TavilySearch] API error:', result.error);
            }
            
            return '';
        } catch (e) {
            console.error('[TavilySearch] Search failed:', e);
            return '';
        }
    }
    
    // ============ Settings UI ============
    
    function createSettingsUI() {
        return `
            <div class="tavily-settings" style="display:flex; flex-direction:column; height:100%; max-height:70vh;">
                <div class="tavily-scrollable" style="flex:1; overflow-y:auto; min-height:0;">
                <!-- API Key Section -->
                <div class="tavily-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('apiKeyLabel')}</h3>
                    <p style="margin:0 0 12px 0; font-size:0.85rem; color:var(--text-secondary);">${t('apiKeyHint')}</p>
                    
                    <div style="display:flex; gap:12px; align-items:center;">
                        <input type="password" id="tavily-api-key" class="input-minimal" 
                            placeholder="${t('apiKeyPlaceholder')}"
                            style="flex:1; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                        <button id="tavily-verify-btn" class="btn-primary" onclick="window._tavilyPlugin.verifyApiKey()"
                            style="padding:10px 20px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500; white-space:nowrap;">
                            ${t('verify')}
                        </button>
                    </div>
                    <div id="tavily-api-status" style="margin-top:10px; font-size:0.85rem;"></div>
                </div>
                
                <!-- Search Configuration -->
                <div class="tavily-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 16px 0; font-size:1rem; font-weight:600;">${t('searchDepth')}</h3>
                    <p style="margin:0 0 12px 0; font-size:0.85rem; color:var(--text-secondary);">${t('searchDepthHint')}</p>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px;">
                        <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                            <input type="radio" name="tavily-search-depth" value="basic" ${pluginSettings.searchDepth === 'basic' ? 'checked' : ''}
                                onchange="window._tavilyPlugin.updateSetting('searchDepth', 'basic')"
                                style="margin-right:10px;">
                            <span>${t('basic')}</span>
                        </label>
                        <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                            <input type="radio" name="tavily-search-depth" value="advanced" ${pluginSettings.searchDepth === 'advanced' ? 'checked' : ''}
                                onchange="window._tavilyPlugin.updateSetting('searchDepth', 'advanced')"
                                style="margin-right:10px;">
                            <span>${t('advanced')}</span>
                        </label>
                        <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                            <input type="radio" name="tavily-search-depth" value="fast" ${pluginSettings.searchDepth === 'fast' ? 'checked' : ''}
                                onchange="window._tavilyPlugin.updateSetting('searchDepth', 'fast')"
                                style="margin-right:10px;">
                            <span>${t('fast')}</span>
                        </label>
                        <label style="display:flex; align-items:center; padding:12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); cursor:pointer;">
                            <input type="radio" name="tavily-search-depth" value="ultra-fast" ${pluginSettings.searchDepth === 'ultra-fast' ? 'checked' : ''}
                                onchange="window._tavilyPlugin.updateSetting('searchDepth', 'ultra-fast')"
                                style="margin-right:10px;">
                            <span>${t('ultraFast')}</span>
                        </label>
                    </div>
                </div>
                
                <!-- Basic Options -->
                <div class="tavily-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:20px;">
                        <div>
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('maxResults')}</label>
                            <select id="tavily-max-results" class="input-minimal"
                                onchange="window._tavilyPlugin.updateSetting('maxResults', this.value)"
                                style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                                <option value="5" ${pluginSettings.maxResults === '5' ? 'selected' : ''}>5</option>
                                <option value="10" ${pluginSettings.maxResults === '10' ? 'selected' : ''}>10</option>
                                <option value="20" ${pluginSettings.maxResults === '20' ? 'selected' : ''}>20</option>
                            </select>
                        </div>
                        <div>
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('includeAnswer')}</label>
                            <select id="tavily-include-answer" class="input-minimal"
                                onchange="window._tavilyPlugin.updateSetting('includeAnswer', this.value)"
                                style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                                <option value="false" ${pluginSettings.includeAnswer === 'false' ? 'selected' : ''}>${t('noAnswer')}</option>
                                <option value="basic" ${pluginSettings.includeAnswer === 'basic' ? 'selected' : ''}>${t('basicAnswer')}</option>
                                <option value="advanced" ${pluginSettings.includeAnswer === 'advanced' ? 'selected' : ''}>${t('advancedAnswer')}</option>
                            </select>
                        </div>
                    </div>
                </div>
                
                <!-- Advanced Options -->
                <div class="tavily-section" style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:20px;">
                        <div>
                            <label style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                                <input type="checkbox" id="tavily-include-images"
                                    ${pluginSettings.includeImages ? 'checked' : ''}
                                    onchange="window._tavilyPlugin.updateSetting('includeImages', this.checked)"
                                    style="width:18px; height:18px;">
                                <span style="font-weight:500;">${t('includeImages')}</span>
                            </label>
                        </div>
                        <div>
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('topic')}</label>
                            <select id="tavily-topic" class="input-minimal"
                                onchange="window._tavilyPlugin.updateSetting('topic', this.value)"
                                style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                                <option value="general" ${pluginSettings.topic === 'general' ? 'selected' : ''}>${t('general')}</option>
                                <option value="news" ${pluginSettings.topic === 'news' ? 'selected' : ''}>${t('news')}</option>
                                <option value="finance" ${pluginSettings.topic === 'finance' ? 'selected' : ''}>${t('finance')}</option>
                            </select>
                        </div>
                        <div>
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('timeRange')}</label>
                            <select id="tavily-time-range" class="input-minimal"
                                onchange="window._tavilyPlugin.updateSetting('timeRange', this.value)"
                                style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                                <option value="" ${pluginSettings.timeRange === '' ? 'selected' : ''}>${t('noLimit')}</option>
                                <option value="day" ${pluginSettings.timeRange === 'day' ? 'selected' : ''}>${t('pastDay')}</option>
                                <option value="week" ${pluginSettings.timeRange === 'week' ? 'selected' : ''}>${t('pastWeek')}</option>
                                <option value="month" ${pluginSettings.timeRange === 'month' ? 'selected' : ''}>${t('pastMonth')}</option>
                                <option value="year" ${pluginSettings.timeRange === 'year' ? 'selected' : ''}>${t('pastYear')}</option>
                            </select>
                        </div>
                    </div>
                </div>
                </div>
                
                <!-- Actions Bar (fixed at bottom) -->
                <div style="flex-shrink:0; display:flex; justify-content:flex-end; gap:12px; padding:16px 24px; border-top:1px solid var(--border-color); background:var(--bg-primary);">
                    <button class="btn-secondary" onclick="window._tavilyPlugin.closeSettings()" 
                        style="padding:10px 24px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">
                        ${t('cancel')}
                    </button>
                    <button class="btn-primary" onclick="window._tavilyPlugin.saveAllSettings()"
                        style="padding:10px 24px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500;">
                        ${t('save')}
                    </button>
                </div>
            </div>
        `;
    }
    
    async function updateApiKeyStatus() {
        const statusEl = document.getElementById('tavily-api-status');
        const inputEl = document.getElementById('tavily-api-key');
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
    
    window._tavilyPlugin = {
        updateSetting: (key, value) => {
            pluginSettings[key] = value;
        },
        
        verifyApiKey: async () => {
            const input = document.getElementById('tavily-api-key');
            const btn = document.getElementById('tavily-verify-btn');
            const status = document.getElementById('tavily-api-status');
            
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
            console.error('[TavilySearch] Settings container not found');
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
            console.log('[TavilySearch] before_send hook triggered');
            
            try {
                const { enabled, settings } = await getPluginStatus();
                console.log('[TavilySearch] Plugin enabled:', enabled);
                
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
                    console.log('[TavilySearch] Search completed, found results');
                    
                    let webContent = searchContent;
                    if (body.web_content) {
                        webContent = body.web_content + '\n\n---\n\n' + searchContent;
                    }
                    
                    return {
                        success: true,
                        body: {
                            web_content: webContent,
                            web_url: body.web_url ? body.web_url + ', Tavily Search' : 'Tavily Search'
                        }
                    };
                }
                
                return { success: false };
            } catch (e) {
                console.error('[TavilySearch] Hook error:', e);
                return { success: false };
            }
        }
    });
    
    // ============ Initialize ============
    
    loadSettings();
    setupSettingsListener();
    
    console.log('[TavilySearch] Plugin loaded successfully');
    
})(window.ChatRawPlugin);
