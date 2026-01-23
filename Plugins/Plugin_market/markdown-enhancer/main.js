/**
 * Markdown Renderer Plus - Enhanced Markdown rendering for ChatRaw
 * 
 * Features:
 * - KaTeX math formulas ($...$ and $$...$$)
 * - Mermaid diagrams (```mermaid code blocks)
 * - Code block copy buttons
 * - Message copy button (copy entire AI response)
 * - Extended syntax highlighting (15+ languages)
 * 
 * Architecture: DOM post-processing via MutationObserver
 * (processes content AFTER marked.js renders it)
 * 
 * Fully offline - all dependencies bundled locally.
 */
(function(ChatRawPlugin) {
    'use strict';
    
    const PLUGIN_ID = 'markdown-enhancer';
    const LIB_BASE = `/api/plugins/${PLUGIN_ID}/lib`;
    
    // ============ State ============
    let katexLoaded = false;
    let mermaidLoaded = false;
    let extraLangsLoaded = false;
    let observerInitialized = false;
    let mermaidCounter = 0;
    let settings = {};
    
    // ============ i18n ============
    const i18n = {
        en: {
            copied: 'Copied!',
            copyFailed: 'Copy failed',
            copy: 'Copy',
            copyMessage: 'Copy message',
            renderError: 'Render error',
            loading: 'Loading...'
        },
        zh: {
            copied: '已复制！',
            copyFailed: '复制失败',
            copy: '复制',
            copyMessage: '复制消息',
            renderError: '渲染错误',
            loading: '加载中...'
        }
    };
    
    function t(key) {
        const lang = ChatRawPlugin?.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }
    
    // ============ CSS Loader ============
    function loadCSS(url) {
        return new Promise((resolve, reject) => {
            const existing = document.querySelector(`link[href="${url}"]`);
            if (existing) {
                resolve();
                return;
            }
            
            const link = document.createElement('link');
            link.rel = 'stylesheet';
            link.href = url;
            link.onload = resolve;
            link.onerror = () => reject(new Error(`Failed to load CSS: ${url}`));
            document.head.appendChild(link);
        });
    }
    
    // ============ Script Loader ============
    function loadScript(url) {
        return new Promise((resolve, reject) => {
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
    }
    
    // ============ Initialize Dependencies ============
    async function initKatex() {
        if (katexLoaded) return true;
        
        try {
            await loadCSS(`${LIB_BASE}/katex.min.css`);
            await loadScript(`${LIB_BASE}/katex.min.js`);
            
            if (window.katex) {
                katexLoaded = true;
                console.log('[MarkdownEnhancer] KaTeX loaded');
                return true;
            }
        } catch (e) {
            console.error('[MarkdownEnhancer] Failed to load KaTeX:', e);
        }
        return false;
    }
    
    async function initMermaid(theme = 'default') {
        if (mermaidLoaded) return true;
        
        try {
            await loadScript(`${LIB_BASE}/mermaid.min.js`);
            
            if (window.mermaid) {
                // Initialize mermaid with strict security to avoid affecting other elements
                window.mermaid.initialize({
                    startOnLoad: false,
                    theme: theme === 'dark' ? 'dark' : theme,
                    securityLevel: 'strict',  // Changed from 'loose' to prevent side effects
                    fontFamily: 'inherit'
                });
                mermaidLoaded = true;
                console.log('[MarkdownEnhancer] Mermaid loaded');
                return true;
            }
        } catch (e) {
            console.error('[MarkdownEnhancer] Failed to load Mermaid:', e);
        }
        return false;
    }
    
    async function initExtraLanguages() {
        if (extraLangsLoaded || !window.hljs) return;
        
        const languages = [
            'typescript', 'go', 'rust', 'java', 'c', 'cpp', 'csharp',
            'ruby', 'php', 'swift', 'kotlin', 'sql', 'yaml', 'xml', 'shell'
        ];
        
        try {
            for (const lang of languages) {
                try {
                    await loadScript(`${LIB_BASE}/hljs-${lang}.min.js`);
                } catch (e) {
                    // Ignore individual language load failures
                }
            }
            extraLangsLoaded = true;
            console.log('[MarkdownEnhancer] Extra languages loaded');
        } catch (e) {
            console.error('[MarkdownEnhancer] Failed to load extra languages:', e);
        }
    }
    
    // ============ Inject Styles ============
    function injectStyles() {
        const styleId = 'markdown-enhancer-styles';
        if (document.getElementById(styleId)) return;
        
        const style = document.createElement('style');
        style.id = styleId;
        style.textContent = `
            /* Code copy button */
            .message-content pre {
                position: relative;
            }
            .code-copy-btn {
                position: absolute;
                top: 8px;
                right: 8px;
                padding: 4px 8px;
                font-size: 12px;
                background: var(--bg-tertiary, #e5e5e5);
                color: var(--text-secondary, #666);
                border: 1px solid var(--border-color, #ddd);
                border-radius: 4px;
                cursor: pointer;
                opacity: 0;
                transition: opacity 0.2s, background 0.2s;
                z-index: 10;
            }
            .message-content pre:hover .code-copy-btn {
                opacity: 1;
            }
            .code-copy-btn:hover {
                background: var(--bg-hover, #d5d5d5);
            }
            .code-copy-btn.copied {
                background: var(--success-color, #10b981);
                color: white;
                border-color: var(--success-color, #10b981);
            }
            
            /* Message copy button */
            .message.assistant {
                position: relative;
            }
            .message-copy-btn {
                position: absolute;
                top: 8px;
                right: 8px;
                padding: 6px;
                background: var(--bg-secondary, #f5f5f5);
                color: var(--text-secondary, #666);
                border: 1px solid var(--border-color, #ddd);
                border-radius: 6px;
                cursor: pointer;
                opacity: 0;
                transition: opacity 0.2s, background 0.2s;
                z-index: 10;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .message.assistant:hover .message-copy-btn {
                opacity: 1;
            }
            .message-copy-btn:hover {
                background: var(--bg-hover, #e5e5e5);
            }
            .message-copy-btn.copied {
                background: var(--success-color, #10b981);
                color: white;
                border-color: var(--success-color, #10b981);
            }
            .message-copy-btn svg {
                width: 16px;
                height: 16px;
            }
            
            /* KaTeX styles */
            .katex-block {
                display: block;
                text-align: center;
                margin: 1em 0;
                overflow-x: auto;
                padding: 0.5em 0;
            }
            .katex-inline {
                display: inline;
            }
            .katex-error {
                color: var(--error-color, #ef4444);
                background: rgba(239, 68, 68, 0.1);
                padding: 2px 4px;
                border-radius: 2px;
                font-family: monospace;
                font-size: 0.9em;
            }
            
            /* Mermaid styles */
            .mermaid-container {
                display: flex;
                justify-content: center;
                margin: 1em 0;
                padding: 1em;
                background: var(--bg-secondary, #f5f5f5);
                border-radius: 8px;
                overflow-x: auto;
            }
            .mermaid-loading {
                min-height: 100px;
                align-items: center;
            }
            .mermaid-loading-text {
                color: var(--text-secondary, #666);
                font-style: italic;
            }
            .mermaid-error-container {
                color: var(--error-color, #ef4444);
                background: rgba(239, 68, 68, 0.1);
                padding: 1em;
                border-radius: 8px;
            }
            .mermaid-error-container pre {
                margin-top: 8px;
                font-size: 12px;
                white-space: pre-wrap;
                background: transparent;
                border: none;
                padding: 0;
            }
            .mermaid-rendered svg {
                max-width: 100%;
                height: auto;
            }
        `;
        document.head.appendChild(style);
    }
    
    // ============ KaTeX DOM Processing ============
    function processKatexInElement(element) {
        if (!window.katex || settings.enableKatex === false) return;
        
        // Process text nodes to find math expressions
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: (node) => {
                    // Skip if inside code, pre, script, style, or already processed
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    const tagName = parent.tagName?.toLowerCase();
                    if (['code', 'pre', 'script', 'style', 'textarea', 'input'].includes(tagName)) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    if (parent.classList?.contains('katex') || parent.closest('.katex')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    // Check if contains math delimiters
                    if (/\$\$[\s\S]+?\$\$|\$[^\$\n]+?\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)/.test(node.textContent)) {
                        return NodeFilter.FILTER_ACCEPT;
                    }
                    return NodeFilter.FILTER_REJECT;
                }
            }
        );
        
        const nodesToProcess = [];
        let currentNode;
        while ((currentNode = walker.nextNode())) {
            nodesToProcess.push(currentNode);
        }
        
        for (const textNode of nodesToProcess) {
            processKatexTextNode(textNode);
        }
    }
    
    function processKatexTextNode(textNode) {
        const text = textNode.textContent;
        if (!text) return;
        
        // Combined regex for all math patterns
        const mathRegex = /(\$\$[\s\S]+?\$\$|\$[^\$\n]+?\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\))/g;
        
        const parts = text.split(mathRegex);
        if (parts.length <= 1) return;
        
        const fragment = document.createDocumentFragment();
        
        for (const part of parts) {
            if (!part) continue;
            
            // Check if this part is a math expression
            const blockMatch = part.match(/^\$\$([\s\S]+?)\$\$$/) || part.match(/^\\\[([\s\S]+?)\\\]$/);
            const inlineMatch = part.match(/^\$([^\$\n]+?)\$$/) || part.match(/^\\\(([\s\S]+?)\\\)$/);
            
            if (blockMatch) {
                const formula = blockMatch[1].trim();
                try {
                    const container = document.createElement('div');
                    container.className = 'katex-block';
                    container.innerHTML = window.katex.renderToString(formula, {
                        displayMode: true,
                        throwOnError: false,
                        output: 'html'
                    });
                    fragment.appendChild(container);
                } catch (e) {
                    const errorSpan = document.createElement('div');
                    errorSpan.className = 'katex-error';
                    errorSpan.textContent = part;
                    fragment.appendChild(errorSpan);
                }
            } else if (inlineMatch) {
                const formula = inlineMatch[1].trim();
                // Skip currency-like patterns
                if (/^\d+(\.\d+)?$/.test(formula)) {
                    fragment.appendChild(document.createTextNode(part));
                    continue;
                }
                try {
                    const container = document.createElement('span');
                    container.className = 'katex-inline';
                    container.innerHTML = window.katex.renderToString(formula, {
                        displayMode: false,
                        throwOnError: false,
                        output: 'html'
                    });
                    fragment.appendChild(container);
                } catch (e) {
                    const errorSpan = document.createElement('span');
                    errorSpan.className = 'katex-error';
                    errorSpan.textContent = part;
                    fragment.appendChild(errorSpan);
                }
            } else {
                fragment.appendChild(document.createTextNode(part));
            }
        }
        
        textNode.parentNode.replaceChild(fragment, textNode);
    }
    
    // ============ Mermaid DOM Processing ============
    async function processMermaidInElement(element) {
        if (!window.mermaid || settings.enableMermaid === false) return;
        
        // Find mermaid code blocks
        const mermaidBlocks = element.querySelectorAll('pre > code.language-mermaid, pre > code.hljs.language-mermaid');
        
        for (const codeBlock of mermaidBlocks) {
            const pre = codeBlock.parentElement;
            if (!pre || pre.dataset.mermaidProcessed) continue;
            
            pre.dataset.mermaidProcessed = 'true';
            
            const code = codeBlock.textContent.trim();
            const id = `mermaid-${Date.now()}-${mermaidCounter++}`;
            
            // Create container
            const container = document.createElement('div');
            container.id = id;
            container.className = 'mermaid-container mermaid-loading';
            container.innerHTML = `<div class="mermaid-loading-text">${t('loading')}</div>`;
            
            // Replace pre with container
            pre.parentNode.replaceChild(container, pre);
            
            // Render asynchronously
            try {
                const { svg } = await window.mermaid.render(`${id}-svg`, code);
                container.innerHTML = svg;
                container.classList.remove('mermaid-loading');
                container.classList.add('mermaid-rendered');
            } catch (e) {
                console.error('[MarkdownEnhancer] Mermaid render error:', e);
                container.className = 'mermaid-error-container';
                container.innerHTML = `
                    <strong>${t('renderError')}:</strong> ${e.message || 'Unknown error'}
                    <pre>${code}</pre>
                `;
            }
        }
    }
    
    // ============ Code Copy Buttons ============
    function addCodeCopyButtons(element) {
        if (settings.enableCopyButton === false) return;
        
        const codeBlocks = element.querySelectorAll('.message-content pre');
        
        for (const pre of codeBlocks) {
            if (pre.querySelector('.code-copy-btn')) continue;
            if (pre.dataset.mermaidProcessed) continue;  // Skip mermaid blocks
            
            const code = pre.querySelector('code');
            if (!code) continue;
            
            const btn = document.createElement('button');
            btn.className = 'code-copy-btn';
            btn.textContent = t('copy');
            btn.onclick = async (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                try {
                    await navigator.clipboard.writeText(code.textContent);
                    btn.textContent = t('copied');
                    btn.classList.add('copied');
                    setTimeout(() => {
                        btn.textContent = t('copy');
                        btn.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('[MarkdownEnhancer] Copy failed:', err);
                    btn.textContent = t('copyFailed');
                    setTimeout(() => {
                        btn.textContent = t('copy');
                    }, 2000);
                }
            };
            
            pre.appendChild(btn);
        }
    }
    
    // ============ Message Copy Button ============
    function addMessageCopyButton(element) {
        // Find assistant messages
        const messages = element.querySelectorAll('.message.assistant');
        
        for (const msg of messages) {
            if (msg.querySelector('.message-copy-btn')) continue;
            
            const content = msg.querySelector('.message-content');
            if (!content) continue;
            
            const btn = document.createElement('button');
            btn.className = 'message-copy-btn';
            btn.title = t('copyMessage');
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
            `;
            
            btn.onclick = async (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                // Get the original markdown content from the message
                // We need to extract text content, preserving structure
                const textContent = getMessageTextContent(content);
                
                try {
                    await navigator.clipboard.writeText(textContent);
                    btn.innerHTML = `
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    `;
                    btn.classList.add('copied');
                    setTimeout(() => {
                        btn.innerHTML = `
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                            </svg>
                        `;
                        btn.classList.remove('copied');
                    }, 2000);
                } catch (err) {
                    console.error('[MarkdownEnhancer] Message copy failed:', err);
                }
            };
            
            msg.appendChild(btn);
        }
    }
    
    function getMessageTextContent(element) {
        // Clone to avoid modifying original
        const clone = element.cloneNode(true);
        
        // Remove copy buttons from clone
        clone.querySelectorAll('.code-copy-btn, .message-copy-btn').forEach(btn => btn.remove());
        
        // Convert KaTeX back to text (approximate)
        clone.querySelectorAll('.katex-block').forEach(el => {
            const annotation = el.querySelector('annotation[encoding="application/x-tex"]');
            if (annotation) {
                el.textContent = '$$' + annotation.textContent + '$$';
            }
        });
        clone.querySelectorAll('.katex-inline').forEach(el => {
            const annotation = el.querySelector('annotation[encoding="application/x-tex"]');
            if (annotation) {
                el.textContent = '$' + annotation.textContent + '$';
            }
        });
        
        // Get text content
        return clone.textContent || clone.innerText || '';
    }
    
    // ============ Main Processing Function ============
    async function processElement(element) {
        // Load dependencies if needed
        if (settings.enableKatex !== false) {
            await initKatex();
        }
        if (settings.enableMermaid !== false) {
            const theme = settings.mermaidTheme || 'default';
            await initMermaid(theme);
        }
        if (settings.enableExtraLanguages !== false) {
            await initExtraLanguages();
        }
        
        // Process in order: Mermaid first (replaces pre blocks), then KaTeX, then copy buttons
        await processMermaidInElement(element);
        processKatexInElement(element);
        addCodeCopyButtons(element);
        addMessageCopyButton(element);
    }
    
    // ============ MutationObserver Setup ============
    function initObserver() {
        if (observerInitialized) return;
        
        injectStyles();
        
        // Debounce processing to avoid excessive calls
        let processingTimeout = null;
        const pendingElements = new Set();
        
        const processQueue = async () => {
            const elements = Array.from(pendingElements);
            pendingElements.clear();
            
            for (const el of elements) {
                await processElement(el);
            }
        };
        
        const observer = new MutationObserver((mutations) => {
            for (const mutation of mutations) {
                for (const node of mutation.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if it's a message or contains messages
                        if (node.classList?.contains('message') || 
                            node.classList?.contains('message-content') ||
                            node.querySelector?.('.message-content')) {
                            pendingElements.add(node);
                        }
                    }
                }
            }
            
            if (pendingElements.size > 0) {
                clearTimeout(processingTimeout);
                processingTimeout = setTimeout(processQueue, 100);
            }
        });
        
        // Start observing
        const container = document.querySelector('.messages-container') || document.body;
        observer.observe(container, {
            childList: true,
            subtree: true
        });
        
        // Process existing content
        const existingMessages = document.querySelectorAll('.message-content');
        if (existingMessages.length > 0) {
            for (const msg of existingMessages) {
                pendingElements.add(msg);
            }
            processQueue();
        }
        
        observerInitialized = true;
        console.log('[MarkdownEnhancer] Observer initialized');
    }
    
    // ============ Load Settings ============
    async function loadSettings() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const plugin = plugins.find(p => p.id === PLUGIN_ID);
                if (plugin?.settings_values) {
                    settings = plugin.settings_values;
                }
            }
        } catch (e) {
            console.error('[MarkdownEnhancer] Failed to load settings:', e);
        }
    }
    
    // ============ Initialize ============
    async function init() {
        await loadSettings();
        initObserver();
        console.log('[MarkdownEnhancer] Plugin initialized');
    }
    
    // Start initialization when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})(window.ChatRawPlugin);
