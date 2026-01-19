// JustChat - Minimalist AI Chat Application

// i18n translations
const i18n = {
    en: {
        newChat: 'New Chat',
        clearAllChats: 'Clear All',
        confirmClearAll: 'Are you sure you want to delete all chats? This cannot be undone.',
        allChatsCleared: 'All chats cleared',
        settings: 'Settings',
        delete: 'Delete',
        expand: 'Expand',
        collapse: 'Collapse',
        defaultSubtitle: 'Minimalist AI Assistant, Ready to Use',
        fastResponse: 'Fast Response',
        multiModel: 'Multi-Model',
        knowledgeBase: 'Knowledge Base',
        kbEnabled: 'KB Enabled',
        thinkingMode: 'Thinking Mode',
        thinkingEnabled: 'Thinking Enabled',
        thinkingProcess: 'Thinking Process',
        uploadImage: 'Upload Image',
        uploadDocument: 'Upload Document',
        image: 'Image',
        imageSelected: 'Image Selected',
        documentAttached: 'Document Attached',
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
        systemPrompt: 'System Prompt',
        systemPromptHint: 'Set instructions for the AI assistant',
        systemPromptPlaceholder: 'You are a helpful assistant...',
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
        stopGeneration: 'Stop',
        createChatFailed: 'Failed to create chat',
        documentDeleted: 'Document deleted',
        logoName: 'Logo & Name',
        uploadUserAvatar: 'Upload User Avatar',
        uploadAIAvatar: 'Upload AI Avatar',
        active: 'Active',
        error: 'Error',
        apacheLicense: 'Apache 2.0 License',
        // Plugin translations
        plugins: 'Plugins',
        pluginMarket: 'Plugin Market',
        pluginMarketDesc: 'Browse and install plugins from the official market.',
        installedPlugins: 'Installed',
        installedPluginsDesc: 'Manage your installed plugins.',
        installLocalPlugin: 'Install Local',
        installLocalPluginDesc: 'Upload a plugin zip file to install.',
        refreshingMarket: 'Refreshing plugin market...',
        networkError: 'Please check network connection',
        retry: 'Retry',
        install: 'Install',
        installed: 'Installed',
        installing: 'Installing...',
        installSuccess: 'Plugin installed successfully',
        installFailed: 'Install failed',
        uninstall: 'Uninstall',
        uninstallSuccess: 'Plugin uninstalled',
        uninstallFailed: 'Uninstall failed',
        confirmUninstall: 'Are you sure you want to uninstall this plugin?',
        pluginDisabled: 'Plugin disabled',
        selectPluginZip: 'Click or drag to upload plugin (.zip)',
        pluginDevGuide: 'Plugin Development Guide',
        noPluginsAvailable: 'No plugins available',
        noPluginsInstalled: 'No plugins installed yet',
        noPluginSettings: 'This plugin has no settings.',
        apiKeySettings: 'API Key Settings',
        enterApiKey: 'Enter API Key',
        apiKeySet: 'API Key is already set. Clear and enter new key to change.',
        onlyZipSupported: 'Only .zip files are supported',
        close: 'Close'
    },
    zh: {
        newChat: '新对话',
        clearAllChats: '清空所有',
        confirmClearAll: '确定要删除所有对话吗？此操作无法撤销。',
        allChatsCleared: '已清空所有对话',
        settings: '设置',
        delete: '删除',
        expand: '展开',
        collapse: '收起',
        defaultSubtitle: '极简AI助手，开箱即用',
        fastResponse: '极速响应',
        multiModel: '多模型支持',
        knowledgeBase: '知识库',
        kbEnabled: '知识库已开启',
        thinkingMode: '思考模式',
        thinkingEnabled: '思考模式已开启',
        thinkingProcess: '思考过程',
        uploadImage: '上传图片',
        uploadDocument: '上传文档',
        image: '图片',
        imageSelected: '已选择图片',
        documentAttached: '已附加文档',
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
        systemPrompt: '系统提示词',
        systemPromptHint: '设置AI助手的行为指令',
        systemPromptPlaceholder: '你是一个有帮助的助手...',
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
        stopGeneration: '停止',
        createChatFailed: '创建对话失败',
        documentDeleted: '文档已删除',
        logoName: 'Logo & 名称',
        uploadUserAvatar: '上传用户头像',
        uploadAIAvatar: '上传 AI 头像',
        active: '活跃',
        error: '错误',
        apacheLicense: 'Apache 2.0 协议',
        // Plugin translations
        plugins: '插件',
        pluginMarket: '插件市场',
        pluginMarketDesc: '浏览并安装官方市场的插件',
        installedPlugins: '已安装',
        installedPluginsDesc: '管理已安装的插件',
        installLocalPlugin: '本地安装',
        installLocalPluginDesc: '上传插件 zip 文件进行安装',
        refreshingMarket: '正在刷新插件市场...',
        networkError: '请检查网络连接',
        retry: '重试',
        install: '安装',
        installed: '已安装',
        installing: '安装中...',
        installSuccess: '插件安装成功',
        installFailed: '安装失败',
        uninstall: '卸载',
        uninstallSuccess: '插件已卸载',
        uninstallFailed: '卸载失败',
        confirmUninstall: '确定要卸载此插件吗？',
        pluginDisabled: '插件已禁用',
        selectPluginZip: '点击或拖拽上传插件 (.zip)',
        pluginDevGuide: '插件开发指南',
        noPluginsAvailable: '暂无可用插件',
        noPluginsInstalled: '暂未安装任何插件',
        noPluginSettings: '此插件暂无可配置项',
        apiKeySettings: 'API 密钥设置',
        enterApiKey: '输入 API Key',
        apiKeySet: 'API Key 已设置。清空后输入新密钥可更改。',
        onlyZipSupported: '仅支持 .zip 文件',
        close: '关闭'
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
        showSystemPrompt: false,
        currentChatId: null,
        inputMessage: '',
        useRAG: false,
        useThinking: false,
        isGenerating: false,
        abortController: null,
        uploadedImage: null,
        uploadedImageBase64: '',
        uploadProgress: { show: false, filename: '', progress: 0, status: '', current: 0, total: 0 },
        
        // URL Parser state
        showUrlInput: false,
        urlInputValue: '',
        isParsingUrl: false,
        parsedUrl: null,  // { title, content, url }
        parsedUrlTitle: '',
        
        // Document attachment state
        attachedDocument: null,  // { filename, content }
        isUploadingDocument: false,
        
        // Plugin state
        showPlugins: false,
        pluginTab: 'market',
        marketPlugins: [],
        installedPlugins: [],
        pluginMarketLoading: false,
        pluginMarketError: false,
        pluginInstalling: null,
        pluginUploading: false,
        showPluginSettings: false,
        currentPluginSettings: null,
        pluginSettingsValues: {},
        pluginApiKeys: {},
        
        // Plugin hooks system
        pluginHooks: {
            // Document/Content processing
            parse_document: [],      // Parse uploaded documents
            web_search: [],          // Web search providers
            pre_embedding: [],       // Before embedding text
            post_retrieval: [],      // After RAG retrieval
            
            // Message lifecycle
            before_send: [],         // Before sending message to AI
            after_receive: [],       // After receiving AI response
            
            // UI extensions
            toolbar_button: [],      // Add toolbar buttons
            file_preview: [],        // Custom file preview renderers
            custom_action: [],       // Custom action handlers
            custom_settings: [],     // Custom settings UI
            
            // Content transformation
            transform_input: [],     // Transform user input
            transform_output: [],    // Transform AI output before display
        },
        loadedPluginDeps: {},
        
        // Data
        chats: [],
        messages: [],
        models: [],
        documents: [],
        settings: {
            chat_settings: {
                temperature: 0.7,
                top_p: 0.9,
                stream: true,
                system_prompt: ''
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
                theme_mode: 'light',
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
            await this.loadInstalledPlugins();
            this.applyTheme();
            // Update favicon and title based on logo settings
            this.updateFavicon(this.settings.ui_settings.logo_data);
            // Initialize plugin system
            this.initPluginSystem();
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
            // Stop any ongoing generation first
            if (this.isGenerating) {
                this.stopGeneration();
            }
            
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
        
        // Clear all chats
        async clearAllChats() {
            if (!confirm(this.t('confirmClearAll'))) return;
            
            try {
                // Delete all chats one by one
                for (const chat of this.chats) {
                    await fetch(`/api/chats/${chat.id}`, { method: 'DELETE' });
                }
                this.chats = [];
                this.currentChatId = null;
                this.messages = [];
                this.showToast(this.t('allChatsCleared'), 'success');
            } catch (e) {
                this.showToast(this.t('deleteFailed'), 'error');
            }
        },
        
        // Stop generation
        stopGeneration() {
            if (this.abortController) {
                this.abortController.abort();
                this.abortController = null;
                this.isGenerating = false;
            }
        },
        
        // Send message
        async sendMessage() {
            let message = this.inputMessage.trim();
            if (!message || this.isGenerating) return;
            
            this.inputMessage = '';
            this.isGenerating = true;
            this.abortController = new AbortController();
            
            // Call transform_input hooks to allow plugins to modify the input
            const transformResult = await this.callHook('transform_input', message);
            if (transformResult?.success && transformResult.content) {
                message = transformResult.content;
            }
            
            this.messages.push({
                role: 'user',
                content: message
            });
            this.$nextTick(() => this.scrollToBottom());
            
            try {
                // Combine web content and document content
                let combinedContent = '';
                let contentSource = '';
                
                if (this.parsedUrl) {
                    combinedContent = this.parsedUrl.content;
                    contentSource = this.parsedUrl.url;
                }
                
                if (this.attachedDocument) {
                    if (combinedContent) {
                        combinedContent += '\n\n---\n\n';
                    }
                    combinedContent += this.attachedDocument.content;
                    contentSource = contentSource ? contentSource + ', ' + this.attachedDocument.filename : this.attachedDocument.filename;
                }
                
                let body = {
                    chat_id: this.currentChatId,
                    message: message,
                    use_rag: this.useRAG,
                    use_thinking: this.useThinking,
                    image_base64: this.uploadedImageBase64,
                    web_content: combinedContent,
                    web_url: contentSource
                };
                
                // Call before_send hooks to allow plugins to modify the request
                const beforeSendResult = await this.callHook('before_send', body);
                if (beforeSendResult?.success && beforeSendResult.body) {
                    body = { ...body, ...beforeSendResult.body };
                }
                
                this.removeUploadedImage();
                this.removeParsedUrl();
                this.removeAttachedDocument();
                
                if (this.settings.chat_settings.stream) {
                    await this.handleStreamResponse(body);
                } else {
                    await this.handleNormalResponse(body);
                }
                
                // Call after_receive hooks for post-processing
                const lastMsg = this.messages[this.messages.length - 1];
                if (lastMsg && lastMsg.role === 'assistant') {
                    const afterResult = await this.callHook('after_receive', lastMsg);
                    if (afterResult?.success && afterResult.content) {
                        lastMsg.content = afterResult.content;
                        this.messages[this.messages.length - 1] = { ...lastMsg };
                    }
                }
                
                await this.loadChats();
                
            } catch (e) {
                if (e.name === 'AbortError') {
                    // User cancelled, do nothing
                } else {
                    console.error('Failed to send message:', e);
                    this.showToast(this.t('sendFailed') + ': ' + e.message, 'error');
                }
            } finally {
                this.isGenerating = false;
                this.abortController = null;
            }
        },
        
        // Handle stream response (NDJSON format) - TRUE STREAMING
        async handleStreamResponse(body) {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
                signal: this.abortController?.signal
            });
            
            if (!res.ok) {
                const errText = await res.text();
                throw new Error(errText || 'Request failed');
            }
            
            const assistantMsg = { role: 'assistant', content: '', thinking: '', references: [], showThinking: false };
            this.messages.push(assistantMsg);
            const msgIndex = this.messages.length - 1;
            
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            
            try {
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
                            
                            // Handle thinking/reasoning content
                            if (parsed.thinking) {
                                // Preserve showThinking state when updating
                                const currentShowThinking = this.messages[msgIndex]?.showThinking || false;
                                assistantMsg.thinking += parsed.thinking;
                                assistantMsg.showThinking = currentShowThinking;
                                this.messages[msgIndex] = { ...assistantMsg };
                                this.$nextTick(() => this.scrollToBottom());
                            }
                            
                            if (parsed.content) {
                                // Preserve showThinking state when updating
                                const currentShowThinking = this.messages[msgIndex]?.showThinking || false;
                                assistantMsg.content += parsed.content;
                                assistantMsg.showThinking = currentShowThinking;
                                this.messages[msgIndex] = { ...assistantMsg };
                                this.$nextTick(() => this.scrollToBottom());
                            }
                            
                            if (parsed.references) {
                                const currentShowThinking = this.messages[msgIndex]?.showThinking || false;
                                assistantMsg.references = parsed.references;
                                assistantMsg.showThinking = currentShowThinking;
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
            } catch (e) {
                if (e.name === 'AbortError') {
                    // User stopped generation, keep partial content
                    reader.cancel();
                } else {
                    throw e;
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
                thinking: data.thinking || '',
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
        
        // Check if browser supports WebP encoding
        supportsWebP() {
            const canvas = document.createElement('canvas');
            canvas.width = 1;
            canvas.height = 1;
            return canvas.toDataURL('image/webp').startsWith('data:image/webp');
        },
        
        // Compress image using Canvas API, target 500KB, max 1120px long edge
        async compressImage(file, targetSizeMB = 0.5) {
            const targetSize = targetSizeMB * 1024 * 1024; // 500KB default
            const maxLongEdge = 1120; // Maximum long edge dimension
            
            return new Promise((resolve, reject) => {
                const img = new Image();
                const url = URL.createObjectURL(file);
                
                img.onload = async () => {
                    URL.revokeObjectURL(url);
                    
                    // Detect format support
                    const useWebP = this.supportsWebP();
                    const mimeType = useWebP ? 'image/webp' : 'image/jpeg';
                    const ext = useWebP ? '.webp' : '.jpg';
                    
                    let { width, height } = img;
                    const originalWidth = width;
                    const originalHeight = height;
                    
                    // Resize to max 1120px on long edge while maintaining aspect ratio
                    const longEdge = Math.max(width, height);
                    if (longEdge > maxLongEdge) {
                        const ratio = maxLongEdge / longEdge;
                        width = Math.round(width * ratio);
                        height = Math.round(height * ratio);
                    }
                    
                    const canvas = document.createElement('canvas');
                    const ctx = canvas.getContext('2d');
                    
                    // Helper to create blob
                    const createBlob = (w, h, quality) => {
                        return new Promise((res) => {
                            canvas.width = w;
                            canvas.height = h;
                            ctx.fillStyle = '#FFFFFF';
                            ctx.fillRect(0, 0, w, h);
                            ctx.drawImage(img, 0, 0, w, h);
                            canvas.toBlob((blob) => res(blob), mimeType, quality);
                        });
                    };
                    
                    // Try compression with different quality levels until under target size
                    const qualityLevels = [0.92, 0.85, 0.75, 0.65, 0.55, 0.45, 0.35, 0.25];
                    
                    let bestBlob = null;
                    
                    // Try different quality levels with the resized dimensions
                    for (const quality of qualityLevels) {
                        const blob = await createBlob(width, height, quality);
                        if (blob && blob.size <= targetSize) {
                            bestBlob = blob;
                            break;
                        }
                        // Keep the smallest one we've seen
                        if (!bestBlob || (blob && blob.size < bestBlob.size)) {
                            bestBlob = blob;
                        }
                    }
                    
                    // If still too large, try scaling down further
                    if (bestBlob && bestBlob.size > targetSize) {
                        const scaleLevels = [0.9, 0.8, 0.7, 0.6, 0.5];
                        for (const scale of scaleLevels) {
                            const w = Math.round(width * scale);
                            const h = Math.round(height * scale);
                            
                            for (const quality of qualityLevels) {
                                const blob = await createBlob(w, h, quality);
                                if (blob && blob.size <= targetSize) {
                                    bestBlob = blob;
                                    break;
                                }
                                if (blob && blob.size < bestBlob.size) {
                                    bestBlob = blob;
                                }
                            }
                            
                            if (bestBlob && bestBlob.size <= targetSize) {
                                break;
                            }
                        }
                    }
                    
                    if (!bestBlob) {
                        reject(new Error('Compression failed'));
                        return;
                    }
                    
                    const newName = file.name.replace(/\.[^.]+$/, ext);
                    resolve(new File([bestBlob], newName, { type: mimeType }));
                };
                
                img.onerror = () => {
                    URL.revokeObjectURL(url);
                    reject(new Error('Failed to load image'));
                };
                
                img.src = url;
            });
        },
        
        // Handle image upload
        async handleImageUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            try {
                // Compress image before upload
                const compressedFile = await this.compressImage(file);
                
                const formData = new FormData();
                formData.append('file', compressedFile);
                
                const res = await fetch('/api/upload/image', {
                    method: 'POST',
                    body: formData
                });
                
                if (res.ok) {
                    const data = await res.json();
                    this.uploadedImage = file.name; // Keep original name for display
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
            const favicon = document.getElementById('favicon');
            if (dataUrl) {
                favicon.href = dataUrl;
            } else {
                // Empty favicon when no logo is set
                favicon.href = 'data:,';
            }
            document.title = this.settings.ui_settings.logo_text || 'ChatRaw';
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
        
        // Handle document upload for chat attachment
        async handleDocumentUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            this.isUploadingDocument = true;
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const res = await fetch('/api/upload/document', {
                    method: 'POST',
                    body: formData
                });
                
                if (!res.ok) {
                    const text = await res.text();
                    try {
                        const data = JSON.parse(text);
                        throw new Error(data.error || `HTTP ${res.status}`);
                    } catch {
                        throw new Error(`HTTP ${res.status}: ${text.substring(0, 100)}`);
                    }
                }
                
                const data = await res.json();
                
                if (data.success) {
                    this.attachedDocument = {
                        filename: data.filename,
                        content: data.content
                    };
                    this.showToast(this.t('documentAttached') + ': ' + data.filename, 'success');
                } else {
                    this.showToast(this.t('uploadFailed') + ': ' + (data.error || 'Unknown error'), 'error');
                }
            } catch (e) {
                console.error('Document upload error:', e);
                this.showToast(this.t('uploadFailed') + ': ' + (e.message || 'Unknown error'), 'error');
            } finally {
                this.isUploadingDocument = false;
            }
            
            event.target.value = '';
        },
        
        // Remove attached document
        removeAttachedDocument() {
            this.attachedDocument = null;
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
        },
        
        // ============ Plugin System ============
        
        // Track which plugin registered which hooks
        pluginHookRegistry: {},  // { pluginId: [{ hookName, handler }] }
        
        // Initialize plugin system
        initPluginSystem() {
            // Track current loading plugin
            this._currentLoadingPlugin = null;
            
            // Reference to app instance for closures
            const appInstance = this;

            // Create global ChatRawPlugin object for plugins
            window.ChatRawPlugin = {
                // Hook system
                hooks: {
                    register: (hookName, handler) => this.registerHook(hookName, handler),
                    // List available hooks
                    available: () => Object.keys(this.pluginHooks)
                },
                
                // Dependency loader
                require: (depName) => this.loadedPluginDeps[depName],
                
                // Proxy API for external service calls
                proxy: {
                    // JSON request proxy
                    request: (params) => this.proxyRequest(params),
                    
                    // File upload proxy (for services like Whisper, OCR)
                    upload: async (file, serviceId, url, extraFields = {}, fileFieldName = 'file') => {
                        const formData = new FormData();
                        formData.append('file', file);
                        formData.append('service_id', serviceId);
                        formData.append('url', url);
                        formData.append('extra_fields', JSON.stringify(extraFields));
                        formData.append('file_field_name', fileFieldName);
                        
                        try {
                            const res = await fetch('/api/proxy/upload', {
                                method: 'POST',
                                body: formData
                            });
                            return await res.json();
                        } catch (e) {
                            return { success: false, error: e.message };
                        }
                    }
                },
                
                // Plugin settings
                settings: (pluginId) => this.getPluginSettings(pluginId || this._currentLoadingPlugin),
                
                // Utility functions for plugin developers
                utils: {
                    // Load external script dynamically
                    loadScript: (url) => appInstance.loadScript(url),
                    
                    // Show toast notification
                    showToast: (message, type = '') => appInstance.showToast(message, type),
                    
                    // Get current language
                    getLanguage: () => appInstance.lang,
                    
                    // Translate key (if exists in i18n)
                    t: (key) => appInstance.t(key),
                    
                    // Show progress indicator (uses existing upload progress)
                    showProgress: (percent, text = '') => {
                        appInstance.uploadProgress = {
                            show: true,
                            filename: text,
                            progress: percent,
                            status: 'processing',
                            current: percent,
                            total: 100
                        };
                    },
                    
                    // Hide progress indicator
                    hideProgress: () => {
                        appInstance.uploadProgress = {
                            show: false,
                            filename: '',
                            progress: 0,
                            status: '',
                            current: 0,
                            total: 0
                        };
                    },
                    
                    // Get current chat ID
                    getCurrentChatId: () => appInstance.currentChatId,
                    
                    // Get current messages
                    getMessages: () => [...appInstance.messages],
                    
                    // Add a message to the current chat display
                    addMessage: (role, content) => {
                        appInstance.messages.push({ role, content });
                        appInstance.$nextTick(() => appInstance.scrollToBottom());
                    }
                },
                
                // Plugin local storage (namespaced by plugin ID)
                // All methods accept an optional pluginId parameter for use after plugin loading
                storage: {
                    // Get value from plugin storage
                    // Usage: ChatRaw.storage.get(key, defaultValue, pluginId)
                    get: (key, defaultValue = null, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) {
                            console.warn('[Plugin Storage] No plugin context - pass pluginId as third argument');
                            return defaultValue;
                        }
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            const data = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            return key in data ? data[key] : defaultValue;
                        } catch (e) {
                            return defaultValue;
                        }
                    },
                    
                    // Set value in plugin storage
                    // Usage: ChatRaw.storage.set(key, value, pluginId)
                    set: (key, value, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) {
                            console.warn('[Plugin Storage] No plugin context - pass pluginId as third argument');
                            return false;
                        }
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            const data = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            data[key] = value;
                            // Limit storage size per plugin (1MB)
                            const serialized = JSON.stringify(data);
                            if (serialized.length > 1024 * 1024) {
                                console.warn('[Plugin Storage] Storage limit exceeded (1MB)');
                                return false;
                            }
                            localStorage.setItem(storageKey, serialized);
                            return true;
                        } catch (e) {
                            console.error('[Plugin Storage] Error:', e);
                            return false;
                        }
                    },
                    
                    // Remove key from plugin storage
                    // Usage: ChatRaw.storage.remove(key, pluginId)
                    remove: (key, pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return false;
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            const data = JSON.parse(localStorage.getItem(storageKey) || '{}');
                            delete data[key];
                            localStorage.setItem(storageKey, JSON.stringify(data));
                            return true;
                        } catch (e) {
                            return false;
                        }
                    },
                    
                    // Clear all plugin storage
                    // Usage: ChatRaw.storage.clear(pluginId)
                    clear: (pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return false;
                        try {
                            localStorage.removeItem(`chatraw_plugin_${pid}`);
                            return true;
                        } catch (e) {
                            return false;
                        }
                    },
                    
                    // Get all plugin storage data
                    // Usage: ChatRaw.storage.getAll(pluginId)
                    getAll: (pluginId = null) => {
                        const pid = pluginId || appInstance._currentLoadingPlugin;
                        if (!pid) return {};
                        try {
                            const storageKey = `chatraw_plugin_${pid}`;
                            return JSON.parse(localStorage.getItem(storageKey) || '{}');
                        } catch (e) {
                            return {};
                        }
                    }
                }
            };

            // Load enabled plugins
            this.loadEnabledPlugins();
        },
        
        // Load installed plugins list
        async loadInstalledPlugins() {
            try {
                const res = await fetch('/api/plugins');
                if (res.ok) {
                    this.installedPlugins = await res.json();
                }
            } catch (e) {
                console.error('Failed to load installed plugins:', e);
            }
        },
        
        // Load enabled plugins' JS
        async loadEnabledPlugins() {
            for (const plugin of this.installedPlugins) {
                if (plugin.enabled) {
                    await this.loadPluginJS(plugin);
                }
            }
        },
        
        // Load a plugin's JS file
        async loadPluginJS(plugin) {
            try {
                // First load dependencies
                if (plugin.dependencies) {
                    for (const [name, url] of Object.entries(plugin.dependencies)) {
                        if (!this.loadedPluginDeps[name]) {
                            try {
                                await this.loadScript(url);
                                // Common library detection patterns
                                if (name === 'xlsx' && window.XLSX) {
                                    this.loadedPluginDeps[name] = window.XLSX;
                                } else if (name === 'pdfjs' && window.pdfjsLib) {
                                    this.loadedPluginDeps[name] = window.pdfjsLib;
                                } else if (window[name]) {
                                    this.loadedPluginDeps[name] = window[name];
                                }
                            } catch (depError) {
                                console.error(`[Plugin] Failed to load dependency ${name} for ${plugin.id}:`, depError);
                                // Continue loading other dependencies
                            }
                        }
                    }
                }
                
                // Set current loading plugin for hook registration
                this._currentLoadingPlugin = plugin.id;
                
                // Then load the plugin main.js
                const scriptUrl = `/api/plugins/${encodeURIComponent(plugin.id)}/main.js`;
                await this.loadScript(scriptUrl);
                
                this._currentLoadingPlugin = null;
                console.log(`[Plugin] Loaded: ${plugin.id}`);
            } catch (e) {
                this._currentLoadingPlugin = null;
                console.error(`[Plugin] Failed to load ${plugin.id}:`, e);
            }
        },
        
        // Load external script
        loadScript(url) {
            return new Promise((resolve, reject) => {
                // Check if already loaded
                const existing = document.querySelector(`script[src="${url}"]`);
                if (existing) {
                    resolve();
                    return;
                }
                
                const script = document.createElement('script');
                script.src = url;
                script.onload = resolve;
                script.onerror = () => reject(new Error(`Failed to load script: ${url}`));
                document.head.appendChild(script);
            });
        },
        
        // Register a hook handler
        registerHook(hookName, handler) {
            if (!this.pluginHooks[hookName]) {
                console.warn(`[Plugin] Unknown hook: ${hookName}`);
                return;
            }
            
            // Add plugin ID to handler for tracking
            const pluginId = this._currentLoadingPlugin;
            const wrappedHandler = { ...handler, _pluginId: pluginId };
            
            this.pluginHooks[hookName].push(wrappedHandler);
            this.pluginHooks[hookName].sort((a, b) => (b.priority || 0) - (a.priority || 0));
            
            // Track for later removal
            if (pluginId) {
                if (!this.pluginHookRegistry[pluginId]) {
                    this.pluginHookRegistry[pluginId] = [];
                }
                this.pluginHookRegistry[pluginId].push({ hookName, handler: wrappedHandler });
            }
        },
        
        // Unregister all hooks for a plugin
        unregisterPluginHooks(pluginId) {
            const registrations = this.pluginHookRegistry[pluginId];
            if (!registrations) return;
            
            for (const { hookName, handler } of registrations) {
                const hooks = this.pluginHooks[hookName];
                if (hooks) {
                    const idx = hooks.indexOf(handler);
                    if (idx !== -1) {
                        hooks.splice(idx, 1);
                    }
                }
            }
            
            delete this.pluginHookRegistry[pluginId];
        },
        
        // Call hook handlers
        async callHook(hookName, ...args) {
            const handlers = this.pluginHooks[hookName] || [];
            for (const handler of handlers) {
                // Skip if plugin is disabled
                if (handler._pluginId) {
                    const plugin = this.installedPlugins.find(p => p.id === handler._pluginId);
                    if (plugin && !plugin.enabled) continue;
                }
                
                try {
                    const result = await handler.handler(...args);
                    if (result?.success) return result;
                } catch (e) {
                    console.error(`[Hook ${hookName}] Error:`, e);
                }
            }
            return null;
        },
        
        // Get plugin settings with defaults
        getPluginSettings(pluginId) {
            const plugin = this.installedPlugins.find(p => p.id === pluginId);
            if (!plugin) return {};
            
            // Merge defaults with saved values
            const defaults = {};
            if (plugin.settings) {
                for (const setting of plugin.settings) {
                    defaults[setting.id] = setting.default;
                }
            }
            
            return { ...defaults, ...(plugin.settings_values || {}) };
        },
        
        // Proxy request for plugins
        async proxyRequest(params) {
            try {
                // Convert serviceId to service_id for backend compatibility
                const body = {
                    service_id: params.serviceId || params.service_id,
                    url: params.url,
                    method: params.method || 'POST',
                    headers: params.headers || {},
                    body: params.body || {}
                };
                
                const res = await fetch('/api/proxy/request', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body)
                });
                return await res.json();
            } catch (e) {
                return { success: false, error: e.message };
            }
        },
        
        // Load plugin market
        async loadPluginMarket() {
            if (this.pluginMarketLoading) return;
            
            this.pluginMarketLoading = true;
            this.pluginMarketError = false;
            
            try {
                const controller = new AbortController();
                const timeout = setTimeout(() => controller.abort(), 5000);
                
                const res = await fetch(
                    'https://raw.githubusercontent.com/massif-01/ChatRaw/main/Plugins/Plugin_market/index.json',
                    { signal: controller.signal }
                );
                clearTimeout(timeout);
                
                if (!res.ok) throw new Error('Failed to fetch');
                
                const data = await res.json();
                this.marketPlugins = data.plugins || [];
            } catch (e) {
                console.error('Failed to load plugin market:', e);
                this.pluginMarketError = true;
            } finally {
                this.pluginMarketLoading = false;
            }
        },
        
        // Check if plugin is installed
        isPluginInstalled(pluginId) {
            return this.installedPlugins.some(p => p.id === pluginId);
        },
        
        // Install plugin from market
        async installPlugin(plugin) {
            this.pluginInstalling = plugin.id;
            
            try {
                const sourceUrl = `https://raw.githubusercontent.com/massif-01/ChatRaw/main/Plugins/Plugin_market/${plugin.folder}`;
                
                const res = await fetch('/api/plugins/install', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_url: sourceUrl })
                });
                
                const data = await res.json();
                
                if (data.success) {
                    this.showToast(this.t('installSuccess'), 'success');
                    await this.loadInstalledPlugins();
                    // Load the newly installed plugin
                    const newPlugin = this.installedPlugins.find(p => p.id === plugin.id);
                    if (newPlugin) {
                        await this.loadPluginJS(newPlugin);
                    }
                } else {
                    this.showToast(this.t('installFailed') + ': ' + data.error, 'error');
                }
            } catch (e) {
                this.showToast(this.t('installFailed') + ': ' + e.message, 'error');
            } finally {
                this.pluginInstalling = null;
            }
        },
        
        // Handle local plugin upload
        async handlePluginUpload(event) {
            const file = event.target.files[0];
            if (!file) return;
            
            if (!file.name.endsWith('.zip')) {
                this.showToast(this.t('onlyZipSupported'), 'error');
                return;
            }
            
            this.pluginUploading = true;
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const res = await fetch('/api/plugins/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await res.json();
                
                if (data.success) {
                    this.showToast(this.t('installSuccess'), 'success');
                    await this.loadInstalledPlugins();
                    // Load the newly installed plugin
                    const newPlugin = this.installedPlugins.find(p => p.id === data.plugin_id);
                    if (newPlugin) {
                        await this.loadPluginJS(newPlugin);
                    }
                } else {
                    this.showToast(this.t('installFailed') + ': ' + data.error, 'error');
                }
            } catch (e) {
                this.showToast(this.t('installFailed') + ': ' + e.message, 'error');
            } finally {
                this.pluginUploading = false;
                event.target.value = '';
            }
        },
        
        // Toggle plugin enabled/disabled
        async togglePlugin(plugin) {
            const newState = !plugin.enabled;
            
            try {
                const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}/toggle`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: newState })
                });
                
                if (res.ok) {
                    plugin.enabled = newState;
                    if (newState) {
                        // Load plugin if enabled
                        await this.loadPluginJS(plugin);
                        this.showToast(this.t('settingsSaved'), 'success');
                    } else {
                        // Unregister hooks when disabled
                        this.unregisterPluginHooks(plugin.id);
                        this.showToast(this.t('pluginDisabled'), 'success');
                    }
                }
            } catch (e) {
                this.showToast(this.t('saveFailed'), 'error');
            }
        },
        
        // Open plugin settings
        async openPluginSettings(plugin) {
            this.currentPluginSettings = plugin;
            
            // Initialize settings with defaults, then override with saved values
            const settingsValues = {};
            if (plugin.settings) {
                for (const setting of plugin.settings) {
                    settingsValues[setting.id] = setting.default;
                }
            }
            // Override with saved values
            Object.assign(settingsValues, plugin.settings_values || {});
            
            this.pluginSettingsValues = settingsValues;
            this.pluginApiKeys = {};
            
            // Load saved API keys (masked) for display
            if (plugin.proxy && plugin.proxy.length > 0) {
                try {
                    const res = await fetch('/api/plugins/api-keys');
                    if (res.ok) {
                        const data = await res.json();
                        const savedKeys = data.api_keys || {};
                        for (const proxy of plugin.proxy) {
                            if (savedKeys[proxy.id]) {
                                this.pluginApiKeys[proxy.id] = savedKeys[proxy.id];
                            }
                        }
                    }
                } catch (e) {
                    console.error('Failed to load API keys:', e);
                }
            }
            
            this.showPluginSettings = true;
            
            // Dispatch event for plugins with custom settings to inject their UI
            if (plugin.customSettings) {
                setTimeout(() => {
                    window.dispatchEvent(new CustomEvent('plugin-settings-open', {
                        detail: { pluginId: plugin.id, customSettings: true }
                    }));
                }, 50);
            }
        },
        
        // Save plugin settings
        async savePluginSettings() {
            if (!this.currentPluginSettings) return;
            
            try {
                // Save settings
                const settingsRes = await fetch(`/api/plugins/${encodeURIComponent(this.currentPluginSettings.id)}/settings`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ settings: this.pluginSettingsValues })
                });
                
                if (!settingsRes.ok) {
                    throw new Error('Failed to save settings');
                }
                
                // Save API keys (only if user entered a new value, not the masked placeholder)
                for (const [serviceId, apiKey] of Object.entries(this.pluginApiKeys)) {
                    // Skip masked values (contain *) - user didn't change the key
                    if (apiKey && !apiKey.includes('*')) {
                        await fetch('/api/plugins/api-key', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ service_id: serviceId, api_key: apiKey })
                        });
                    }
                }
                
                // Update local state
                const plugin = this.installedPlugins.find(p => p.id === this.currentPluginSettings.id);
                if (plugin) {
                    plugin.settings_values = { ...this.pluginSettingsValues };
                }
                
                this.showPluginSettings = false;
                this.showToast(this.t('settingsSaved'), 'success');
            } catch (e) {
                this.showToast(this.t('saveFailed'), 'error');
            }
        },
        
        // Uninstall plugin
        async uninstallPlugin(plugin) {
            if (!plugin || !confirm(this.t('confirmUninstall'))) return;
            
            try {
                // First unregister hooks
                this.unregisterPluginHooks(plugin.id);
                
                const res = await fetch(`/api/plugins/${encodeURIComponent(plugin.id)}`, {
                    method: 'DELETE'
                });
                
                if (res.ok) {
                    this.showPluginSettings = false;
                    this.currentPluginSettings = null;
                    this.showToast(this.t('uninstallSuccess'), 'success');
                    await this.loadInstalledPlugins();
                } else {
                    const data = await res.json().catch(() => ({}));
                    this.showToast(this.t('uninstallFailed') + (data.error ? ': ' + data.error : ''), 'error');
                }
            } catch (e) {
                this.showToast(this.t('uninstallFailed'), 'error');
            }
        }
    };
}
