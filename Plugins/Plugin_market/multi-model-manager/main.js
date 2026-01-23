/**
 * Multi-Model Manager Plugin for ChatRaw
 * Manage multiple AI models and switch between them quickly
 * 
 * @version 1.0.0
 * @author ChatRaw
 * @license Apache-2.0
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[MultiModel] ChatRawPlugin not available, retrying in 500ms...');
        setTimeout(() => {
            if (window.ChatRawPlugin && window.ChatRawPlugin.hooks) {
                arguments.callee(window.ChatRawPlugin);
            } else {
                console.error('[MultiModel] ChatRawPlugin still not available after retry');
            }
        }, 500);
        return;
    }
    
    const PLUGIN_ID = 'multi-model-manager';
    
    // ============ i18n Translations ============
    const i18n = {
        en: {
            title: 'Multi-Model Manager',
            addModel: 'Add Model',
            deleteModel: 'Delete',
            confirmDelete: 'Are you sure you want to delete this model?',
            displayName: 'Display Name',
            displayNameHint: 'Name shown in the model list on the left',
            apiEndpoint: 'API Endpoint',
            apiKey: 'API Key',
            optional: 'Optional',
            modelId: 'Model ID',
            capabilities: 'Capabilities',
            vision: 'Vision',
            reasoning: 'Reasoning',
            tools: 'Tools',
            contextLength: 'Context Length',
            maxOutput: 'Max Output',
            verify: 'Verify',
            verifying: 'Verifying...',
            save: 'Save',
            active: 'Active',
            error: 'Error',
            save: 'Save',
            cancel: 'Cancel',
            noModels: 'No models configured yet',
            noModelsHint: 'Click "Add Model" to create your first model configuration',
            selectModel: 'Select a model',
            selectModelHint: 'Choose a model from the left to view or edit its configuration',
            modelSaved: 'Model saved',
            modelDeleted: 'Model deleted',
            saveFailed: 'Save failed',
            verifySuccess: 'Connection verified',
            verifyFailed: 'Connection failed',
            originalRestored: 'Original model config restored',
            noActiveModel: 'No active model',
            activating: 'Activating...'
        },
        zh: {
            title: '多模型管理',
            addModel: '添加模型',
            deleteModel: '删除',
            confirmDelete: '确定要删除这个模型吗？',
            displayName: '显示名称',
            displayNameHint: '显示在左侧模型列表中的名称',
            apiEndpoint: 'API 端点',
            apiKey: 'API Key',
            optional: '可选',
            modelId: '模型 ID',
            capabilities: '能力',
            vision: '视觉',
            reasoning: '推理',
            tools: '工具',
            contextLength: '上下文长度',
            maxOutput: '最大输出',
            verify: '验证',
            verifying: '验证中...',
            save: '保存',
            active: '活跃',
            error: '错误',
            save: '保存',
            cancel: '取消',
            noModels: '暂无配置的模型',
            noModelsHint: '点击"添加模型"创建你的第一个模型配置',
            selectModel: '选择模型',
            selectModelHint: '从左侧选择一个模型来查看或编辑配置',
            modelSaved: '模型已保存',
            modelDeleted: '模型已删除',
            saveFailed: '保存失败',
            verifySuccess: '连接验证成功',
            verifyFailed: '连接失败',
            originalRestored: '已恢复原模型配置',
            noActiveModel: '无激活模型',
            activating: '激活中...'
        }
    };
    
    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // ============ State Management ============
    let pluginData = {
        models: [],
        originalConfig: null
    };
    let selectedModelId = null;
    let verifyingModelId = null;
    
    // ============ Storage Functions ============
    // Use backend API for persistent storage (survives Docker restarts with volume)
    async function loadPluginData() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin?.settings_values) {
                    // settings_values contains our pluginData
                    pluginData = { 
                        models: plugin.settings_values.models || [],
                        originalConfig: plugin.settings_values.originalConfig || null
                    };
                }
            }
            console.log('[MultiModel] Loaded plugin data from backend:', pluginData);
        } catch (e) {
            console.error('[MultiModel] Failed to load plugin data:', e);
        }
    }
    
    async function savePluginData() {
        try {
            const res = await fetch(`/api/plugins/${encodeURIComponent(PLUGIN_ID)}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: pluginData })
            });
            if (res.ok) {
                console.log('[MultiModel] Saved plugin data to backend');
                return true;
            } else {
                console.error('[MultiModel] Failed to save plugin data:', res.status);
                return false;
            }
        } catch (e) {
            console.error('[MultiModel] Failed to save plugin data:', e);
            return false;
        }
    }
    
    // ============ Model Management ============
    function generateId() {
        return 'model-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
    }
    
    function createNewModel() {
        return {
            id: generateId(),
            displayName: '',
            active: false,
            api_url: '',
            api_key: '',
            model_id: '',
            capability: {
                vision: false,
                reasoning: false,
                tools: false
            },
            context_length: 8192,
            max_output: 4096,
            status: null,
            verifyMessage: ''
        };
    }
    
    async function backupOriginalConfig() {
        if (pluginData.originalConfig) {
            console.log('[MultiModel] Original config already backed up');
            return;
        }
        
        try {
            const res = await fetch('/api/models');
            if (res.ok) {
                const models = await res.json();
                const chatModel = models.find(m => m.type === 'chat');
                if (chatModel) {
                    pluginData.originalConfig = { ...chatModel };
                    await savePluginData();
                    console.log('[MultiModel] Backed up original config:', pluginData.originalConfig);
                }
            }
        } catch (e) {
            console.error('[MultiModel] Failed to backup original config:', e);
        }
    }
    
    async function restoreOriginalConfig() {
        if (!pluginData.originalConfig) {
            console.log('[MultiModel] No original config to restore');
            return;
        }
        
        try {
            const res = await fetch('/api/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...pluginData.originalConfig,
                    id: 'default-chat',
                    type: 'chat'
                })
            });
            
            if (res.ok) {
                pluginData.originalConfig = null;
                await savePluginData();
                ChatRaw.utils?.showToast?.(t('originalRestored'), 'success');
                console.log('[MultiModel] Restored original config');
            }
        } catch (e) {
            console.error('[MultiModel] Failed to restore original config:', e);
        }
    }
    
    async function activateModel(modelId) {
        const model = pluginData.models.find(m => m.id === modelId);
        if (!model) return;
        
        // First backup original config if not already done
        await backupOriginalConfig();
        
        // Deactivate all other models
        pluginData.models.forEach(m => m.active = (m.id === modelId));
        
        // Write to main config
        try {
            const res = await fetch('/api/models', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: 'default-chat',
                    type: 'chat',
                    api_url: model.api_url,
                    api_key: model.api_key,
                    model_id: model.model_id,
                    capability: model.capability,
                    context_length: model.context_length,
                    max_output: model.max_output
                })
            });
            
            if (res.ok) {
                await savePluginData();
                renderUI();
                console.log('[MultiModel] Activated model:', model.displayName);
            }
        } catch (e) {
            console.error('[MultiModel] Failed to activate model:', e);
        }
    }
    
    async function deactivateModel(modelId) {
        const model = pluginData.models.find(m => m.id === modelId);
        if (model) {
            model.active = false;
        }
        
        // Check if any model is still active
        const hasActiveModel = pluginData.models.some(m => m.active);
        
        if (!hasActiveModel) {
            // No active model, restore original config
            await restoreOriginalConfig();
        }
        
        await savePluginData();
        renderUI();
    }
    
    async function saveModel(model) {
        const index = pluginData.models.findIndex(m => m.id === model.id);
        if (index >= 0) {
            pluginData.models[index] = { ...model };
        } else {
            pluginData.models.push({ ...model });
        }
        await savePluginData();
        
        // If this model is active, update main config too
        if (model.active) {
            await activateModel(model.id);
        }
        
        ChatRaw.utils?.showToast?.(t('modelSaved'), 'success');
    }
    
    async function deleteModel(modelId) {
        const model = pluginData.models.find(m => m.id === modelId);
        const wasActive = model?.active;
        
        pluginData.models = pluginData.models.filter(m => m.id !== modelId);
        
        // If deleted model was active, check if we need to restore
        if (wasActive) {
            const hasActiveModel = pluginData.models.some(m => m.active);
            if (!hasActiveModel) {
                await restoreOriginalConfig();
            }
        }
        
        await savePluginData();
        
        if (selectedModelId === modelId) {
            selectedModelId = pluginData.models.length > 0 ? pluginData.models[0].id : null;
        }
        
        ChatRaw.utils?.showToast?.(t('modelDeleted'), 'success');
        renderUI();
    }
    
    function updateModelFromForm(model) {
        model.displayName = document.getElementById('mm-displayName')?.value || '';
        model.api_url = document.getElementById('mm-apiUrl')?.value || '';
        model.api_key = document.getElementById('mm-apiKey')?.value || '';
        model.model_id = document.getElementById('mm-modelId')?.value || '';
        model.capability = {
            vision: document.getElementById('mm-vision')?.checked || false,
            reasoning: document.getElementById('mm-reasoning')?.checked || false,
            tools: document.getElementById('mm-tools')?.checked || false
        };
        model.context_length = parseInt(document.getElementById('mm-contextLength')?.value) || 8192;
        model.max_output = parseInt(document.getElementById('mm-maxOutput')?.value) || 4096;
    }
    
    async function verifyModel(model) {
        if (!model.api_url || !model.model_id) {
            model.status = 'error';
            model.verifyMessage = 'API URL and Model ID required';
            return false;
        }
        
        verifyingModelId = model.id;
        renderUI();
        
        try {
            const res = await fetch('/api/models/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    id: model.id,
                    type: 'chat',
                    api_url: model.api_url,
                    api_key: model.api_key,
                    model_id: model.model_id
                })
            });
            
            const result = await res.json();
            verifyingModelId = null;
            
            if (result.success) {
                model.status = 'success';
                model.verifyMessage = t('verifySuccess');
                return true;
            } else {
                model.status = 'error';
                model.verifyMessage = result.error || t('verifyFailed');
                return false;
            }
        } catch (e) {
            verifyingModelId = null;
            model.status = 'error';
            model.verifyMessage = e.message || t('verifyFailed');
            return false;
        } finally {
            renderUI();
        }
    }
    
    // ============ UI Rendering ============
    function getStyles() {
        return `
            .mm-container {
                display: flex;
                height: 100%;
                max-height: 70vh;
                min-height: 400px;
                gap: 0;
                border-radius: 12px;
                overflow: hidden;
            }
            .mm-sidebar {
                width: 200px;
                min-width: 200px;
                border-right: 1px solid var(--border-color);
                display: flex;
                flex-direction: column;
                background: var(--bg-secondary);
                border-radius: 12px 0 0 12px;
            }
            .mm-sidebar-header {
                padding: 16px;
                border-bottom: 1px solid var(--border-color);
            }
            .mm-add-btn {
                width: 100%;
                padding: 10px 16px;
                background: var(--text-primary);
                color: var(--bg-primary);
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                transition: opacity 0.2s;
            }
            .mm-add-btn:hover {
                opacity: 0.8;
            }
            .mm-add-btn svg {
                stroke: var(--bg-primary);
            }
            .mm-model-list {
                flex: 1;
                overflow-y: auto;
                padding: 8px;
            }
            .mm-model-item {
                display: flex;
                align-items: center;
                padding: 11px;
                margin-bottom: 4px;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s;
                gap: 10px;
                border: 1px solid transparent;
                background: transparent;
            }
            .mm-model-item:hover {
                background: var(--bg-hover);
            }
            .mm-model-item.selected {
                background: var(--bg-primary);
                border: 1px solid var(--text-primary);
            }
            .mm-model-item.selected .mm-model-name {
                color: var(--text-primary);
                font-weight: 500;
            }
            .mm-model-toggle {
                flex-shrink: 0;
            }
            .mm-model-name {
                flex: 1;
                font-size: 14px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                color: var(--text-primary);
            }
            .mm-model-status {
                width: 8px;
                height: 8px;
                border-radius: 50%;
                flex-shrink: 0;
            }
            .mm-model-status.active {
                background: var(--text-primary);
            }
            .mm-content {
                flex: 1;
                padding: 24px;
                overflow-y: auto;
                background: var(--bg-primary);
                border-radius: 0 12px 12px 0;
            }
            .mm-empty {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100%;
                color: var(--text-secondary);
                text-align: center;
            }
            .mm-empty-icon {
                font-size: 48px;
                margin-bottom: 16px;
                opacity: 0.5;
            }
            .mm-empty-title {
                font-size: 18px;
                margin-bottom: 8px;
                color: var(--text-primary);
            }
            .mm-empty-hint {
                font-size: 14px;
            }
            .mm-form-group {
                margin-bottom: 20px;
            }
            .mm-form-label {
                display: block;
                font-size: 14px;
                font-weight: 500;
                margin-bottom: 8px;
                color: var(--text-primary);
            }
            .mm-form-hint {
                font-size: 12px;
                color: var(--text-secondary);
                margin-top: 4px;
            }
            .mm-input {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid var(--border-color);
                border-radius: 8px;
                background: var(--bg-primary);
                color: var(--text-primary);
                font-size: 14px;
                box-sizing: border-box;
            }
            .mm-input:focus {
                outline: none;
                border-color: var(--primary-color);
            }
            .mm-checkbox-group {
                display: flex;
                gap: 20px;
                margin-top: 8px;
            }
            .mm-checkbox-label {
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 14px;
                cursor: pointer;
            }
            .mm-checkbox-label input {
                width: 16px;
                height: 16px;
            }
            .mm-btn-row {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                margin-top: 24px;
            }
            .mm-btn-verify {
                padding: 12px 24px;
                background: transparent;
                color: var(--text-primary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s;
            }
            .mm-btn-verify:hover {
                background: var(--bg-hover);
                border-color: var(--text-primary);
            }
            .mm-btn-verify:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .mm-btn-save {
                padding: 12px 24px;
                background: var(--text-primary);
                color: var(--bg-primary);
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: opacity 0.2s;
            }
            .mm-btn-save:hover {
                opacity: 0.8;
            }
            .mm-btn-danger {
                padding: 12px 24px;
                background: transparent;
                color: var(--text-secondary);
                border: 1px solid var(--border-color);
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
                transition: all 0.2s;
            }
            .mm-btn-danger:hover {
                color: var(--text-primary);
                border-color: var(--text-primary);
            }
            .mm-verify-msg {
                margin-top: 12px;
                font-size: 13px;
                padding: 8px 12px;
                border-radius: 6px;
            }
            .mm-verify-msg.success {
                background: var(--bg-secondary);
                color: var(--text-primary);
                border: 1px solid var(--border-color);
            }
            .mm-verify-msg.error {
                background: var(--bg-secondary);
                color: var(--text-secondary);
                border: 1px solid var(--border-color);
            }
            .mm-toggle {
                position: relative;
                width: 36px;
                height: 20px;
                background: var(--border-color);
                border-radius: 10px;
                cursor: pointer;
                transition: background 0.2s;
            }
            .mm-toggle.checked {
                background: var(--text-primary);
            }
            .mm-toggle-handle {
                position: absolute;
                top: 2px;
                left: 2px;
                width: 16px;
                height: 16px;
                background: var(--bg-primary);
                border-radius: 50%;
                transition: left 0.2s;
            }
            .mm-toggle.checked .mm-toggle-handle {
                left: 18px;
                background: var(--bg-primary);
            }
            .mm-section-title {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 20px;
                color: var(--text-primary);
            }
            .mm-footer {
                padding: 16px 24px;
                border-top: 1px solid var(--border-color);
                display: flex;
                justify-content: flex-end;
                gap: 12px;
            }
            .mm-footer-btn {
                padding: 10px 24px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                transition: all 0.2s;
            }
            .mm-footer-btn.cancel {
                background: transparent;
                border: 1px solid var(--border-color);
                color: var(--text-primary);
            }
            .mm-footer-btn.cancel:hover {
                background: var(--bg-hover);
            }
            .mm-footer-btn.save {
                background: var(--text-primary);
                border: none;
                color: var(--bg-primary);
            }
            .mm-footer-btn.save:hover {
                opacity: 0.8;
            }
        `;
    }
    
    function renderModelList() {
        if (pluginData.models.length === 0) {
            return `<div class="mm-empty" style="padding: 20px; text-align: center; color: var(--text-secondary); font-size: 13px;">
                ${t('noModels')}
            </div>`;
        }
        
        return pluginData.models.map(model => {
            const isSelected = selectedModelId === model.id;
            const displayName = model.displayName || model.model_id || 'Unnamed';
            
            return `
                <div class="mm-model-item ${isSelected ? 'selected' : ''}" data-model-id="${model.id}">
                    <div class="mm-model-toggle ${model.active ? 'checked' : ''}" data-toggle-id="${model.id}">
                        <div class="mm-toggle ${model.active ? 'checked' : ''}">
                            <div class="mm-toggle-handle"></div>
                        </div>
                    </div>
                    <span class="mm-model-name">${escapeHtml(displayName)}</span>
                    ${model.active ? '<div class="mm-model-status active"></div>' : ''}
                </div>
            `;
        }).join('');
    }
    
    function renderModelForm() {
        if (pluginData.models.length === 0) {
            return `
                <div class="mm-empty">
                    <div class="mm-empty-icon">📦</div>
                    <div class="mm-empty-title">${t('noModels')}</div>
                    <div class="mm-empty-hint">${t('noModelsHint')}</div>
                </div>
            `;
        }
        
        if (!selectedModelId) {
            return `
                <div class="mm-empty">
                    <div class="mm-empty-icon">👈</div>
                    <div class="mm-empty-title">${t('selectModel')}</div>
                    <div class="mm-empty-hint">${t('selectModelHint')}</div>
                </div>
            `;
        }
        
        const model = pluginData.models.find(m => m.id === selectedModelId);
        if (!model) return '';
        
        const isVerifying = verifyingModelId === model.id;
        
        return `
            <div class="mm-section-title">${escapeHtml(model.displayName || t('selectModel'))}</div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('displayName')}</label>
                <input type="text" class="mm-input" id="mm-displayName" value="${escapeHtml(model.displayName || '')}" placeholder="My GPT-4">
                <div class="mm-form-hint">${t('displayNameHint')}</div>
            </div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('apiEndpoint')}</label>
                <input type="text" class="mm-input" id="mm-apiUrl" value="${escapeHtml(model.api_url || '')}" placeholder="https://api.openai.com/v1">
            </div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('apiKey')} <span style="color: var(--text-secondary);">(${t('optional')})</span></label>
                <input type="password" class="mm-input" id="mm-apiKey" value="${escapeHtml(model.api_key || '')}" placeholder="sk-...">
            </div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('modelId')}</label>
                <input type="text" class="mm-input" id="mm-modelId" value="${escapeHtml(model.model_id || '')}" placeholder="gpt-4o">
            </div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('capabilities')}</label>
                <div class="mm-checkbox-group">
                    <label class="mm-checkbox-label">
                        <input type="checkbox" id="mm-vision" ${model.capability?.vision ? 'checked' : ''}>
                        ${t('vision')}
                    </label>
                    <label class="mm-checkbox-label">
                        <input type="checkbox" id="mm-reasoning" ${model.capability?.reasoning ? 'checked' : ''}>
                        ${t('reasoning')}
                    </label>
                    <label class="mm-checkbox-label">
                        <input type="checkbox" id="mm-tools" ${model.capability?.tools ? 'checked' : ''}>
                        ${t('tools')}
                    </label>
                </div>
            </div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('contextLength')}</label>
                <input type="number" class="mm-input" id="mm-contextLength" value="${model.context_length || 8192}" placeholder="8192">
            </div>
            
            <div class="mm-form-group">
                <label class="mm-form-label">${t('maxOutput')}</label>
                <input type="number" class="mm-input" id="mm-maxOutput" value="${model.max_output || 4096}" placeholder="4096">
            </div>
            
            <div class="mm-btn-row">
                <button class="mm-btn-verify" id="mm-verify" ${isVerifying ? 'disabled' : ''}>
                    ${isVerifying ? t('verifying') : t('verify')}
                </button>
                <button class="mm-btn-save" id="mm-save">${t('save')}</button>
                <button class="mm-btn-danger" id="mm-delete">${t('deleteModel')}</button>
            </div>
            
            ${model.verifyMessage ? `
                <div class="mm-verify-msg ${model.status || ''}">${escapeHtml(model.verifyMessage)}</div>
            ` : ''}
        `;
    }
    
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
    
    function renderUI() {
        const container = document.getElementById('mm-settings-container');
        if (!container) return;
        
        container.innerHTML = `
            <style>${getStyles()}</style>
            <div class="mm-container">
                <div class="mm-sidebar">
                    <div class="mm-sidebar-header">
                        <button class="mm-add-btn" id="mm-add-model">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M12 5v14M5 12h14"/>
                            </svg>
                            ${t('addModel')}
                        </button>
                    </div>
                    <div class="mm-model-list">
                        ${renderModelList()}
                    </div>
                </div>
                <div class="mm-content">
                    ${renderModelForm()}
                </div>
            </div>
        `;
        
        bindEvents();
    }
    
    function bindEvents() {
        // Add model button
        const addBtn = document.getElementById('mm-add-model');
        if (addBtn) {
            addBtn.onclick = () => {
                const newModel = createNewModel();
                newModel.displayName = `Model ${pluginData.models.length + 1}`;
                pluginData.models.push(newModel);
                selectedModelId = newModel.id;
                savePluginData();
                renderUI();
            };
        }
        
        // Model list items
        document.querySelectorAll('.mm-model-item').forEach(item => {
            item.onclick = (e) => {
                // Check if clicking on toggle
                const toggleEl = e.target.closest('.mm-model-toggle');
                if (toggleEl) {
                    e.stopPropagation();
                    const modelId = toggleEl.dataset.toggleId;
                    const model = pluginData.models.find(m => m.id === modelId);
                    if (model) {
                        if (model.active) {
                            deactivateModel(modelId);
                        } else {
                            activateModel(modelId);
                        }
                    }
                    return;
                }
                
                // Select model
                const modelId = item.dataset.modelId;
                if (modelId) {
                    selectedModelId = modelId;
                    renderUI();
                }
            };
        });
        
        // Verify button
        const verifyBtn = document.getElementById('mm-verify');
        if (verifyBtn) {
            verifyBtn.onclick = async () => {
                const model = pluginData.models.find(m => m.id === selectedModelId);
                if (!model) return;
                
                // Update model from form first
                updateModelFromForm(model);
                
                // Verify
                await verifyModel(model);
                renderUI();
            };
        }
        
        // Save button
        const saveBtn = document.getElementById('mm-save');
        if (saveBtn) {
            saveBtn.onclick = async () => {
                const model = pluginData.models.find(m => m.id === selectedModelId);
                if (!model) return;
                
                // Update model from form
                updateModelFromForm(model);
                
                // Save
                await saveModel(model);
                renderUI();
            };
        }
        
        // Delete button
        const deleteBtn = document.getElementById('mm-delete');
        if (deleteBtn) {
            deleteBtn.onclick = () => {
                if (confirm(t('confirmDelete'))) {
                    deleteModel(selectedModelId);
                }
            };
        }
    }
    
    // ============ Settings UI Hook ============
    function createSettingsUI(container) {
        container.innerHTML = `<div id="mm-settings-container" style="height: 100%;"></div>`;
        
        // Load data and render
        loadPluginData().then(() => {
            // Auto-select first model if none selected
            if (!selectedModelId && pluginData.models.length > 0) {
                selectedModelId = pluginData.models[0].id;
            }
            renderUI();
        });
    }
    
    // ============ Close Settings ============
    function closeSettings() {
        const closeBtn = document.querySelector('.plugin-settings-modal .close-btn');
        if (closeBtn) {
            closeBtn.click();
        }
    }
    
    // ============ Register Hooks ============
    ChatRaw.hooks.register('custom_settings', (data) => {
        if (data.pluginId === PLUGIN_ID && data.container) {
            createSettingsUI(data.container);
            return true;
        }
        return false;
    });
    
    // Listen for settings open event
    window.addEventListener('plugin-settings-open', (e) => {
        console.log('[MultiModel] Received plugin-settings-open event:', e.detail);
        if (e.detail?.pluginId === PLUGIN_ID) {
            const container = document.getElementById('plugin-custom-settings-area');
            if (container) {
                console.log('[MultiModel] Injecting settings UI');
                createSettingsUI(container);
            } else {
                console.error('[MultiModel] Container not found: plugin-custom-settings-area');
            }
        }
    });
    
    // ============ Initialize ============
    async function init() {
        await loadPluginData();
        console.log('[MultiModel] Plugin initialized');
    }
    
    init();
    
})(window.ChatRawPlugin);
