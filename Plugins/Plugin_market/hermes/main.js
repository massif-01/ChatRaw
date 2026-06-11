/**
 * Hermes Router Plugin
 *
 * Routes selected ChatRaw messages to the host-approved Hermes bridge.
 * The plugin never calls Hermes chat directly and never reads API keys.
 */
(function(ChatRaw) {
    'use strict';

    const PLUGIN_ID = 'hermes';
    const SESSION_KEY_SERVICE_ID = 'hermes-session-key';
    const BUTTON_ID = 'toggle';
    const STORAGE_ACTIVE_KEY = 'active';
    const DEFAULT_BASE_URL = 'http://127.0.0.1:8642/v1';
    const DEFAULT_MODEL = 'hermes-agent';
    const DEFAULT_API_MODE = 'chat_completions';

    if (!ChatRaw || !ChatRaw.hooks || !ChatRaw.ui || !ChatRaw.storage) {
        console.error('[Hermes] ChatRaw plugin APIs are not available');
        return;
    }

    const previous = window._chatrawHermesPlugin;
    if (previous && typeof previous.destroy === 'function') {
        previous.destroy();
    }

    const i18n = {
        en: {
            toggle: 'Hermes',
            enabled: 'Hermes mode enabled',
            disabled: 'Hermes mode disabled',
            title: 'Hermes Router',
            description: 'Route messages to a local Hermes API server through ChatRaw\'s secure backend bridge.',
            baseUrl: 'Hermes base URL',
            baseUrlHint: 'Only loopback URLs are accepted by the backend bridge.',
            model: 'Model name',
            apiMode: 'Execution mode',
            apiModeChat: 'Chat Completions',
            apiModeRuns: 'Runs',
            apiModeHint: 'Runs uses Hermes /v1/runs while keeping the ChatRaw chat UI.',
            apiKey: 'API Server Key (if required)',
            apiKeyHint: 'Stored by ChatRaw backend. Official Hermes requires API_SERVER_KEY; leave empty only for compatible servers that do not require auth.',
            apiKeySaved: 'API key saved',
            apiKeyNotSet: 'No API key saved',
            apiKeyPlaceholder: 'Enter a new key to replace the saved key',
            sessionKey: 'Session Key',
            sessionKeyHint: 'Optional backend-saved key for isolating Hermes long-term session state.',
            sessionKeySaved: 'Session key saved',
            sessionKeyNotSet: 'Session key not set',
            sessionKeyPlaceholder: 'Enter a new session key to replace the saved key',
            cancel: 'Cancel',
            check: 'Check',
            save: 'Save',
            clearKey: 'Clear key',
            clearSessionKey: 'Clear session key',
            saving: 'Saving...',
            checking: 'Checking...',
            saved: 'Settings saved',
            keyCleared: 'API key cleared',
            sessionKeyCleared: 'Session key cleared',
            healthOk: 'Hermes is reachable',
            healthFailed: 'Hermes check failed',
            requestFailed: 'Request failed'
        },
        zh: {
            toggle: 'Hermes',
            enabled: 'Hermes 模式已开启',
            disabled: 'Hermes 模式已关闭',
            title: 'Hermes 路由',
            description: '通过 ChatRaw 安全后端桥接，将消息路由到本机 Hermes API Server。',
            baseUrl: 'Hermes 基础 URL',
            baseUrlHint: '后端桥接只接受 loopback URL。',
            model: '模型名称',
            apiMode: '执行模式',
            apiModeChat: 'Chat Completions',
            apiModeRuns: 'Runs',
            apiModeHint: 'Runs 使用 Hermes /v1/runs，同时保留 ChatRaw 聊天 UI。',
            apiKey: 'API Server Key（如服务要求）',
            apiKeyHint: '由 ChatRaw 后端保存。官方 Hermes 需要 API_SERVER_KEY；仅无鉴权兼容服务可留空。',
            apiKeySaved: 'API key 已保存',
            apiKeyNotSet: '未保存 API key',
            apiKeyPlaceholder: '输入新 key 以替换已保存 key',
            sessionKey: 'Session Key',
            sessionKeyHint: '可选，由后端保存，用于隔离 Hermes 长期 session 状态。',
            sessionKeySaved: 'Session key 已保存',
            sessionKeyNotSet: '尚未设置 session key',
            sessionKeyPlaceholder: '输入新 session key 以替换已保存 key',
            cancel: '取消',
            check: '检查',
            save: '保存',
            clearKey: '清空 key',
            clearSessionKey: '清空 session key',
            saving: '保存中...',
            checking: '检查中...',
            saved: '设置已保存',
            keyCleared: 'API key 已清空',
            sessionKeyCleared: 'Session key 已清空',
            healthOk: 'Hermes 可连接',
            healthFailed: 'Hermes 检查失败',
            requestFailed: '请求失败'
        }
    };

    let active = Boolean(ChatRaw.storage.get(STORAGE_ACTIVE_KEY, false, PLUGIN_ID));
    let settings = {
        baseUrl: DEFAULT_BASE_URL,
        model: DEFAULT_MODEL,
        apiMode: DEFAULT_API_MODE
    };
    let maskedApiKey = '';
    let maskedSessionKey = '';
    let settingsListener = null;

    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function getAppState() {
        const root = document.querySelector('[x-data]');
        if (!root) return null;
        return root.__x?.$data || root._x_dataStack?.[0] || null;
    }

    function closeSettings() {
        const app = getAppState();
        if (app) {
            app.showPluginSettings = false;
        }
    }

    function setStatus(message, type) {
        const status = document.getElementById('hermes-status');
        if (!status) return;
        const row = document.getElementById('hermes-status-row');
        const text = message || '';
        status.textContent = text;
        if (row) row.style.display = text ? 'block' : 'none';
        status.style.color = type === 'error' ? 'var(--danger-color, #dc2626)' : 'var(--text-secondary)';
    }

    function setButtonLoading(loading) {
        ChatRaw.ui.setButtonState(BUTTON_ID, { loading: Boolean(loading) }, PLUGIN_ID);
    }

    function syncButtonState() {
        ChatRaw.ui.setButtonState(BUTTON_ID, { active, loading: false }, PLUGIN_ID);
    }

    function setActive(nextActive) {
        active = Boolean(nextActive);
        ChatRaw.storage.set(STORAGE_ACTIVE_KEY, active, PLUGIN_ID);
        syncButtonState();
        ChatRaw.utils?.showToast?.(active ? t('enabled') : t('disabled'), active ? 'success' : '');
    }

    async function loadSavedSettings() {
        const res = await fetch('/api/plugins');
        if (!res.ok) return;
        const plugins = await res.json();
        const plugin = plugins.find(item => item.id === PLUGIN_ID);
        settings = {
            baseUrl: plugin?.settings_values?.baseUrl || DEFAULT_BASE_URL,
            model: plugin?.settings_values?.model || DEFAULT_MODEL,
            apiMode: plugin?.settings_values?.apiMode || DEFAULT_API_MODE
        };
    }

    async function loadApiKeyStatus() {
        maskedApiKey = '';
        maskedSessionKey = '';
        const res = await fetch('/api/plugins/api-keys');
        if (!res.ok) return;
        const data = await res.json();
        maskedApiKey = data.api_keys?.[PLUGIN_ID] || '';
        maskedSessionKey = data.api_keys?.[SESSION_KEY_SERVICE_ID] || '';
    }

    function readSettingsForm() {
        const baseUrlInput = document.getElementById('hermes-base-url');
        const modelInput = document.getElementById('hermes-model');
        const apiModeInput = document.getElementById('hermes-api-mode');
        const keyInput = document.getElementById('hermes-api-key');
        const sessionKeyInput = document.getElementById('hermes-session-key');
        const apiMode = apiModeInput?.value === 'runs' ? 'runs' : DEFAULT_API_MODE;
        return {
            baseUrl: (baseUrlInput?.value || '').trim() || DEFAULT_BASE_URL,
            model: (modelInput?.value || '').trim() || DEFAULT_MODEL,
            apiMode,
            apiKey: (keyInput?.value || '').trim(),
            sessionKey: (sessionKeyInput?.value || '').trim()
        };
    }

    async function saveSettings() {
        const next = readSettingsForm();
        settings = {
            baseUrl: next.baseUrl,
            model: next.model,
            apiMode: next.apiMode
        };

        const settingsRes = await fetch(`/api/plugins/${encodeURIComponent(PLUGIN_ID)}/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ settings })
        });
        if (!settingsRes.ok) {
            const text = await settingsRes.text();
            throw new Error(text || t('requestFailed'));
        }

        let shouldRefreshKeys = false;
        if (next.apiKey) {
            await saveApiKey(PLUGIN_ID, next.apiKey);
            shouldRefreshKeys = true;
        }
        if (next.sessionKey) {
            await saveApiKey(SESSION_KEY_SERVICE_ID, next.sessionKey);
            shouldRefreshKeys = true;
        }
        if (shouldRefreshKeys) {
            await loadApiKeyStatus();
        }
    }

    async function saveApiKey(serviceId, apiKey) {
        const res = await fetch('/api/plugins/api-key', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ service_id: serviceId, api_key: apiKey })
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.error || t('requestFailed'));
        }
    }

    async function handleSave(closeOnSuccess) {
        try {
            setStatus(t('saving'));
            await saveSettings();
            ChatRaw.utils?.showToast?.(t('saved'), 'success');
            if (closeOnSuccess) {
                closeSettings();
            } else {
                injectSettingsUI();
                setStatus(t('saved'));
            }
        } catch (error) {
            setStatus(error.message || t('requestFailed'), 'error');
            ChatRaw.utils?.showToast?.(`${t('requestFailed')}: ${error.message}`, 'error');
        }
    }

    async function handleCheck() {
        try {
            setStatus(t('checking'));

            const res = await fetch('/api/hermes/health');
            const data = await res.json().catch(() => ({}));
            if (!res.ok || data.success === false) {
                throw new Error(data.error || t('healthFailed'));
            }

            setStatus(`${t('healthOk')}: ${data.model || settings.model}`);
            ChatRaw.utils?.showToast?.(t('healthOk'), 'success');
        } catch (error) {
            setStatus(error.message || t('healthFailed'), 'error');
            ChatRaw.utils?.showToast?.(`${t('healthFailed')}: ${error.message}`, 'error');
        }
    }

    async function handleClearKey() {
        try {
            setStatus(t('saving'));
            await saveApiKey(PLUGIN_ID, '');
            maskedApiKey = '';
            const keyInput = document.getElementById('hermes-api-key');
            if (keyInput) keyInput.value = '';
            updateApiKeyStatus();
            setStatus(t('keyCleared'));
            ChatRaw.utils?.showToast?.(t('keyCleared'), 'success');
        } catch (error) {
            setStatus(error.message || t('requestFailed'), 'error');
            ChatRaw.utils?.showToast?.(`${t('requestFailed')}: ${error.message}`, 'error');
        }
    }

    async function handleClearSessionKey() {
        try {
            setStatus(t('saving'));
            await saveApiKey(SESSION_KEY_SERVICE_ID, '');
            maskedSessionKey = '';
            const keyInput = document.getElementById('hermes-session-key');
            if (keyInput) keyInput.value = '';
            updateApiKeyStatus();
            setStatus(t('sessionKeyCleared'));
            ChatRaw.utils?.showToast?.(t('sessionKeyCleared'), 'success');
        } catch (error) {
            setStatus(error.message || t('requestFailed'), 'error');
            ChatRaw.utils?.showToast?.(`${t('requestFailed')}: ${error.message}`, 'error');
        }
    }

    function updateApiKeyStatus() {
        const status = document.getElementById('hermes-api-key-status');
        const clearButton = document.getElementById('hermes-clear-key');
        const sessionStatus = document.getElementById('hermes-session-key-status');
        const sessionClearButton = document.getElementById('hermes-clear-session-key');

        if (status && maskedApiKey) {
            status.textContent = `${t('apiKeySaved')}: ${maskedApiKey}`;
            if (clearButton) clearButton.disabled = false;
        } else if (status) {
            status.textContent = t('apiKeyNotSet');
            if (clearButton) clearButton.disabled = true;
        }

        if (sessionStatus && maskedSessionKey) {
            sessionStatus.textContent = `${t('sessionKeySaved')}: ${maskedSessionKey}`;
            if (sessionClearButton) sessionClearButton.disabled = false;
        } else if (sessionStatus) {
            sessionStatus.textContent = t('sessionKeyNotSet');
            if (sessionClearButton) sessionClearButton.disabled = true;
        }
    }

    function createSettingsMarkup() {
        return `
            <div class="hermes-settings" style="padding:0;">
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0 0 8px 0; font-size:1.05rem; font-weight:600;">${escapeHtml(t('title'))}</h3>
                    <p style="margin:0; color:var(--text-secondary); font-size:0.86rem; line-height:1.5;">${escapeHtml(t('description'))}</p>
                </div>
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color); display:grid; gap:16px;">
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('baseUrl'))}</span>
                        <input id="hermes-base-url" type="text" class="input-minimal" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                        <span style="color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('baseUrlHint'))}</span>
                    </label>
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('model'))}</span>
                        <input id="hermes-model" type="text" class="input-minimal" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                    </label>
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('apiMode'))}</span>
                        <select id="hermes-api-mode" class="input-minimal" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                            <option value="chat_completions">${escapeHtml(t('apiModeChat'))}</option>
                            <option value="runs">${escapeHtml(t('apiModeRuns'))}</option>
                        </select>
                        <span style="color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('apiModeHint'))}</span>
                    </label>
                </div>
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color); display:grid; gap:12px;">
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('apiKey'))}</span>
                        <input id="hermes-api-key" type="password" class="input-minimal" autocomplete="off" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                    </label>
                    <p style="margin:0; color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('apiKeyHint'))}</p>
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                        <span id="hermes-api-key-status" style="color:var(--text-secondary); font-size:0.86rem;"></span>
                        <button id="hermes-clear-key" class="btn-secondary" type="button" style="padding:8px 14px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">${escapeHtml(t('clearKey'))}</button>
                    </div>
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('sessionKey'))}</span>
                        <input id="hermes-session-key" type="password" class="input-minimal" autocomplete="off" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                    </label>
                    <p style="margin:0; color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('sessionKeyHint'))}</p>
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                        <span id="hermes-session-key-status" style="color:var(--text-secondary); font-size:0.86rem;"></span>
                        <button id="hermes-clear-session-key" class="btn-secondary" type="button" style="padding:8px 14px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">${escapeHtml(t('clearSessionKey'))}</button>
                    </div>
                </div>
                <div id="hermes-status-row" style="display:none; padding:12px 24px;">
                    <div id="hermes-status" style="font-size:0.86rem; color:var(--text-secondary);"></div>
                </div>
                <div style="display:flex; justify-content:flex-end; gap:10px; padding:16px 24px; border-top:1px solid var(--border-color);">
                    <button id="hermes-cancel" class="btn-secondary" type="button" style="padding:10px 18px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">${escapeHtml(t('cancel'))}</button>
                    <button id="hermes-check" class="btn-secondary" type="button" style="padding:10px 18px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">${escapeHtml(t('check'))}</button>
                    <button id="hermes-save" class="btn-primary" type="button" style="padding:10px 18px; border:none; border-radius:var(--radius-sm); background:var(--text-primary); color:var(--bg-primary); cursor:pointer; font-weight:500;">${escapeHtml(t('save'))}</button>
                </div>
            </div>
        `;
    }

    function injectSettingsUI() {
        const container = document.getElementById('plugin-custom-settings-area');
        if (!container) return;

        container.innerHTML = createSettingsMarkup();

        const baseUrlInput = document.getElementById('hermes-base-url');
        const modelInput = document.getElementById('hermes-model');
        const apiModeInput = document.getElementById('hermes-api-mode');
        const keyInput = document.getElementById('hermes-api-key');
        const sessionKeyInput = document.getElementById('hermes-session-key');
        if (baseUrlInput) baseUrlInput.value = settings.baseUrl || DEFAULT_BASE_URL;
        if (modelInput) modelInput.value = settings.model || DEFAULT_MODEL;
        if (apiModeInput) apiModeInput.value = settings.apiMode === 'runs' ? 'runs' : DEFAULT_API_MODE;
        if (keyInput) keyInput.placeholder = maskedApiKey ? t('apiKeyPlaceholder') : '';
        if (sessionKeyInput) sessionKeyInput.placeholder = maskedSessionKey ? t('sessionKeyPlaceholder') : '';
        updateApiKeyStatus();

        document.getElementById('hermes-cancel')?.addEventListener('click', closeSettings);
        document.getElementById('hermes-check')?.addEventListener('click', handleCheck);
        document.getElementById('hermes-save')?.addEventListener('click', () => handleSave(true));
        document.getElementById('hermes-clear-key')?.addEventListener('click', handleClearKey);
        document.getElementById('hermes-clear-session-key')?.addEventListener('click', handleClearSessionKey);
    }

    async function openSettings() {
        injectSettingsUI();
        const errors = [];
        try {
            await loadSavedSettings();
        } catch (error) {
            errors.push(error);
        }
        try {
            await loadApiKeyStatus();
        } catch (error) {
            errors.push(error);
        }
        injectSettingsUI();
        if (errors.length > 0) {
            setStatus(errors[0].message || t('requestFailed'), 'error');
        }
    }

    settingsListener = async (event) => {
        if (event.detail?.pluginId !== PLUGIN_ID) return;
        setTimeout(() => {
            openSettings().catch(error => {
                console.error('[Hermes] Failed to open settings:', error);
                setStatus(error.message || t('requestFailed'), 'error');
            });
        }, 50);
    };
    window.addEventListener('plugin-settings-open', settingsListener);

    ChatRaw.ui.registerToolbarButton({
        id: BUTTON_ID,
        icon: 'ri-robot-2-line',
        label: {
            en: 'Hermes',
            zh: 'Hermes'
        },
        order: 30,
        onClick: () => {
            setButtonLoading(true);
            try {
                setActive(!active);
            } finally {
                setButtonLoading(false);
            }
        }
    }, PLUGIN_ID);
    syncButtonState();

    ChatRaw.hooks.register('route_message', {
        priority: 10,
        handler: async () => {
            if (!active) {
                return { success: false };
            }
            return { success: true, route: PLUGIN_ID };
        }
    });

    window._chatrawHermesPlugin = {
        destroy() {
            if (settingsListener) {
                window.removeEventListener('plugin-settings-open', settingsListener);
                settingsListener = null;
            }
            const app = getAppState();
            if (app && typeof app.unregisterPluginHooks === 'function') {
                app.unregisterPluginHooks(PLUGIN_ID);
            }
        },
        isActive() {
            return active;
        }
    };
})(window.ChatRawPlugin);
