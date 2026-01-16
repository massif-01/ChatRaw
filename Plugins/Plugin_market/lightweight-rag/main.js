/**
 * Lightweight RAG Demo Plugin for ChatRaw
 * Provides RAG (Retrieval Augmented Generation) functionality
 * 
 * @version 1.0.0
 * @author ChatRaw
 * @license Apache-2.0
 */
(function(ChatRaw) {
    'use strict';
    
    // Safety check
    if (!ChatRaw || !ChatRaw.hooks) {
        console.error('[RAG Plugin] ChatRawPlugin not available, retrying in 500ms...');
        setTimeout(() => {
            if (window.ChatRawPlugin && window.ChatRawPlugin.hooks) {
                // Re-execute with the now-available ChatRawPlugin
                arguments.callee(window.ChatRawPlugin);
            } else {
                console.error('[RAG Plugin] ChatRawPlugin still not available after retry');
            }
        }, 500);
        return;
    }
    
    const PLUGIN_ID = 'lightweight-rag';
    
    // ============ i18n Translations ============
    const i18n = {
        en: {
            ragSettings: 'RAG Settings',
            ragSettingsDesc: 'Configure retrieval augmented generation parameters.',
            knowledgeBase: 'Knowledge Base',
            kbDesc: 'Upload documents for RAG context.',
            embeddingModel: 'Embedding Model',
            embeddingModelDesc: 'Configure the embedding model for document vectorization.',
            rerankerModel: 'Reranker Model',
            rerankerModelDesc: 'Configure the reranker model for improving search results.',
            chunkSize: 'Chunk Size',
            chunkSizeHint: 'Number of characters per document chunk',
            chunkOverlap: 'Chunk Overlap',
            chunkOverlapHint: 'Overlap characters between adjacent chunks',
            topKHint: 'Number of relevant documents to retrieve',
            scoreThreshold: 'Score Threshold',
            scoreThresholdHint: 'Documents below this threshold will be filtered',
            uploadDocument: 'Upload Document',
            noDocuments: 'No documents yet. Upload one above.',
            saveAndVerify: 'Save & Verify',
            verifying: 'Verifying...',
            active: 'Active',
            error: 'Error',
            save: 'Save',
            cancel: 'Cancel',
            settingsSaved: 'Settings saved',
            saveFailed: 'Save failed',
            uploadSuccess: 'uploaded successfully',
            uploadFailed: 'Upload failed',
            documentDeleted: 'Document deleted',
            deleteFailed: 'Delete failed',
            optional: 'Optional'
        },
        zh: {
            ragSettings: 'RAG 设置',
            ragSettingsDesc: '配置检索增强生成参数',
            knowledgeBase: '知识库',
            kbDesc: '上传文档用于 RAG 上下文',
            embeddingModel: '嵌入模型',
            embeddingModelDesc: '配置用于文档向量化的嵌入模型',
            rerankerModel: '重排模型',
            rerankerModelDesc: '配置用于改善搜索结果的重排模型',
            chunkSize: '分块大小',
            chunkSizeHint: '每个文档块的字符数',
            chunkOverlap: '分块重叠',
            chunkOverlapHint: '相邻块之间的重叠字符数',
            topKHint: '要检索的相关文档数量',
            scoreThreshold: '分数阈值',
            scoreThresholdHint: '低于此阈值的文档将被过滤',
            uploadDocument: '上传文档',
            noDocuments: '暂无文档，请在上方上传',
            saveAndVerify: '保存并验证',
            verifying: '验证中...',
            active: '活跃',
            error: '错误',
            save: '保存',
            cancel: '取消',
            settingsSaved: '设置已保存',
            saveFailed: '保存失败',
            uploadSuccess: '上传成功',
            uploadFailed: '上传失败',
            documentDeleted: '文档已删除',
            deleteFailed: '删除失败',
            optional: '可选'
        }
    };
    
    // Get translation
    function t(key) {
        const lang = ChatRaw.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // ============ State Management ============
    let ragSettings = {
        chunk_size: 500,
        chunk_overlap: 50,
        top_k: 3,
        score_threshold: 0.5
    };
    
    let documents = [];
    let models = [];
    let uploadProgress = { show: false, filename: '', progress: 0, status: '' };
    let currentTab = 'rag';
    
    // ============ API Functions ============
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            if (res.ok) {
                const data = await res.json();
                if (data.rag_settings) {
                    ragSettings = { ...ragSettings, ...data.rag_settings };
                }
            }
        } catch (e) {
            console.error('[RAG Plugin] Failed to load settings:', e);
        }
    }
    
    async function saveSettings() {
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rag_settings: ragSettings })
            });
            if (res.ok) {
                ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                return true;
            } else {
                throw new Error('Save failed');
            }
        } catch (e) {
            console.error('[RAG Plugin] Failed to save settings:', e);
            ChatRaw.utils?.showToast?.(t('saveFailed'), 'error');
            return false;
        }
    }
    
    async function loadDocuments() {
        try {
            const res = await fetch('/api/documents');
            if (res.ok) {
                documents = await res.json();
                renderDocumentList();
            }
        } catch (e) {
            console.error('[RAG Plugin] Failed to load documents:', e);
        }
    }
    
    async function loadModels() {
        try {
            const res = await fetch('/api/models');
            if (res.ok) {
                models = await res.json();
                renderModelCards();
            }
        } catch (e) {
            console.error('[RAG Plugin] Failed to load models:', e);
        }
    }
    
    async function deleteDocument(docId) {
        try {
            const res = await fetch(`/api/documents/${docId}`, { method: 'DELETE' });
            if (res.ok) {
                documents = documents.filter(d => d.id !== docId);
                renderDocumentList();
                ChatRaw.utils?.showToast?.(t('documentDeleted'), 'success');
            } else {
                throw new Error('Delete failed');
            }
        } catch (e) {
            console.error('[RAG Plugin] Failed to delete document:', e);
            ChatRaw.utils?.showToast?.(t('deleteFailed'), 'error');
        }
    }
    
    async function uploadDocument(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        uploadProgress = { show: true, filename: file.name, progress: 0, status: 'uploading' };
        renderUploadProgress();
        
        try {
            const res = await fetch('/api/documents', {
                method: 'POST',
                body: formData
            });
            
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(errorData.error || 'Upload failed');
            }
            
            // Read streaming response (NDJSON)
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                
                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        uploadProgress.progress = data.progress || 0;
                        uploadProgress.status = data.status || 'processing';
                        renderUploadProgress();
                        
                        if (data.status === 'done') {
                            uploadProgress.show = false;
                            renderUploadProgress();
                            await loadDocuments();
                            ChatRaw.utils?.showToast?.(file.name + ' ' + t('uploadSuccess'), 'success');
                        }
                    } catch (e) {
                        console.error('[RAG Plugin] Parse progress error:', e);
                    }
                }
            }
        } catch (e) {
            console.error('[RAG Plugin] Upload failed:', e);
            uploadProgress.show = false;
            renderUploadProgress();
            ChatRaw.utils?.showToast?.(t('uploadFailed') + ': ' + e.message, 'error');
        }
    }
    
    async function saveAndVerifyModel(model, index) {
        const modelCard = document.querySelector(`[data-model-index="${index}"]`);
        if (!modelCard) return;
        
        const statusEl = modelCard.querySelector('.rag-model-status');
        const messageEl = modelCard.querySelector('.rag-model-message');
        const btnEl = modelCard.querySelector('.rag-model-save-btn');
        
        if (btnEl) btnEl.textContent = t('verifying');
        if (statusEl) statusEl.innerHTML = '';
        if (messageEl) messageEl.textContent = '';
        
        try {
            // First verify the model
            const verifyRes = await fetch('/api/models/verify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(model)
            });
            
            const verifyData = await verifyRes.json();
            
            if (verifyRes.ok && verifyData.success) {
                model.status = 'success';
                model.verifyMessage = verifyData.message || 'Connected';
                if (statusEl) statusEl.innerHTML = `<span style="color:var(--success-color)">● ${t('active')}</span>`;
                
                // Save the model to backend after successful verification
                const saveRes = await fetch('/api/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(model)
                });
                
                if (saveRes.ok) {
                    const savedModel = await saveRes.json();
                    // Update model with saved data (including ID if new)
                    Object.assign(model, savedModel);
                    ChatRaw.utils?.showToast?.(t('settingsSaved'), 'success');
                } else {
                    console.error('[RAG Plugin] Failed to save model');
                }
            } else {
                model.status = 'error';
                model.verifyMessage = verifyData.error || 'Connection failed';
                if (statusEl) statusEl.innerHTML = `<span style="color:var(--error-color)">● ${t('error')}</span>`;
            }
            
            if (messageEl) {
                messageEl.textContent = model.verifyMessage;
                messageEl.style.color = model.status === 'success' ? 'var(--success-color)' : 'var(--error-color)';
            }
        } catch (e) {
            model.status = 'error';
            model.verifyMessage = e.message;
            if (statusEl) statusEl.innerHTML = `<span style="color:var(--error-color)">● ${t('error')}</span>`;
            if (messageEl) {
                messageEl.textContent = e.message;
                messageEl.style.color = 'var(--error-color)';
            }
        }
        
        if (btnEl) btnEl.textContent = t('saveAndVerify');
        
        // Update models array
        models[index] = model;
    }
    
    // ============ UI Rendering ============
    function renderUploadProgress() {
        const container = document.getElementById('rag-upload-progress');
        if (!container) return;
        
        if (!uploadProgress.show) {
            container.style.display = 'none';
            return;
        }
        
        container.style.display = 'block';
        container.innerHTML = `
            <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:0.85rem;">
                <span>${uploadProgress.filename}</span>
                <span>${uploadProgress.status === 'chunking' ? 'Chunking...' : Math.round(uploadProgress.progress) + '%'}</span>
            </div>
            <div style="height:4px; background:var(--bg-hover); border-radius:2px; overflow:hidden;">
                <div style="height:100%; background:var(--text-primary); transition:width 0.2s; width:${uploadProgress.progress}%"></div>
            </div>
        `;
    }
    
    function renderDocumentList() {
        const container = document.getElementById('rag-documents-list');
        if (!container) return;
        
        if (documents.length === 0) {
            container.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:20px;">${t('noDocuments')}</div>`;
            return;
        }
        
        container.innerHTML = documents.map(doc => `
            <div class="nav-item" style="cursor:default; justify-content:space-between; display:flex; align-items:center; padding:12px; background:var(--bg-secondary); border-radius:var(--radius-sm); margin-bottom:8px;">
                <span>${doc.filename}</span>
                <button class="btn-delete" style="opacity:1; background:transparent; border:none; cursor:pointer; font-size:1.2rem; color:var(--text-muted);" onclick="window._ragPlugin.deleteDocument('${doc.id}')">×</button>
            </div>
        `).join('');
    }
    
    function renderModelCards() {
        const embeddingContainer = document.getElementById('rag-embedding-models');
        const rerankerContainer = document.getElementById('rag-reranker-models');
        
        if (!embeddingContainer || !rerankerContainer) return;
        
        const embeddingModels = models.filter(m => m.type === 'embedding');
        const rerankerModels = models.filter(m => m.type === 'rerank');
        
        embeddingContainer.innerHTML = embeddingModels.length > 0 
            ? embeddingModels.map((model, idx) => renderModelCard(model, models.indexOf(model))).join('')
            : '<div style="color:var(--text-muted); padding:20px; text-align:center;">No embedding model configured</div>';
            
        rerankerContainer.innerHTML = rerankerModels.length > 0
            ? rerankerModels.map((model, idx) => renderModelCard(model, models.indexOf(model))).join('')
            : '<div style="color:var(--text-muted); padding:20px; text-align:center;">No reranker model configured (${t("optional")})</div>';
    }
    
    function renderModelCard(model, index) {
        const statusHtml = model.status === 'success' 
            ? `<span style="color:var(--success-color)">● ${t('active')}</span>`
            : model.status === 'error'
            ? `<span style="color:var(--error-color)">● ${t('error')}</span>`
            : '';
            
        return `
            <div class="model-card" data-model-index="${index}" style="background:var(--bg-secondary); padding:20px; border-radius:var(--radius-md); margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                    <span class="model-badge" style="background:${model.type === 'embedding' ? '#3b82f6' : '#8b5cf6'}; color:#fff; padding:4px 12px; border-radius:var(--radius-sm); font-size:0.85rem; font-weight:500;">${model.type === 'embedding' ? 'Embedding' : 'Reranker'}</span>
                    <div class="rag-model-status">${statusHtml}</div>
                </div>
                
                <div class="form-group" style="margin-bottom:16px;">
                    <label class="form-label" style="display:block; margin-bottom:8px; font-weight:500;">API Endpoint</label>
                    <input type="text" class="input-minimal" value="${model.api_url || ''}" 
                        onchange="window._ragPlugin.updateModel(${index}, 'api_url', this.value)"
                        style="width:100%; padding:10px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                </div>
                
                <div class="form-group" style="margin-bottom:16px;">
                    <label class="form-label" style="display:block; margin-bottom:8px; font-weight:500;">API Key (${t('optional')})</label>
                    <input type="password" class="input-minimal" value="${model.api_key || ''}"
                        onchange="window._ragPlugin.updateModel(${index}, 'api_key', this.value)"
                        style="width:100%; padding:10px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                </div>
                
                <div class="form-group" style="margin-bottom:16px;">
                    <label class="form-label" style="display:block; margin-bottom:8px; font-weight:500;">Model ID</label>
                    <input type="text" class="input-minimal" value="${model.model_id || ''}"
                        onchange="window._ragPlugin.updateModel(${index}, 'model_id', this.value)"
                        style="width:100%; padding:10px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-primary);">
                </div>
                
                <button class="btn-primary rag-model-save-btn" onclick="window._ragPlugin.saveAndVerifyModel(${index})"
                    style="width:100%; padding:12px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500;">
                    ${t('saveAndVerify')}
                </button>
                <div class="rag-model-message" style="margin-top:10px; font-size:0.85rem;">${model.verifyMessage || ''}</div>
            </div>
        `;
    }
    
    function createSettingsUI() {
        return `
            <div class="rag-plugin-settings" style="display:flex; height:100%; min-height:400px;">
                <!-- Left Navigation -->
                <div class="rag-settings-nav" style="width:200px; border-right:1px solid var(--border-color); padding:20px 0;">
                    <div class="rag-nav-item ${currentTab === 'rag' ? 'active' : ''}" data-tab="rag" 
                        style="padding:12px 24px; cursor:pointer; ${currentTab === 'rag' ? 'background:var(--bg-hover); font-weight:500;' : ''}">
                        ${t('ragSettings')}
                    </div>
                    <div class="rag-nav-item ${currentTab === 'docs' ? 'active' : ''}" data-tab="docs"
                        style="padding:12px 24px; cursor:pointer; ${currentTab === 'docs' ? 'background:var(--bg-hover); font-weight:500;' : ''}">
                        ${t('knowledgeBase')}
                    </div>
                    <div class="rag-nav-item ${currentTab === 'embedding' ? 'active' : ''}" data-tab="embedding"
                        style="padding:12px 24px; cursor:pointer; ${currentTab === 'embedding' ? 'background:var(--bg-hover); font-weight:500;' : ''}">
                        ${t('embeddingModel')}
                    </div>
                    <div class="rag-nav-item ${currentTab === 'reranker' ? 'active' : ''}" data-tab="reranker"
                        style="padding:12px 24px; cursor:pointer; ${currentTab === 'reranker' ? 'background:var(--bg-hover); font-weight:500;' : ''}">
                        ${t('rerankerModel')}
                    </div>
                </div>
                
                <!-- Right Content -->
                <div class="rag-settings-content" style="flex:1; padding:24px; overflow-y:auto;">
                    <!-- RAG Settings Tab -->
                    <div class="rag-tab-content" data-tab="rag" style="display:${currentTab === 'rag' ? 'block' : 'none'};">
                        <div class="section-header" style="margin-bottom:24px;">
                            <h2 style="margin:0 0 8px 0; font-size:1.25rem;">${t('ragSettings')}</h2>
                            <p style="margin:0; color:var(--text-muted); font-size:0.9rem;">${t('ragSettingsDesc')}</p>
                        </div>
                        
                        <div class="form-group" style="margin-bottom:20px;">
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('chunkSize')}</label>
                            <input type="number" id="rag-chunk-size" value="${ragSettings.chunk_size}" 
                                style="width:100%; padding:10px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-secondary);">
                            <p style="margin:8px 0 0 0; font-size:0.85rem; color:var(--text-muted);">${t('chunkSizeHint')}</p>
                        </div>
                        
                        <div class="form-group" style="margin-bottom:20px;">
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('chunkOverlap')}</label>
                            <input type="number" id="rag-chunk-overlap" value="${ragSettings.chunk_overlap}"
                                style="width:100%; padding:10px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-secondary);">
                            <p style="margin:8px 0 0 0; font-size:0.85rem; color:var(--text-muted);">${t('chunkOverlapHint')}</p>
                        </div>
                        
                        <div class="form-group" style="margin-bottom:20px;">
                            <label style="display:block; margin-bottom:8px; font-weight:500;">Top K</label>
                            <input type="number" id="rag-top-k" value="${ragSettings.top_k}"
                                style="width:100%; padding:10px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:var(--bg-secondary);">
                            <p style="margin:8px 0 0 0; font-size:0.85rem; color:var(--text-muted);">${t('topKHint')}</p>
                        </div>
                        
                        <div class="form-group" style="margin-bottom:20px;">
                            <label style="display:block; margin-bottom:8px; font-weight:500;">${t('scoreThreshold')}: <span id="rag-score-display">${ragSettings.score_threshold}</span></label>
                            <input type="range" id="rag-score-threshold" min="0" max="1" step="0.05" value="${ragSettings.score_threshold}"
                                style="width:100%;"
                                oninput="document.getElementById('rag-score-display').textContent = this.value">
                            <p style="margin:8px 0 0 0; font-size:0.85rem; color:var(--text-muted);">${t('scoreThresholdHint')}</p>
                        </div>
                    </div>
                    
                    <!-- Knowledge Base Tab -->
                    <div class="rag-tab-content" data-tab="docs" style="display:${currentTab === 'docs' ? 'block' : 'none'};">
                        <div class="section-header" style="margin-bottom:24px;">
                            <h2 style="margin:0 0 8px 0; font-size:1.25rem;">${t('knowledgeBase')}</h2>
                            <p style="margin:0; color:var(--text-muted); font-size:0.9rem;">${t('kbDesc')}</p>
                        </div>
                        
                        <div class="upload-area" id="rag-upload-area" 
                            style="border:2px dashed var(--border-color); border-radius:var(--radius-md); padding:40px; text-align:center; cursor:pointer; margin-bottom:20px;">
                            <input type="file" id="rag-file-input" accept=".txt,.md,.pdf,.doc,.docx" style="display:none;">
                            <div style="font-size:2rem; margin-bottom:10px;">📄</div>
                            <div>${t('uploadDocument')}</div>
                        </div>
                        
                        <div id="rag-upload-progress" style="display:none; margin-bottom:20px; padding:16px; background:var(--bg-tertiary); border-radius:var(--radius-sm);"></div>
                        
                        <div id="rag-documents-list"></div>
                    </div>
                    
                    <!-- Embedding Model Tab -->
                    <div class="rag-tab-content" data-tab="embedding" style="display:${currentTab === 'embedding' ? 'block' : 'none'};">
                        <div class="section-header" style="margin-bottom:24px;">
                            <h2 style="margin:0 0 8px 0; font-size:1.25rem;">${t('embeddingModel')}</h2>
                            <p style="margin:0; color:var(--text-muted); font-size:0.9rem;">${t('embeddingModelDesc')}</p>
                        </div>
                        <div id="rag-embedding-models"></div>
                    </div>
                    
                    <!-- Reranker Model Tab -->
                    <div class="rag-tab-content" data-tab="reranker" style="display:${currentTab === 'reranker' ? 'block' : 'none'};">
                        <div class="section-header" style="margin-bottom:24px;">
                            <h2 style="margin:0 0 8px 0; font-size:1.25rem;">${t('rerankerModel')}</h2>
                            <p style="margin:0; color:var(--text-muted); font-size:0.9rem;">${t('rerankerModelDesc')}</p>
                        </div>
                        <div id="rag-reranker-models"></div>
                    </div>
                </div>
            </div>
            
            <!-- Actions Bar -->
            <div class="rag-actions-bar" style="display:flex; justify-content:flex-end; gap:12px; padding:16px 24px; border-top:1px solid var(--border-color);">
                <button class="btn-secondary" onclick="window._ragPlugin.closeSettings()" 
                    style="padding:10px 24px; border:1px solid var(--border-color); border-radius:var(--radius-sm); background:transparent; cursor:pointer;">
                    ${t('cancel')}
                </button>
                <button class="btn-primary" onclick="window._ragPlugin.saveAllSettings()"
                    style="padding:10px 24px; background:var(--text-primary); color:var(--bg-primary); border:none; border-radius:var(--radius-sm); cursor:pointer; font-weight:500;">
                    ${t('save')}
                </button>
            </div>
        `;
    }
    
    function bindSettingsEvents() {
        // Tab navigation
        document.querySelectorAll('.rag-nav-item').forEach(item => {
            item.addEventListener('click', () => {
                const tab = item.dataset.tab;
                currentTab = tab;
                
                // Update nav styles
                document.querySelectorAll('.rag-nav-item').forEach(nav => {
                    nav.style.background = nav.dataset.tab === tab ? 'var(--bg-hover)' : '';
                    nav.style.fontWeight = nav.dataset.tab === tab ? '500' : '';
                });
                
                // Update content visibility
                document.querySelectorAll('.rag-tab-content').forEach(content => {
                    content.style.display = content.dataset.tab === tab ? 'block' : 'none';
                });
            });
        });
        
        // File upload
        const uploadArea = document.getElementById('rag-upload-area');
        const fileInput = document.getElementById('rag-file-input');
        
        if (uploadArea && fileInput) {
            uploadArea.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => {
                if (e.target.files && e.target.files[0]) {
                    uploadDocument(e.target.files[0]);
                }
            });
        }
        
        // Render documents and models
        renderDocumentList();
        renderModelCards();
    }
    
    async function saveAllSettings() {
        // Collect settings from form
        const chunkSize = document.getElementById('rag-chunk-size');
        const chunkOverlap = document.getElementById('rag-chunk-overlap');
        const topK = document.getElementById('rag-top-k');
        const scoreThreshold = document.getElementById('rag-score-threshold');
        
        if (chunkSize) ragSettings.chunk_size = parseInt(chunkSize.value) || 500;
        if (chunkOverlap) ragSettings.chunk_overlap = parseInt(chunkOverlap.value) || 50;
        if (topK) ragSettings.top_k = parseInt(topK.value) || 3;
        if (scoreThreshold) ragSettings.score_threshold = parseFloat(scoreThreshold.value) || 0.5;
        
        const success = await saveSettings();
        if (success) {
            closeSettings();
        }
    }
    
    function closeSettings() {
        // Try to close via Alpine.js state
        const app = document.querySelector('[x-data]');
        if (app && app.__x) {
            app.__x.$data.showPluginSettings = false;
        } else if (app && app._x_dataStack) {
            // Alpine.js v3 way
            app._x_dataStack[0].showPluginSettings = false;
        }
        
        // Fallback: click the modal overlay to close
        const overlay = document.querySelector('.modal-overlay[x-show="showPluginSettings"]');
        if (overlay) {
            overlay.click();
        }
    }
    
    function updateModel(index, field, value) {
        if (models[index]) {
            models[index][field] = value;
        }
    }
    
    // ============ Global Plugin API ============
    window._ragPlugin = {
        deleteDocument,
        saveAndVerifyModel: (index) => saveAndVerifyModel(models[index], index),
        saveAllSettings,
        closeSettings,
        updateModel
    };
    
    // ============ Settings UI Injection ============
    function injectSettingsUI() {
        // Find the custom settings container by ID
        const customContainer = document.getElementById('plugin-custom-settings-area');
        
        if (customContainer) {
            // Inject our custom UI
            customContainer.innerHTML = createSettingsUI();
            bindSettingsEvents();
            console.log('[RAG Plugin] Settings UI injected');
        } else {
            console.warn('[RAG Plugin] Custom settings container not found');
        }
    }
    
    // ============ Event Listener for Settings Modal ============
    function setupSettingsListener() {
        // Listen for plugin settings open event from main app
        window.addEventListener('plugin-settings-open', (e) => {
            console.log('[RAG Plugin] Received plugin-settings-open event:', e.detail);
            if (e.detail.pluginId === PLUGIN_ID && e.detail.customSettings) {
                // Wait for Alpine.js to render the container
                setTimeout(() => {
                    injectSettingsUI();
                }, 150);
            }
        });
        
        // Also check if settings modal is already open (in case we loaded late)
        const customContainer = document.getElementById('plugin-custom-settings-area');
        if (customContainer) {
            console.log('[RAG Plugin] Settings container already exists, injecting UI...');
            setTimeout(() => injectSettingsUI(), 100);
        }
    }
    
    // ============ Hooks Registration ============
    
    // Register before_send hook to control RAG
    ChatRaw.hooks.register('before_send', {
        priority: 5,
        handler: async (body) => {
            try {
                // Check if this plugin is enabled
                const res = await fetch('/api/plugins');
                if (res.ok) {
                    const plugins = await res.json();
                    const ragPlugin = plugins.find(p => p.id === PLUGIN_ID);
                    const enabled = ragPlugin?.enabled ?? false;
                    
                    return {
                        success: true,
                        body: { use_rag: enabled }
                    };
                }
            } catch (e) {
                console.error('[RAG Plugin] Error checking plugin status:', e);
            }
            return { success: false };
        }
    });
    
    // Register custom_settings hook
    ChatRaw.hooks.register('custom_settings', {
        pluginId: PLUGIN_ID,
        handler: () => {
            return {
                success: true,
                customUI: true
            };
        }
    });
    
    // ============ Initialization ============
    async function init() {
        console.log('[RAG Plugin] Initializing...');
        
        // Load data
        await loadSettings();
        await loadDocuments();
        await loadModels();
        
        // Setup event listener for settings modal
        setupSettingsListener();
        
        console.log('[RAG Plugin] Initialized successfully');
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})(window.ChatRawPlugin);
