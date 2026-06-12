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
    const REMOTE_URLS_MAX_LENGTH = 4000;
    const REMOTE_URL_MAX_LENGTH = 300;
    const REMOTE_STATUS_DEBOUNCE_MS = 300;

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
            description: 'Route messages to a Hermes API server through ChatRaw\'s secure backend bridge.',
            baseUrl: 'Hermes base URL',
            baseUrlHint: 'Loopback URLs are allowed by default. Remote URLs must be enabled in the advanced section below.',
            remoteSectionTitle: 'Remote Base URL access',
            allowedRemoteBaseUrls: 'Allowed remote base URLs',
            allowedRemoteBaseUrlsHint: 'One URL per line or comma-separated. Only listed remote Hermes base URLs are allowed after risk confirmation.',
            remoteUrlsReview: 'Review and enable remote URLs',
            remoteUrlsConfirmed: 'Remote URLs confirmed. Save settings to apply.',
            remoteUrlsNotConfirmed: 'Remote URLs require risk confirmation before use.',
            remoteUrlsEmpty: 'No remote URLs listed',
            remoteUrlsInvalid: 'Invalid remote URL list',
            remoteUrlsRequired: 'Add at least one remote Base URL before enabling remote access.',
            remoteUrlsBaseUrlIsLocal: 'Current Base URL is local and does not require remote access.',
            remoteWarningTitle: 'Enable remote Hermes address access',
            remoteWarningConfirm: 'Confirm remote address access',
            remoteWarningCancel: 'Cancel',
            remoteWarningReadAll: 'Please read the full warning',
            remoteWarningNeedCheck: 'Please confirm you understand the risk',
            remoteWarningConfirmText: 'I confirm these remote addresses are controlled by me or trusted, and I understand chat content, API keys, and Hermes tool execution boundaries may change.',
            remoteWarningBody: `You are enabling access to non-local Hermes Base URLs. After enabling, the ChatRaw backend will be allowed to connect to addresses listed in "Allowed remote base URLs", such as LAN, intranet, or remote server addresses.

Please confirm you understand these risks before continuing:

1. Remote Hermes is not a local service
When the Base URL points to a non-localhost / 127.0.0.1 / ::1 address, the Hermes agent, tools, file access, command execution, and MCP capabilities may run on a remote machine instead of the machine currently running ChatRaw.

2. Chat content will be sent to that address
Messages routed through Hermes, system prompts, context, document snippets, search/RAG augmented content, and related metadata may be sent to the remote Hermes service you entered.

3. API Server Key will also be sent to that address
If you saved a Hermes API Server Key, the ChatRaw backend will send it as an Authorization Bearer token to the matching remote Base URL. Only enter service addresses you control and trust.

4. The address may access internal network resources
Remote address access lets the ChatRaw backend send requests to specified intranet or LAN addresses. Do not enter routers, NAS devices, database consoles, cloud metadata services, proxy services, unknown tunnels, or any address you do not fully trust.

5. HTTP plaintext connections may be observed
If the remote address uses http://, devices on the same network or intermediate nodes may see request content. Use HTTP only on networks you trust; HTTPS, VPN, or SSH tunnels are recommended.

6. Add only necessary addresses
The allowlist should contain only the Hermes API Server Base URLs you currently need. After testing or when no longer needed, delete unnecessary addresses and disable remote access.

After enabling, ChatRaw only allows remote Hermes Base URLs explicitly listed in the allowlist. If you modify the allowlist, you must confirm these risks again.`,
            model: 'Model name',
            apiMode: 'Execution mode',
            apiModeChat: 'Chat Completions',
            apiModeRuns: 'Runs',
            apiModeHint: 'Runs shows Hermes tool events and approval controls in the ChatRaw chat UI.',
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
            requestFailed: 'Request failed',
            settingsHelp: 'Settings help',
            settingsHelpTitle: 'Hermes settings guide',
            settingsHelpClose: 'Close settings guide',
            settingsHelpIntro: 'These settings tell ChatRaw which Hermes API Server to use and how to send messages to it. Hermes is the agent runtime; this is not where you choose the underlying base model.',
            settingsHelpRecommended: 'Recommended starting point',
            settingsHelpBaseUrlTitle: 'Hermes base URL',
            settingsHelpRemoteTitle: 'Remote Base URL access',
            settingsHelpModelTitle: 'Model name',
            settingsHelpModeTitle: 'Execution mode',
            settingsHelpApiKeyTitle: 'API Server Key',
            settingsHelpSessionKeyTitle: 'Session Key'
        },
        zh: {
            toggle: 'Hermes',
            enabled: 'Hermes 模式已开启',
            disabled: 'Hermes 模式已关闭',
            title: 'Hermes 路由',
            description: '通过 ChatRaw 安全后端桥接，将消息路由到 Hermes API Server。',
            baseUrl: 'Hermes 基础 URL',
            baseUrlHint: '本机地址默认允许。远程地址需在下方高级放行中填写并确认风险。',
            remoteSectionTitle: '远程 Base URL 放行',
            allowedRemoteBaseUrls: '允许的远程 Base URL',
            allowedRemoteBaseUrlsHint: '一行一个或用逗号分隔。远程 Hermes Base URL 只有列入此处并确认风险后才会放行。',
            remoteUrlsReview: '查看风险并启用远程地址放行',
            remoteUrlsConfirmed: '远程地址已确认。请保存设置以生效。',
            remoteUrlsNotConfirmed: '远程地址使用前需要先确认风险。',
            remoteUrlsEmpty: '未填写远程地址',
            remoteUrlsInvalid: '远程地址列表无效',
            remoteUrlsRequired: '启用远程访问前，请至少填写一个远程 Base URL。',
            remoteUrlsBaseUrlIsLocal: '当前 Base URL 是本机地址，不需要远程放行。',
            remoteWarningTitle: '启用远程 Hermes 地址放行',
            remoteWarningConfirm: '确认启用远程地址放行',
            remoteWarningCancel: '取消',
            remoteWarningReadAll: '请先阅读完整警示内容',
            remoteWarningNeedCheck: '请确认你已理解风险',
            remoteWarningConfirmText: '我确认这些远程地址由我控制或信任，并理解聊天内容、API key 和 Hermes 工具执行边界可能发生变化。',
            remoteWarningBody: `你正在启用非本机 Hermes Base URL 访问。启用后，ChatRaw 后端将允许连接你在“允许的远程 Base URL”中填写的地址，例如局域网、内网或远程服务器地址。

请在继续前确认你理解以下风险：

1. 远程 Hermes 不是本机服务
当 Base URL 指向非 localhost / 127.0.0.1 / ::1 地址时，Hermes agent、工具、文件访问、命令执行和 MCP 能力可能发生在远程机器上，而不是当前运行 ChatRaw 的机器上。

2. 聊天内容会发送到该地址
通过 Hermes 路由发送的消息、系统提示词、上下文、文档片段、搜索/RAG 增强内容和相关元数据，可能会被发送到你填写的远程 Hermes 服务。

3. API Server Key 也会发送到该地址
如果你保存了 Hermes API Server Key，ChatRaw 后端会把它作为 Authorization Bearer token 发送给匹配的远程 Base URL。请只填写你控制并信任的服务地址。

4. 该地址可能访问内网资源
远程地址放行会让 ChatRaw 后端向指定的内网或局域网地址发起请求。不要填写路由器、NAS、数据库控制台、云元数据服务、代理服务、未知隧道或任何你不完全信任的地址。

5. HTTP 明文连接可能被监听
如果远程地址使用 http://，同一网络中的设备或中间节点可能看到请求内容。只有在你信任该网络时才使用 HTTP；更推荐使用 HTTPS、VPN 或 SSH tunnel。

6. 只添加必要地址
允许列表应只包含你当前需要使用的 Hermes API Server Base URL。测试完成或不再使用后，请删除不需要的地址并关闭远程放行。

启用后，ChatRaw 只会放行明确写在允许列表里的远程 Base URL。修改允许列表后，需要重新确认这些风险。`,
            model: '模型名称',
            apiMode: '执行模式',
            apiModeChat: 'Chat Completions',
            apiModeRuns: 'Runs',
            apiModeHint: 'Runs 会在 ChatRaw 聊天 UI 中显示 Hermes 工具事件和审批控件。',
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
            requestFailed: '请求失败',
            settingsHelp: '配置说明',
            settingsHelpTitle: 'Hermes 配置说明',
            settingsHelpClose: '关闭配置说明',
            settingsHelpIntro: '这些设置决定 ChatRaw 连接哪个 Hermes API Server，以及用什么方式把消息发给它。Hermes 是 agent 运行时；这里不是选择 GPT、Claude、DeepSeek 等基座模型的地方。',
            settingsHelpRecommended: '推荐起步配置',
            settingsHelpBaseUrlTitle: 'Hermes 基础 URL',
            settingsHelpRemoteTitle: '远程 Base URL 放行',
            settingsHelpModelTitle: '模型名称',
            settingsHelpModeTitle: '执行模式',
            settingsHelpApiKeyTitle: 'API Server Key',
            settingsHelpSessionKeyTitle: 'Session Key'
        }
    };

    let active = Boolean(ChatRaw.storage.get(STORAGE_ACTIVE_KEY, false, PLUGIN_ID));
    let settings = {
        baseUrl: DEFAULT_BASE_URL,
        model: DEFAULT_MODEL,
        apiMode: DEFAULT_API_MODE,
        allowedRemoteBaseUrls: '',
        remoteBaseUrlWarningAccepted: false,
        remoteBaseUrlWarningAcceptedFor: ''
    };
    let maskedApiKey = '';
    let maskedSessionKey = '';
    let settingsListener = null;
    let remoteWarningOverlay = null;
    let settingsHelpOverlay = null;
    let remoteStatusRequestId = 0;
    let remoteStatusDebounceTimer = null;

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

    function assertRemoteUrlInputLengths(baseUrl, allowedRemoteBaseUrls) {
        if (String(baseUrl || '').length > REMOTE_URL_MAX_LENGTH) {
            throw new Error(t('remoteUrlsInvalid'));
        }
        if (String(allowedRemoteBaseUrls || '').length > REMOTE_URLS_MAX_LENGTH) {
            throw new Error(t('remoteUrlsInvalid'));
        }
    }

    async function normalizeRemoteBaseUrls(formSettings) {
        const baseUrl = formSettings?.baseUrl || DEFAULT_BASE_URL;
        const allowedRemoteBaseUrls = formSettings?.allowedRemoteBaseUrls || '';
        assertRemoteUrlInputLengths(baseUrl, allowedRemoteBaseUrls);
        const res = await fetch('/api/hermes/remote-base-urls/normalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ baseUrl, allowedRemoteBaseUrls })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || data.success === false) {
            throw new Error(data.error || t('remoteUrlsInvalid'));
        }
        return data;
    }

    async function canonicalizeAllowedRemoteBaseUrls(value, baseUrl) {
        const data = await normalizeRemoteBaseUrls({
            baseUrl: baseUrl || DEFAULT_BASE_URL,
            allowedRemoteBaseUrls: value || ''
        });
        return data.canonicalAllowed || '';
    }

    function getAppState() {
        const root = document.querySelector('[x-data]');
        if (!root) return null;
        return root.__x?.$data || root._x_dataStack?.[0] || null;
    }

    function closeSettings() {
        closeSettingsHelpModal();
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
        const saved = plugin?.settings_values || {};
        settings = {
            baseUrl: saved.baseUrl || DEFAULT_BASE_URL,
            model: saved.model || DEFAULT_MODEL,
            apiMode: saved.apiMode || DEFAULT_API_MODE,
            allowedRemoteBaseUrls: saved.allowedRemoteBaseUrls || '',
            remoteBaseUrlWarningAccepted: saved.remoteBaseUrlWarningAccepted === true,
            remoteBaseUrlWarningAcceptedFor: saved.remoteBaseUrlWarningAcceptedFor || ''
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
        const allowedRemoteInput = document.getElementById('hermes-allowed-remote-base-urls');
        const keyInput = document.getElementById('hermes-api-key');
        const sessionKeyInput = document.getElementById('hermes-session-key');
        const apiMode = apiModeInput?.value === 'runs' ? 'runs' : DEFAULT_API_MODE;
        return {
            baseUrl: (baseUrlInput?.value || '').trim() || DEFAULT_BASE_URL,
            model: (modelInput?.value || '').trim() || DEFAULT_MODEL,
            apiMode,
            allowedRemoteBaseUrls: allowedRemoteInput?.value || '',
            apiKey: (keyInput?.value || '').trim(),
            sessionKey: (sessionKeyInput?.value || '').trim()
        };
    }

    async function saveSettings() {
        const next = readSettingsForm();
        const normalized = await normalizeRemoteBaseUrls(next);
        let acceptedForCanonical = '';
        if (settings.remoteBaseUrlWarningAccepted && settings.remoteBaseUrlWarningAcceptedFor) {
            try {
                acceptedForCanonical = await canonicalizeAllowedRemoteBaseUrls(
                    settings.remoteBaseUrlWarningAcceptedFor,
                    normalized.baseUrl
                );
            } catch (error) {
                acceptedForCanonical = '';
            }
        }
        const canonicalAllowed = normalized.canonicalAllowed || '';
        const remoteAccepted = Boolean(canonicalAllowed && acceptedForCanonical === canonicalAllowed);
        settings = {
            baseUrl: normalized.baseUrl,
            model: next.model,
            apiMode: next.apiMode,
            allowedRemoteBaseUrls: canonicalAllowed,
            remoteBaseUrlWarningAccepted: remoteAccepted,
            remoteBaseUrlWarningAcceptedFor: remoteAccepted ? canonicalAllowed : ''
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

    async function updateRemoteUrlStatus() {
        clearRemoteUrlStatusDebounce();
        const status = document.getElementById('hermes-remote-url-status');
        if (!status) return;

        const requestId = ++remoteStatusRequestId;
        try {
            const value = document.getElementById('hermes-allowed-remote-base-urls')?.value || '';
            const next = readSettingsForm();
            next.allowedRemoteBaseUrls = value;
            const normalized = await normalizeRemoteBaseUrls(next);
            if (requestId !== remoteStatusRequestId) return;
            const canonicalAllowed = normalized.canonicalAllowed || '';
            status.style.color = 'var(--text-secondary)';
            if (!canonicalAllowed) {
                status.textContent = t('remoteUrlsEmpty');
                return;
            }
            let acceptedForCanonical = '';
            if (settings.remoteBaseUrlWarningAccepted && settings.remoteBaseUrlWarningAcceptedFor) {
                try {
                    acceptedForCanonical = await canonicalizeAllowedRemoteBaseUrls(
                        settings.remoteBaseUrlWarningAcceptedFor,
                        normalized.baseUrl
                    );
                } catch (error) {
                    acceptedForCanonical = '';
                }
            }
            if (requestId !== remoteStatusRequestId) return;
            if (
                settings.remoteBaseUrlWarningAccepted &&
                acceptedForCanonical === canonicalAllowed
            ) {
                status.textContent = t('remoteUrlsConfirmed');
            } else {
                status.textContent = t('remoteUrlsNotConfirmed');
            }
        } catch (error) {
            if (requestId !== remoteStatusRequestId) return;
            status.textContent = error.message || t('remoteUrlsInvalid');
            status.style.color = 'var(--danger-color, #dc2626)';
        }
    }

    function clearRemoteUrlStatusDebounce() {
        if (remoteStatusDebounceTimer !== null) {
            clearTimeout(remoteStatusDebounceTimer);
            remoteStatusDebounceTimer = null;
        }
    }

    function scheduleRemoteUrlStatusUpdate() {
        clearRemoteUrlStatusDebounce();
        remoteStatusRequestId += 1;
        remoteStatusDebounceTimer = setTimeout(() => {
            remoteStatusDebounceTimer = null;
            updateRemoteUrlStatus();
        }, REMOTE_STATUS_DEBOUNCE_MS);
    }

    function setRemoteUrlStatus(message, type) {
        clearRemoteUrlStatusDebounce();
        remoteStatusRequestId += 1;
        const status = document.getElementById('hermes-remote-url-status');
        if (!status) return;
        status.textContent = message || '';
        status.style.color = type === 'error' ? 'var(--danger-color, #dc2626)' : 'var(--text-secondary)';
    }

    function closeRemoteWarningModal() {
        if (remoteWarningOverlay) {
            remoteWarningOverlay.remove();
            remoteWarningOverlay = null;
        }
    }

    async function openRemoteWarningModal() {
        const next = readSettingsForm();
        let normalized;
        try {
            normalized = await normalizeRemoteBaseUrls(next);
        } catch (error) {
            setStatus(error.message || t('remoteUrlsInvalid'), 'error');
            await updateRemoteUrlStatus();
            return;
        }

        const canonicalAllowed = normalized.canonicalAllowed || '';
        if (!canonicalAllowed) {
            if (normalized.baseUrlIsLoopback) {
                setRemoteUrlStatus(t('remoteUrlsBaseUrlIsLocal'));
                return;
            }
            setRemoteUrlStatus(t('remoteUrlsRequired'), 'error');
            return;
        }

        closeRemoteWarningModal();
        const bodyHtml = escapeHtml(t('remoteWarningBody')).replace(/\n/g, '<br>');
        remoteWarningOverlay = document.createElement('div');
        remoteWarningOverlay.setAttribute('role', 'dialog');
        remoteWarningOverlay.setAttribute('aria-modal', 'true');
        remoteWarningOverlay.style.cssText = [
            'position:fixed',
            'inset:0',
            'z-index:10000',
            'display:flex',
            'align-items:center',
            'justify-content:center',
            'padding:24px',
            'background:rgba(0,0,0,0.55)'
        ].join(';');
        remoteWarningOverlay.innerHTML = `
            <div style="width:min(720px, 100%); max-height:min(760px, calc(100vh - 48px)); display:grid; grid-template-rows:auto minmax(180px, 1fr) auto; background:var(--bg-primary); border:1px solid var(--border-color); border-radius:var(--radius-lg, 12px); box-shadow:0 24px 80px rgba(0,0,0,0.28); overflow:hidden;">
                <div style="padding:18px 22px; border-bottom:1px solid var(--border-color);">
                    <h3 style="margin:0; font-size:1.05rem; font-weight:600;">${escapeHtml(t('remoteWarningTitle'))}</h3>
                </div>
                <div id="hermes-remote-warning-scroll" style="overflow:auto; padding:18px 22px; color:var(--text-primary); font-size:0.9rem; line-height:1.65;">
                    ${bodyHtml}
                </div>
                <div style="display:grid; gap:12px; padding:16px 22px; border-top:1px solid var(--border-color); background:var(--bg-secondary, var(--bg-primary));">
                    <label style="display:flex; align-items:flex-start; gap:10px; color:var(--text-primary); font-size:0.88rem; line-height:1.45;">
                        <input id="hermes-remote-warning-checkbox" type="checkbox" style="margin-top:3px;">
                        <span>${escapeHtml(t('remoteWarningConfirmText'))}</span>
                    </label>
                    <div id="hermes-remote-warning-status" style="color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('remoteWarningReadAll'))}</div>
                    <div style="display:flex; justify-content:flex-end; gap:10px;">
                        <button id="hermes-remote-warning-cancel" class="btn-secondary" type="button" style="padding:10px 16px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">${escapeHtml(t('remoteWarningCancel'))}</button>
                        <button id="hermes-remote-warning-confirm" class="btn-primary" type="button" disabled style="padding:10px 16px; border:none; border-radius:var(--radius-sm); background:var(--text-primary); color:var(--bg-primary); cursor:not-allowed; font-weight:500; opacity:0.55;">${escapeHtml(t('remoteWarningConfirm'))}</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(remoteWarningOverlay);

        const scrollBox = document.getElementById('hermes-remote-warning-scroll');
        const checkbox = document.getElementById('hermes-remote-warning-checkbox');
        const confirmButton = document.getElementById('hermes-remote-warning-confirm');
        const warningStatus = document.getElementById('hermes-remote-warning-status');

        function updateConfirmState() {
            const readAll = scrollBox.scrollTop + scrollBox.clientHeight >= scrollBox.scrollHeight - 4;
            const checked = checkbox.checked;
            confirmButton.disabled = !(readAll && checked);
            confirmButton.style.cursor = confirmButton.disabled ? 'not-allowed' : 'pointer';
            confirmButton.style.opacity = confirmButton.disabled ? '0.55' : '1';
            if (!readAll) {
                warningStatus.textContent = t('remoteWarningReadAll');
            } else if (!checked) {
                warningStatus.textContent = t('remoteWarningNeedCheck');
            } else {
                warningStatus.textContent = '';
            }
        }

        scrollBox?.addEventListener('scroll', updateConfirmState);
        checkbox?.addEventListener('change', updateConfirmState);
        document.getElementById('hermes-remote-warning-cancel')?.addEventListener('click', closeRemoteWarningModal);
        confirmButton?.addEventListener('click', () => {
            if (confirmButton.disabled) return;
            settings.baseUrl = normalized.baseUrl;
            settings.allowedRemoteBaseUrls = canonicalAllowed;
            settings.remoteBaseUrlWarningAccepted = true;
            settings.remoteBaseUrlWarningAcceptedFor = canonicalAllowed;
            const baseUrlInput = document.getElementById('hermes-base-url');
            const allowedRemoteInput = document.getElementById('hermes-allowed-remote-base-urls');
            if (baseUrlInput) baseUrlInput.value = normalized.baseUrl;
            if (allowedRemoteInput) allowedRemoteInput.value = canonicalAllowed;
            closeRemoteWarningModal();
            updateRemoteUrlStatus();
            setStatus(t('remoteUrlsConfirmed'));
        });
        updateConfirmState();
    }

    function toggleRemoteSection() {
        const toggle = document.getElementById('hermes-remote-section-toggle');
        const content = document.getElementById('hermes-remote-section-content');
        if (!toggle || !content) return;
        const expanded = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        content.style.display = expanded ? 'none' : 'grid';
        const icon = toggle.querySelector('[data-hermes-chevron]');
        if (icon) {
            icon.style.transform = expanded
                ? 'translateY(-60%) rotate(45deg)'
                : 'translateY(-40%) rotate(225deg)';
        }
    }

    function closeSettingsHelpModal() {
        if (settingsHelpOverlay) {
            settingsHelpOverlay.remove();
            settingsHelpOverlay = null;
        }
    }

    function getSettingsHelpContent() {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        if (lang === 'zh') {
            return [
                {
                    title: t('settingsHelpRecommended'),
                    items: [
                        '本机 Hermes: http://127.0.0.1:8642/v1；远程 Hermes: http://服务器地址:端口/v1。',
                        '模型名称先填 hermes-agent；如果 /v1/models 返回了别的 id，就填返回值。',
                        '执行模式先选 Chat Completions；确认基本聊天正常后，再按需要测试 Runs。',
                        '官方 Hermes 通常需要填写 API_SERVER_KEY；Session Key 可先留空。'
                    ]
                },
                {
                    title: t('settingsHelpBaseUrlTitle'),
                    items: [
                        '这是 ChatRaw 后端要连接的 Hermes API Server 根地址，应填到 /v1 层，不要填到 /chat/completions、/models 或 /runs。',
                        '少写 /v1 时，健康检查会访问 /models，官方 Hermes 通常会返回 404。',
                        '如果出现 timeout，通常表示 ChatRaw 后端连不上这个 IP 或端口。'
                    ]
                },
                {
                    title: t('settingsHelpRemoteTitle'),
                    items: [
                        '当基础 URL 不是 localhost、127.0.0.1 或 ::1 时，必须把完全对应的远程 Base URL 写进允许列表并确认风险。',
                        '一行一个或用逗号分隔；只写你控制或信任的 Hermes 服务地址。',
                        '不要填写路由器、NAS、数据库控制台、云元数据服务、未知代理或任何不可信地址。'
                    ]
                },
                {
                    title: t('settingsHelpModelTitle'),
                    items: [
                        '这里填 Hermes API Server 对外暴露的 agent model id，不是基座模型名。',
                        '默认通常是 hermes-agent；最准的值来自 GET /v1/models 返回的 data[0].id。',
                        '真实基座模型在 Hermes 服务端配置；在这里填 gpt-4o、claude-sonnet 或 deepseek-r1 不会切换 Hermes 内部模型。'
                    ]
                },
                {
                    title: t('settingsHelpModeTitle'),
                    items: [
                        'Chat Completions 会调用 /v1/chat/completions，兼容性最好，日常优先使用。',
                        'Runs 会调用 /v1/runs 并订阅 /v1/runs/{id}/events，更适合工具、SSH、长任务、进度事件、停止任务和人工审批。',
                        '需要人工审批时，ChatRaw 会在聊天气泡中显示命令和规则，并要求你显式选择允许一次、本会话允许或拒绝。',
                        '批准的是 Hermes API Server 所在机器和 Hermes 配置环境中的工具/命令执行；ChatRaw 不会自动批准工具调用。'
                    ]
                },
                {
                    title: t('settingsHelpApiKeyTitle'),
                    items: [
                        '这里填 Hermes 服务端 .env 里的 API_SERVER_KEY。',
                        'ChatRaw 后端会保存它，并在请求 Hermes 时作为 Authorization: Bearer <key> 发送。',
                        '只有确认对方是无鉴权兼容服务时才留空；远程地址必须是你控制或信任的服务。'
                    ]
                },
                {
                    title: t('settingsHelpSessionKeyTitle'),
                    items: [
                        '这是可选的长期状态隔离键，会作为 X-Hermes-Session-Key 发送给 Hermes。',
                        '单人单环境使用可以先留空。',
                        '多人、多渠道或多个 ChatRaw 共用同一个 Hermes 服务时，建议填一个稳定且互不相同的值，避免长期记忆混用。'
                    ]
                }
            ];
        }
        return [
            {
                title: t('settingsHelpRecommended'),
                items: [
                    'Local Hermes: http://127.0.0.1:8642/v1. Remote Hermes: http://server:port/v1.',
                    'Start with hermes-agent for the model name; if /v1/models returns another id, use that id.',
                    'Start with Chat Completions; test Runs only after basic chat works.',
                    'Official Hermes usually requires API_SERVER_KEY. Session Key can stay empty at first.'
                ]
            },
            {
                title: t('settingsHelpBaseUrlTitle'),
                items: [
                    'This is the Hermes API Server root URL used by the ChatRaw backend. It should point to /v1, not /chat/completions, /models, or /runs.',
                    'If /v1 is missing, the health check calls /models and official Hermes will usually return 404.',
                    'A timeout usually means the ChatRaw backend cannot reach that IP address or port.'
                ]
            },
            {
                title: t('settingsHelpRemoteTitle'),
                items: [
                    'When the base URL is not localhost, 127.0.0.1, or ::1, the matching remote Base URL must be listed here and risk-confirmed.',
                    'Use one URL per line or comma-separated values. Add only Hermes services you control or trust.',
                    'Do not add routers, NAS devices, database consoles, cloud metadata services, unknown proxies, or untrusted addresses.'
                ]
            },
            {
                title: t('settingsHelpModelTitle'),
                items: [
                    'This is the agent model id exposed by the Hermes API Server, not the underlying base model name.',
                    'The default is usually hermes-agent. The most accurate value is data[0].id from GET /v1/models.',
                    'The real base model is configured inside Hermes; entering gpt-4o, claude-sonnet, or deepseek-r1 here will not switch Hermes internals.'
                ]
            },
            {
                title: t('settingsHelpModeTitle'),
                items: [
                    'Chat Completions calls /v1/chat/completions and is the most compatible everyday mode.',
                    'Runs calls /v1/runs and subscribes to /v1/runs/{id}/events, which is better for tools, SSH, long tasks, progress events, stopping runs, and human approval.',
                    'When approval is required, ChatRaw shows the command and patterns in the chat bubble and requires you to explicitly allow once, allow for the session, or deny.',
                    'Approval applies to tool or command execution in the Hermes API Server machine and configuration environment; ChatRaw never auto-approves tool calls.'
                ]
            },
            {
                title: t('settingsHelpApiKeyTitle'),
                items: [
                    'Enter the API_SERVER_KEY from the Hermes server .env file.',
                    'ChatRaw stores it in the backend and sends it to Hermes as Authorization: Bearer <key>.',
                    'Leave it empty only for a compatible no-auth service. For remote URLs, use only services you control or trust.'
                ]
            },
            {
                title: t('settingsHelpSessionKeyTitle'),
                items: [
                    'This optional long-term state isolation key is sent to Hermes as X-Hermes-Session-Key.',
                    'For a single-user setup, leaving it empty is fine.',
                    'When multiple people, channels, or ChatRaw instances share one Hermes service, use stable distinct values to avoid mixing long-term memory.'
                ]
            }
        ];
    }

    function openSettingsHelpModal() {
        closeSettingsHelpModal();
        const sectionsHtml = getSettingsHelpContent().map(section => `
            <section style="display:grid; gap:8px; padding:0 0 16px 0;">
                <h4 style="margin:0; font-size:0.95rem; font-weight:600; color:var(--text-primary);">${escapeHtml(section.title)}</h4>
                <ul style="margin:0; padding-left:18px; color:var(--text-secondary); font-size:0.86rem; line-height:1.55;">
                    ${section.items.map(item => `<li style="margin:0 0 6px 0;">${escapeHtml(item)}</li>`).join('')}
                </ul>
            </section>
        `).join('');

        settingsHelpOverlay = document.createElement('div');
        settingsHelpOverlay.style.cssText = 'position:fixed; inset:0; z-index:10001; display:flex; align-items:center; justify-content:center; padding:24px; background:rgba(0,0,0,0.42);';
        settingsHelpOverlay.innerHTML = `
            <div role="dialog" aria-modal="true" aria-labelledby="hermes-settings-help-title" style="position:relative; width:min(720px, 100%); max-height:min(720px, 88vh); display:grid; grid-template-rows:auto 1fr; background:var(--bg-primary); color:var(--text-primary); border:1px solid var(--border-color); border-radius:var(--radius-lg); box-shadow:0 24px 80px rgba(0,0,0,0.24); overflow:hidden;">
                <button id="hermes-settings-help-close" class="btn-secondary" type="button" aria-label="${escapeHtml(t('settingsHelpClose'))}" style="position:absolute; top:18px; right:22px; z-index:1; width:28px; height:28px; min-width:28px; padding:0; display:inline-flex; align-items:center; justify-content:center; border:1px solid var(--border-color); border-radius:999px; background:var(--bg-primary); color:var(--text-secondary); cursor:pointer;">
                    <span aria-hidden="true" style="position:absolute; left:50%; top:50%; width:12px; height:2px; border-radius:999px; background:currentColor; transform:translate(-50%, -50%) rotate(45deg);"></span>
                    <span aria-hidden="true" style="position:absolute; left:50%; top:50%; width:12px; height:2px; border-radius:999px; background:currentColor; transform:translate(-50%, -50%) rotate(-45deg);"></span>
                </button>
                <div style="padding:18px 66px 18px 22px; border-bottom:1px solid var(--border-color);">
                    <div style="min-width:0;">
                        <h3 id="hermes-settings-help-title" style="margin:0; font-size:1.05rem; font-weight:600;">${escapeHtml(t('settingsHelpTitle'))}</h3>
                        <p style="margin:8px 0 0 0; color:var(--text-secondary); font-size:0.86rem; line-height:1.5;">${escapeHtml(t('settingsHelpIntro'))}</p>
                    </div>
                </div>
                <div style="overflow:auto; padding:18px 22px 6px 22px;">
                    ${sectionsHtml}
                </div>
            </div>
        `;
        document.body.appendChild(settingsHelpOverlay);
        settingsHelpOverlay.addEventListener('click', event => {
            if (event.target === settingsHelpOverlay) {
                closeSettingsHelpModal();
            }
        });
        document.getElementById('hermes-settings-help-close')?.addEventListener('click', closeSettingsHelpModal);
    }

    function createSettingsMarkup() {
        const remoteSectionExpanded = false;
        return `
            <div class="hermes-settings" style="padding:0;">
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color);">
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:12px; margin:0 0 8px 0;">
                        <h3 style="margin:0; font-size:1.05rem; font-weight:600; line-height:1.3;">${escapeHtml(t('title'))}</h3>
                        <button id="hermes-settings-help" class="btn-secondary" type="button" title="${escapeHtml(t('settingsHelp'))}" aria-label="${escapeHtml(t('settingsHelp'))}" style="width:28px; height:28px; min-width:28px; padding:0; flex:0 0 auto; display:inline-flex; align-items:center; justify-content:center; border:1px solid var(--border-color); border-radius:999px; background:var(--bg-primary); color:var(--text-secondary); cursor:pointer; font:inherit; font-size:0.95rem; font-weight:600; line-height:1;">?</button>
                    </div>
                    <p style="margin:0; color:var(--text-secondary); font-size:0.86rem; line-height:1.5;">${escapeHtml(t('description'))}</p>
                </div>
                <div style="padding:20px 24px; border-bottom:1px solid var(--border-color); display:grid; gap:16px;">
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('baseUrl'))}</span>
                        <input id="hermes-base-url" type="text" class="input-minimal" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                        <span style="color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('baseUrlHint'))}</span>
                    </label>
                    <div id="hermes-remote-section" style="border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary); overflow:hidden;">
                        <button id="hermes-remote-section-toggle" type="button" aria-expanded="${remoteSectionExpanded ? 'true' : 'false'}" style="position:relative; width:100%; height:40px; display:flex; align-items:center; gap:12px; padding:10px 40px 10px 12px; border:none; background:transparent; color:var(--text-primary); cursor:pointer; font:inherit; font-size:16px; line-height:normal; text-align:left;">
                            <span>${escapeHtml(t('remoteSectionTitle'))}</span>
                            <span data-hermes-chevron aria-hidden="true" style="position:absolute; right:13px; top:50%; width:8px; height:8px; border-right:2px solid var(--text-primary); border-bottom:2px solid var(--text-primary); transform:${remoteSectionExpanded ? 'translateY(-40%) rotate(225deg)' : 'translateY(-60%) rotate(45deg)'}; transform-origin:center; pointer-events:none;"></span>
                        </button>
                        <div id="hermes-remote-section-content" style="display:${remoteSectionExpanded ? 'grid' : 'none'}; gap:12px; padding:0 14px 14px 14px;">
                            <label style="display:grid; gap:8px;">
                                <span style="font-weight:500;">${escapeHtml(t('allowedRemoteBaseUrls'))}</span>
                                <textarea id="hermes-allowed-remote-base-urls" class="input-minimal" rows="4" style="width:100%; min-height:92px; resize:vertical; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary); font-family:inherit;"></textarea>
                                <span style="color:var(--text-secondary); font-size:0.82rem;">${escapeHtml(t('allowedRemoteBaseUrlsHint'))}</span>
                            </label>
                            <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
                                <span id="hermes-remote-url-status" style="color:var(--text-secondary); font-size:0.86rem;"></span>
                                <button id="hermes-review-remote-urls" class="btn-secondary" type="button" style="padding:8px 14px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer; white-space:nowrap;">${escapeHtml(t('remoteUrlsReview'))}</button>
                            </div>
                        </div>
                    </div>
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('model'))}</span>
                        <input id="hermes-model" type="text" class="input-minimal" style="width:100%; padding:10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                    </label>
                    <label style="display:grid; gap:8px;">
                        <span style="font-weight:500;">${escapeHtml(t('apiMode'))}</span>
                        <div style="position:relative; width:100%;">
                            <select id="hermes-api-mode" class="input-minimal" style="width:100%; height:42px; appearance:none; -webkit-appearance:none; padding:10px 40px 10px 12px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary); font-size:16px; line-height:normal;">
                                <option value="chat_completions">${escapeHtml(t('apiModeChat'))}</option>
                                <option value="runs">${escapeHtml(t('apiModeRuns'))}</option>
                            </select>
                            <span aria-hidden="true" style="position:absolute; right:14px; top:50%; width:8px; height:8px; border-right:2px solid var(--text-primary); border-bottom:2px solid var(--text-primary); transform:translateY(-60%) rotate(45deg); transform-origin:center; pointer-events:none;"></span>
                        </div>
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
        const allowedRemoteInput = document.getElementById('hermes-allowed-remote-base-urls');
        const keyInput = document.getElementById('hermes-api-key');
        const sessionKeyInput = document.getElementById('hermes-session-key');
        if (baseUrlInput) baseUrlInput.value = settings.baseUrl || DEFAULT_BASE_URL;
        if (allowedRemoteInput) allowedRemoteInput.value = settings.allowedRemoteBaseUrls || '';
        if (modelInput) modelInput.value = settings.model || DEFAULT_MODEL;
        if (apiModeInput) apiModeInput.value = settings.apiMode === 'runs' ? 'runs' : DEFAULT_API_MODE;
        if (keyInput) keyInput.placeholder = maskedApiKey ? t('apiKeyPlaceholder') : '';
        if (sessionKeyInput) sessionKeyInput.placeholder = maskedSessionKey ? t('sessionKeyPlaceholder') : '';
        updateApiKeyStatus();
        updateRemoteUrlStatus();

        document.getElementById('hermes-cancel')?.addEventListener('click', closeSettings);
        document.getElementById('hermes-check')?.addEventListener('click', handleCheck);
        document.getElementById('hermes-save')?.addEventListener('click', () => handleSave(true));
        document.getElementById('hermes-clear-key')?.addEventListener('click', handleClearKey);
        document.getElementById('hermes-clear-session-key')?.addEventListener('click', handleClearSessionKey);
        document.getElementById('hermes-remote-section-toggle')?.addEventListener('click', toggleRemoteSection);
        allowedRemoteInput?.addEventListener('input', scheduleRemoteUrlStatusUpdate);
        document.getElementById('hermes-review-remote-urls')?.addEventListener('click', openRemoteWarningModal);
        document.getElementById('hermes-settings-help')?.addEventListener('click', openSettingsHelpModal);
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
            closeSettingsHelpModal();
            closeRemoteWarningModal();
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
