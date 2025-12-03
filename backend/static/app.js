// JustChat - Minimalist AI Chat Application

// i18n translations
const i18n = {
    en: {
        newChat: 'New Chat',
        settings: 'Settings',
        delete: 'Delete',
        expand: 'Expand',
        collapse: 'Collapse',
        defaultSubtitle: 'Minimalist AI Assistant, Ready to Use',
        fastResponse: 'Fast Response',
        docRAG: 'Document RAG',
        visionAI: 'Vision AI',
        knowledgeBase: 'Knowledge Base',
        kbEnabled: 'KB Enabled',
        uploadImage: 'Upload Image',
        image: 'Image',
        imageSelected: 'Image Selected',
        parseUrl: 'Parse URL',
        enterUrl: 'Enter URL',
        parsing: 'Parsing...',
        urlAttached: 'URL Attached',
        parseFailed: 'Parse failed',
        urlPlaceholder: 'https://example.com/article',
        confirm: 'OK',
        ragReferences: 'References',
        relevance: 'Relevance',
        inputPlaceholder: 'Type a message... (Enter to send, Shift+Enter for new line)',
        modelConfig: 'Models',
        chatSettings: 'Chat',
        chatSettingsDesc: 'Adjust how the AI responds to your inputs.',
        ragSettings: 'RAG',
        ragSettingsDesc: 'Configure retrieval augmented generation parameters.',
        uiSettings: 'Interface',
        uiSettingsDesc: 'Customize the interface appearance.',
        kbDesc: 'Upload documents for RAG context.',
        modelConfigDesc: 'Manage your AI model connections and parameters.',
        modelType: 'Type',
        chat: 'Chat',
        embedding: 'Embedding',
        reranker: 'Reranker',
        optional: 'Optional',
        contextLength: 'Context Length',
        maxOutput: 'Max Output',
        capabilities: 'Capabilities',
        vision: 'Vision',
        reasoning: 'Reasoning',
        tools: 'Tools',
        saveAndVerify: 'Save & Verify',
        verifying: 'Verifying...',
        verifySuccess: 'Connected',
        verifyFailed: 'Connection failed',
        temperatureHint: 'Lower values make output more deterministic, higher values more creative',
        topPHint: 'Nucleus sampling parameter, controls output diversity',
        streamOutput: 'Stream Output',
        streamHint: 'Display AI response in real-time',
        chunkSize: 'Chunk Size',
        chunkSizeHint: 'Number of characters per document chunk',
        chunkOverlap: 'Chunk Overlap',
        chunkOverlapHint: 'Overlap characters between adjacent chunks',
        topKHint: 'Number of relevant documents to retrieve',
        scoreThreshold: 'Score Threshold',
        scoreThresholdHint: 'Documents below this threshold will be filtered',
        language: 'Language',
        theme: 'Theme',
        light: 'Light',
        dark: 'Dark',
        uploadLogo: 'Upload',
        logoText: 'Logo Text',
        subtitle: 'Subtitle',
        avatars: 'Avatars',
        userAvatar: 'User',
        aiAvatar: 'AI',
        uploadDocument: 'Upload Document',
        noDocuments: 'No documents yet. Upload one above.',
        cancel: 'Cancel',
        save: 'Save',
        uploadSuccess: 'uploaded successfully',
        uploadFailed: 'Upload failed',
        deleteFailed: 'Delete failed',
        saveFailed: 'Save failed',
        settingsSaved: 'Settings saved',
        sendFailed: 'Send failed',
        createChatFailed: 'Failed to create chat',
        documentDeleted: 'Document deleted',
        logoName: 'Logo & Name',
        uploadUserAvatar: 'Upload User Avatar',
        uploadAIAvatar: 'Upload AI Avatar',
        active: 'Active',
        error: 'Error',
        apacheLicense: 'Apache 2.0 License'
    },
    zh: {
        newChat: '新对话',
        settings: '设置',
        delete: '删除',
        expand: '展开',
        collapse: '收起',
        defaultSubtitle: '极简AI助手，开箱即用',
        fastResponse: '极速响应',
        docRAG: '文档RAG',
        visionAI: '视觉理解',
        knowledgeBase: '知识库',
        kbEnabled: '知识库已开启',
        uploadImage: '上传图片',
        image: '图片',
        imageSelected: '已选择图片',
        parseUrl: '解析网页',
        enterUrl: '输入网址',
        parsing: '解析中...',
        urlAttached: '已附加网页',
        parseFailed: '解析失败',
        urlPlaceholder: 'https://example.com/article',
        confirm: '确定',
        ragReferences: '引用来源',
        relevance: '相关度',
        inputPlaceholder: '输入消息... (Enter 发送, Shift+Enter 换行)',
        modelConfig: '模型配置',
        modelConfigDesc: '管理您的AI模型连接和参数',
        chatSettings: '聊天设置',
        chatSettingsDesc: '调整AI对您输入的响应方式',
        ragSettings: 'RAG设置',
        ragSettingsDesc: '配置检索增强生成 (RAG) 参数',
        uiSettings: '界面设置',
        uiSettingsDesc: '自定义界面外观',
        kbDesc: '上传用于RAG上下文的文档',
        modelType: '类型',
        chat: '聊天',
        embedding: '嵌入',
        reranker: '重排',
        optional: '可选',
        contextLength: '上下文长度',
        maxOutput: '最大输出',
        capabilities: '模型能力',
        vision: '视觉',
        reasoning: '推理',
        tools: '工具',
        saveAndVerify: '保存并验证',
        verifying: '验证中...',
        verifySuccess: '连接成功',
        verifyFailed: '连接失败',
        temperatureHint: '较低的值使输出更确定，较高的值更有创意',
        topPHint: '核采样参数，控制输出的多样性',
        streamOutput: '流式输出',
        streamHint: '实时显示AI的回复内容',
        chunkSize: '文档块大小',
        chunkSizeHint: '文档分块的字符数',
        chunkOverlap: '块重叠',
        chunkOverlapHint: '相邻块之间的重叠字符数',
        topKHint: '检索相关文档的数量',
        scoreThreshold: '相似度阈值',
        scoreThresholdHint: '低于此阈值的文档将被过滤',
        language: '语言',
        theme: '主题',
        light: '浅色',
        dark: '深色',
        uploadLogo: '上传',
        logoText: 'Logo文字',
        subtitle: '副标题',
        avatars: '头像',
        userAvatar: '用户',
        aiAvatar: 'AI',
        uploadDocument: '上传文档',
        noDocuments: '暂无文档，请在上方上传',
        cancel: '取消',
        save: '保存',
        uploadSuccess: '上传成功',
        uploadFailed: '上传失败',
        deleteFailed: '删除失败',
        saveFailed: '保存失败',
        settingsSaved: '设置已保存',
        sendFailed: '发送失败',
        createChatFailed: '创建对话失败',
        documentDeleted: '文档已删除',
        logoName: 'Logo & 名称',
        uploadUserAvatar: '上传用户头像',
        uploadAIAvatar: '上传 AI 头像',
        active: '活跃',
        error: '错误',
        apacheLicense: 'Apache 2.0 协议'
    }
};

// Configure marked.js
marked.setOptions({
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (e) {}
        }
        return hljs.highlightAuto(code).value;
    },
    breaks: true,
    gfm: true
});

function app() {
    return {
        // Language
        lang: localStorage.getItem('justchat_lang') || 'en',
        
        // State
        sidebarCollapsed: window.innerWidth < 768,
        showSettings: false,
        settingsTab: 'models',
        currentChatId: null,
        inputMessage: '',
        useRAG: false,
        isGenerating: false,
        uploadedImage: null,
        uploadedImageBase64: '',
        uploadProgress: { show: false, filename: '', progress: 0, status: '', current: 0, total: 0 },
        
        // URL Parser state
        showUrlInput: false,
        urlInputValue: '',
        isParsingUrl: false,
        parsedUrl: null,  // { title, content, url }
        parsedUrlTitle: '',
        
        // Data
        chats: [],
        messages: [],
        models: [],
        documents: [],
        settings: {
            chat_settings: {
                temperature: 0.7,
                top_p: 0.9,
                stream: true
            },
            rag_settings: {
                chunk_size: 500,
                chunk_overlap: 50,
                top_k: 3,
                score_threshold: 0.5
            },
            ui_settings: {
                logo_data: '',
                logo_text: 'ChatRaw',
                subtitle: '',
                theme_mode: 'dark',
                user_avatar: '',
                assistant_avatar: ''
            }
        },
        
        // Toast
        toast: {
            show: false,
            message: '',
            type: ''
        },
        
        // Translation helper
        t(key) {
            return i18n[this.lang][key] || key;
        },
        
        // Set language
        setLanguage(newLang) {
            this.lang = newLang;
            localStorage.setItem('justchat_lang', newLang);
        },
        
        // Get model type display name
        getModelTypeName(type) {
            const names = {
                chat: this.t('chat'),
                embedding: this.t('embedding'),
                rerank: this.t('reranker')
            };
            return names[type] || type;
        },
        
        // Initialize
        async init() {
            await this.loadSettings();
            await this.loadModels();
            await this.loadChats();
            await this.loadDocuments();
            this.applyTheme();
            // Update favicon if logo is set
            if (this.settings.ui_settings.logo_data) {
                this.updateFavicon(this.settings.ui_settings.logo_data);
            }
        },
        
        // Apply theme
        applyTheme() {
            document.documentElement.setAttribute('data-theme', this.settings.ui_settings.theme_mode);
        },
        
        // Load settings
        async loadSettings() {
            try {
                const res = await fetch('/api/settings');
                if (res.ok) {
                    const data = await res.json();
                    // Deep merge settings
                    if (data.chat_settings) {
                        this.settings.chat_settings = { ...this.settings.chat_settings, ...data.chat_settings };
                    }
                    if (data.rag_settings) {
                        this.settings.rag_settings = { ...this.settings.rag_settings, ...data.rag_settings };
                    }
                    if (data.ui_settings) {
                        this.settings.ui_settings = { ...this.settings.ui_settings, ...data.ui_settings };
                    }
                }
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        },
        
        // Load model configs
        async loadModels() {
            try {
                const res = await fetch('/api/models');
                if (res.ok) {
                    this.models = await res.json();
                    this.models.forEach(m => {
                        if (!m.capability) {
                            m.capability = { vision: false, reasoning: false, tools: false };
                        }
                    });
                }
            } catch (e) {
                console.error('Failed to load models:', e);
            }
        },
        
        // Load chat list
        async loadChats() {
            try {
                const res = await fetch('/api/chats');
                if (res.ok) {
                    this.chats = await res.json() || [];
                }
            } catch (e) {
                console.error('Failed to load chats:', e);
            }
        },
        
        // Load documents
        async loadDocuments() {
            try {
                const res = await fetch('/api/documents');
                if (res.ok) {
                    this.documents = await res.json() || [];
                }
            } catch (e) {
                console.error('Failed to load documents:', e);
            }
        },
        
        // Create new chat
        async createNewChat() {
            try {
                const res = await fetch('/api/chats', { method: 'POST' });
                if (res.ok) {
                    const chat = await res.json();
                    this.chats.unshift(chat);
                    if (this.chats.length > 10) {
                        this.chats.pop();
                    }
                    this.selectChat(chat.id);
                }
            } catch (e) {
                this.showToast(this.t('createChatFailed'), 'error');
            }
        },
        
        // Select chat
        async selectChat(chatId) {
            this.currentChatId = chatId;
            await this.loadMessages(chatId);
        },
        
        // Load messages
        async loadMessages(chatId) {
            try {
                const res = await fetch(`/api/chats/${chatId}/messages`);
                if (res.ok) {
                    this.messages = await res.json() || [];
                    this.$nextTick(() => this.scrollToBottom());
                }
            } catch (e) {
                console.error('Failed to load messages:', e);
            }
        },
        
        // Delete chat
        async deleteChat(chatId) {
            try {
                await fetch(`/api/chats/${chatId}`, { method: 'DELETE' });
                this.chats = this.chats.filter(c => c.id !== chatId);
                if (this.currentChatId === chatId) {
                    this.currentChatId = null;
                    this.messages = [];
                }
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },
        
        // Send message
        async sendMessage() {
            const message = this.inputMessage.trim();
            if (!message || this.isGenerating) return;
            
            this.inputMessage = '';
            this.isGenerating = true;
            
            this.messages.push({
                role: 'user',
                content: message
            });
            this.$nextTick(() => this.scrollToBottom());
            
            try {
                const body = {
                    chat_id: this.currentChatId,
                    message: message,
                    use_rag: this.useRAG,
                    image_base64: this.uploadedImageBase64,
                    web_content: this.parsedUrl ? this.parsedUrl.content : '',
                    web_url: this.parsedUrl ? this.parsedUrl.url : ''
                };
                
                this.removeUploadedImage();
                this.removeParsedUrl();
                
                if (this.settings.chat_settings.stream) {
                    await this.handleStreamResponse(body);
                } else {
                    await this.handleNormalResponse(body);
                }
                
                await this.loadChats();
                
            } catch (e) {
                console.error('Failed to send message:', e);
                this.showToast(this.t('sendFailed') + ': ' + e.message, 'error');
            } finally {
                this.isGenerating = false;
            }
        },
        
        // Handle stream response (NDJSON format) - TRUE STREAMING
        async handleStreamResponse(body) {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || 'Request failed');
            }
            
            const assistantMsg = { role: 'assistant', content: '', references: [] };
            this.messages.push(assistantMsg);
            const msgIndex = this.messages.length - 1;
            
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                
                // Process complete lines
                let newlineIdx;
                while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
                    const line = buffer.slice(0, newlineIdx).trim();
                    buffer = buffer.slice(newlineIdx + 1);
                    
                    if (!line) continue;
                    
                    try {
                        const parsed = JSON.parse(line);
                        
                        if (parsed.chat_id) {
                            this.currentChatId = parsed.chat_id;
                        }
                        
                        if (parsed.content) {
                            assistantMsg.content += parsed.content;
                            // Force Alpine.js reactivity update
                            this.messages[msgIndex] = { ...assistantMsg };
                            this.$nextTick(() => this.scrollToBottom());
                        }
                        
                        if (parsed.references) {
                            assistantMsg.references = parsed.references;
                            this.messages[msgIndex] = { ...assistantMsg };
                            this.$nextTick(() => this.scrollToBottom());
                        }
                        
                        if (parsed.error) {
                            assistantMsg.content = 'Error: ' + parsed.error;
                            this.messages[msgIndex] = { ...assistantMsg };
                        }
                    } catch (e) {
                        // ignore parse errors
                    }
                }
            }
        },
        
        // Handle normal response
        async handleNormalResponse(body) {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            const data = await res.json();
            
            if (!res.ok) {
                throw new Error(data.error || 'Request failed');
            }
            
            if (!this.currentChatId && data.chat_id) {
                this.currentChatId = data.chat_id;
            }
            
            this.messages.push({
                role: 'assistant',
                content: data.content,
                references: data.references || []
            });
            this.$nextTick(() => this.scrollToBottom());
        },
        
        // Handle file upload (documents) with progress
        async handleFileUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            // Show progress
            this.uploadProgress = { show: true, filename: file.name, progress: 0, status: 'uploading' };
            
            try {
                const res = await fetch('/api/documents', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const error = await res.text();
                    throw new Error(error);
                }
                
                // Read progress stream
                const reader = res.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    
                    let newlineIdx;
                    while ((newlineIdx = buffer.indexOf('\n')) !== -1) {
                        const line = buffer.slice(0, newlineIdx).trim();
                        buffer = buffer.slice(newlineIdx + 1);
                        
                        if (!line) continue;
                        
                        try {
                            const data = JSON.parse(line);
                            
                            if (data.status === 'chunking') {
                                this.uploadProgress.status = 'chunking';
                                this.uploadProgress.total = data.total;
                            } else if (data.status === 'embedding') {
                                this.uploadProgress.status = 'embedding';
                                this.uploadProgress.progress = data.progress;
                                this.uploadProgress.current = data.current;
                                this.uploadProgress.total = data.total;
                            } else if (data.status === 'done') {
                                this.uploadProgress.show = false;
                                this.showToast(`"${file.name}" ${this.t('uploadSuccess')}`, 'success');
                                await this.loadDocuments();
                            }
                        } catch (e) {
                            // ignore parse errors
                        }
                    }
                }
            } catch (e) {
                this.uploadProgress.show = false;
                this.showToast(this.t('uploadFailed') + ': ' + e.message, 'error');
            }
            
            event.target.value = '';
        },
        
        // Handle image upload
        async handleImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const res = await fetch('/api/upload/image', {
                    method: 'POST',
                    body: formData
                });
                
                if (res.ok) {
                    const data = await res.json();
                    this.uploadedImage = file.name;
                    this.uploadedImageBase64 = data.base64;
                } else {
                    const error = await res.json();
                    throw new Error(error.error);
                }
            } catch (e) {
                this.showToast(this.t('uploadFailed') + ': ' + e.message, 'error');
            }
            
            event.target.value = '';
        },
        
        // Handle logo upload
        handleLogoUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                this.settings.ui_settings.logo_data = e.target.result;
                this.updateFavicon(e.target.result);
            };
            reader.readAsDataURL(file);
            
            event.target.value = '';
        },
        
        // Update favicon
        updateFavicon(dataUrl) {
            if (dataUrl) {
                document.getElementById('favicon').href = dataUrl;
                document.title = this.settings.ui_settings.logo_text || 'ChatRaw';
            }
        },
        
        // Handle avatar upload
        handleAvatarUpload(event, type) {
            const file = event.target.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                if (type === 'user') {
                    this.settings.ui_settings.user_avatar = e.target.result;
                } else {
                    this.settings.ui_settings.assistant_avatar = e.target.result;
                }
            };
            reader.readAsDataURL(file);
            
            event.target.value = '';
        },
        
        // Remove uploaded image
        removeUploadedImage() {
            this.uploadedImage = null;
            this.uploadedImageBase64 = '';
        },
        
        // Toggle URL input popup
        toggleUrlInput() {
            this.showUrlInput = !this.showUrlInput;
            if (this.showUrlInput) {
                this.urlInputValue = '';
                this.$nextTick(() => {
                    const input = document.querySelector('.url-input-popup input');
                    if (input) input.focus();
                });
            }
        },
        
        // Parse URL
        async parseUrl() {
            const url = this.urlInputValue.trim();
            if (!url) return;
            
            this.isParsingUrl = true;
            
            try {
                const res = await fetch('/api/parse-url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    this.parsedUrl = {
                        title: data.title,
                        content: data.content,
                        url: data.url
                    };
                    this.parsedUrlTitle = data.title;
                    this.showUrlInput = false;
                    this.urlInputValue = '';
                    this.showToast(this.t('urlAttached') + ': ' + data.title, 'success');
                } else {
                    this.showToast(this.t('parseFailed') + ': ' + data.error, 'error');
                }
            } catch (e) {
                this.showToast(this.t('parseFailed') + ': ' + e.message, 'error');
            } finally {
                this.isParsingUrl = false;
            }
        },
        
        // Remove parsed URL
        removeParsedUrl() {
            this.parsedUrl = null;
            this.parsedUrlTitle = '';
        },
        
        // Cancel URL input
        cancelUrlInput() {
            this.showUrlInput = false;
            this.urlInputValue = '';
        },
        
        // Delete document
        async deleteDocument(id) {
            try {
                await fetch(`/api/documents/${id}`, { method: 'DELETE' });
                this.documents = this.documents.filter(d => d.id !== id);
                this.showToast(this.t('documentDeleted'), 'success');
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },
        
        // Save and verify model
        async saveAndVerifyModel(model, index) {
            model.status = 'loading';
            model.verifyMessage = '';
            
            try {
                // Set name to model_id if empty
                if (!model.name) {
                    model.name = model.model_id || 'Unnamed';
                }
                
                // Save model config
                const saveRes = await fetch('/api/models', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(model)
                });
                
                if (!saveRes.ok) {
                    throw new Error('Failed to save');
                }
                
                const savedModel = await saveRes.json();
                if (savedModel.id) {
                    model.id = savedModel.id;
                }
                
                // Verify model connection
                const verifyRes = await fetch('/api/models/verify', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        api_url: model.api_url,
                        api_key: model.api_key,
                        model_id: model.model_id,
                        type: model.type
                    })
                });
                
                const verifyData = await verifyRes.json();
                
                if (verifyRes.ok && verifyData.success) {
                    model.status = 'success';
                    model.verifyMessage = this.t('verifySuccess');
                } else {
                    model.status = 'error';
                    model.verifyMessage = verifyData.error || this.t('verifyFailed');
                }
                
            } catch (e) {
                model.status = 'error';
                model.verifyMessage = e.message || this.t('verifyFailed');
            }
        },
        
        // Save all settings
        async saveAllSettings() {
            try {
                // Save settings
                await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(this.settings)
                });
                
                // Save model configs
                for (const model of this.models) {
                    // Set name to model_id if empty
                    if (!model.name) {
                        model.name = model.model_id || 'Unnamed';
                    }
                    await fetch('/api/models', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(model)
                    });
                }
                
                this.applyTheme();
                this.showSettings = false;
                this.showToast(this.t('settingsSaved'), 'success');
                
                await this.loadModels();
                
            } catch (e) {
                this.showToast(this.t('saveFailed') + ': ' + e.message, 'error');
            }
        },
        
        // Render Markdown
        renderMarkdown(content) {
            if (!content) return '';
            return marked.parse(content);
        },
        
        // Scroll to bottom
        scrollToBottom() {
            const container = this.$refs.messagesContainer;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },
        
        // Auto resize textarea
        autoResize(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 200) + 'px';
        },
        
        // Show toast
        showToast(message, type = '') {
            this.toast.message = message;
            this.toast.type = type;
            this.toast.show = true;
            
            setTimeout(() => {
                this.toast.show = false;
            }, 3000);
        }
    };
}
