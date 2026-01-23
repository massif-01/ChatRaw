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
 * - Waits for content to stabilize before processing (handles streaming)
 * - Mermaid SVG styles are isolated to prevent CSS pollution
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
    let pluginEnabled = true;
    let mainObserver = null;
    let headStyleObserver = null;
    let pluginStateTimer = null;
    
    // Content stability tracking - wait for streaming to complete
    const contentStabilityMap = new Map();
    const STABILITY_DELAY = 800; // Wait 800ms after last change before processing
    
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
                // Initialize mermaid with sandbox mode for style isolation
                window.mermaid.initialize({
                    startOnLoad: false,
                    theme: theme === 'dark' ? 'dark' : theme,
                    // Use sandbox for maximum isolation (iframe-based rendering)
                    securityLevel: 'sandbox',
                    fontFamily: 'inherit',
                    // Disable flowchart htmlLabels to prevent CSS issues
                    flowchart: {
                        htmlLabels: false,
                        useMaxWidth: true
                    }
                });
                // Mermaid may inject global <style> into <head>. We'll relocate new Mermaid styles
                // into Shadow DOM per-render, but also remove any existing Mermaid global styles now.
                try {
                    removeMermaidHeadStyles();
                } catch (_) {
                    // ignore
                }
                mermaidLoaded = true;
                console.log('[MarkdownEnhancer] Mermaid loaded');
                return true;
            }
        } catch (e) {
            console.error('[MarkdownEnhancer] Failed to load Mermaid:', e);
        }
        return false;
    }

    function removeMermaidHeadStyles() {
        const headStyles = Array.from(document.head.querySelectorAll('style'));
        for (const styleEl of headStyles) {
            const id = (styleEl.id || '').toLowerCase();
            const css = styleEl.textContent || '';
            if (id.includes('mermaid') || css.includes('mermaid') || css.includes('.mermaid')) {
                styleEl.remove();
            }
        }
    }

    function cleanupPluginArtifacts() {
        // Remove plugin-injected styles
        const styleEl = document.getElementById('markdown-enhancer-styles');
        if (styleEl) styleEl.remove();
        // Remove copy buttons
        document.querySelectorAll('.message-copy-container').forEach(el => el.remove());
        document.querySelectorAll('.code-copy-btn').forEach(el => el.remove());
        // Remove Mermaid global styles if any
        removeMermaidHeadStyles();
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
            
            /* Message copy button - small icon at bottom left */
            .message-copy-container {
                display: flex;
                justify-content: flex-start;
                margin-top: 8px;
            }
            .message-copy-btn {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                width: 28px;
                height: 28px;
                padding: 0;
                background: transparent;
                color: var(--text-tertiary, #999);
                border: none;
                border-radius: 4px;
                cursor: pointer;
                transition: background 0.2s, color 0.2s;
            }
            .message-copy-btn:hover {
                background: var(--bg-hover, #f0f0f0);
                color: var(--text-secondary, #666);
            }
            .message-copy-btn.copied {
                color: var(--success-color, #10b981);
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
            
            /* Mermaid styles - isolated container */
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
            /* Prevent mermaid SVG from affecting global styles */
            .mermaid-rendered svg * {
                font-family: inherit !important;
            }
        `;
        document.head.appendChild(style);
    }
    
    // ============ KaTeX DOM Processing ============
    function processKatexInElement(element) {
        if (!window.katex || settings.enableKatex === false) return;
        
        // Don't skip based on katexProcessed - content may have changed during streaming
        // Instead, rely on the walker to only find unprocessed text nodes
        
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
                    if (parent.closest('.mermaid-container')) {
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
                // Mermaid may inject global styles into document.head during render(). Capture and relocate them.
                const headStylesBefore = new Set(Array.from(document.head.querySelectorAll('style')));
                const { svg } = await window.mermaid.render(`${id}-svg`, code);
                const newHeadStyles = Array.from(document.head.querySelectorAll('style'))
                    .filter(el => !headStylesBefore.has(el));

                let relocatedCss = '';
                for (const styleEl of newHeadStyles) {
                    const id = (styleEl.id || '').toLowerCase();
                    const css = styleEl.textContent || '';
                    if (id.includes('mermaid') || css.includes('mermaid') || css.includes('.mermaid')) {
                        relocatedCss += `\n/* relocated from <head> */\n${css}\n`;
                        styleEl.remove();
                    }
                }

                container.innerHTML = '';
                container.classList.remove('mermaid-loading');
                container.classList.add('mermaid-rendered');
                
                // Use Shadow DOM to completely isolate Mermaid SVG styles
                // This prevents any CSS pollution to the main document
                const shadowHost = document.createElement('div');
                shadowHost.className = 'mermaid-shadow-host';
                shadowHost.style.cssText = 'display: flex; justify-content: center; width: 100%;';
                const shadow = shadowHost.attachShadow({ mode: 'closed' });
                shadow.innerHTML = `${relocatedCss ? `<style>${relocatedCss}</style>` : ''}${svg}`;
                container.appendChild(shadowHost);
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
            if (pre.closest('.mermaid-container')) continue;
            
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
    // Track elements that need copy button recheck when streaming ends
    const pendingCopyButtonChecks = new WeakSet();
    
    function addMessageCopyButton(element) {
        // Normalize targets for message-content elements
        const targets = [];
        if (element?.classList?.contains('message-content')) {
            targets.push(element);
        } else if (element?.classList?.contains('message')) {
            const content = element.querySelector('.message-content');
            if (content) targets.push(content);
        } else {
            element.querySelectorAll?.('.message.assistant .message-content').forEach(el => targets.push(el));
        }
        
        for (const content of targets) {
            const msg = content.closest('.message');
            if (!msg || !msg.classList.contains('assistant')) continue;
            // Skip if already has copy button
            if (content.querySelector('.message-copy-container')) continue;
            
            // Check if message is still streaming (has typing indicator visible)
            // Alpine.js x-show sets display: none when hidden
            const typingIndicator = msg?.querySelector('.typing-indicator');
            if (typingIndicator) {
                const computedStyle = window.getComputedStyle(typingIndicator);
                if (computedStyle.display !== 'none') {
                    // Typing indicator is visible, message is still streaming
                    // Schedule a recheck for later
                    if (!pendingCopyButtonChecks.has(content)) {
                        pendingCopyButtonChecks.add(content);
                        setTimeout(() => {
                            pendingCopyButtonChecks.delete(content);
                            addMessageCopyButton(content);
                        }, 1000);
                    }
                    continue;
                }
            }
            
            // Check if content is empty or very short (likely still loading)
            const textLength = content.textContent?.trim().length || 0;
            if (textLength < 10) continue;
            
            // Create container at bottom left of message
            const container = document.createElement('div');
            container.className = 'message-copy-container';
            
            const btn = document.createElement('button');
            btn.className = 'message-copy-btn';
            btn.title = t('copyMessage');
            btn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                </svg>
            `;
            
            btn.onclick = async (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                // Get the text content from the message
                const textContent = getMessageTextContent(content);
                
                try {
                    await navigator.clipboard.writeText(textContent);
                    btn.innerHTML = `
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                    `;
                    btn.classList.add('copied');
                    setTimeout(() => {
                        btn.innerHTML = `
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
            
            container.appendChild(btn);
            content.appendChild(container);
        }
    }
    
    function getMessageTextContent(element) {
        // Clone to avoid modifying original
        const clone = element.cloneNode(true);
        
        // Remove all non-content elements
        clone.querySelectorAll([
            '.code-copy-btn',
            '.message-copy-btn', 
            '.message-copy-container',
            '.thinking-block',      // Thinking process section
            '.thinking-header',
            '.thinking-content',
            '.rag-references',      // RAG references section
            '.rag-references-header',
            '.rag-references-list',
            '.typing-indicator',    // Typing indicator
            '.mermaid-container',   // Mermaid diagrams (keep code representation)
            'svg'                   // Remove SVG icons
        ].join(', ')).forEach(el => el.remove());
        
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
        
        // Get text content and clean up whitespace
        let text = clone.textContent || clone.innerText || '';
        // Collapse multiple newlines/spaces into single ones
        text = text.replace(/\n{3,}/g, '\n\n').trim();
        return text;
    }
    
    // ============ Main Processing Function ============
    async function processElement(element) {
        if (!pluginEnabled) return;
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
    
    // ============ Content Stability Detection ============
    function scheduleProcessing(element) {
        if (!pluginEnabled) return;
        // Use element or a unique identifier as key
        const key = element;
        
        // Clear any existing timer for this element
        const existingTimer = contentStabilityMap.get(key);
        if (existingTimer) {
            clearTimeout(existingTimer);
        }
        
        // Schedule new processing after stability delay
        const timer = setTimeout(async () => {
            contentStabilityMap.delete(key);
            await processElement(element);
        }, STABILITY_DELAY);
        
        contentStabilityMap.set(key, timer);
    }
    
    // ============ MutationObserver Setup ============
    function initObserver() {
        if (observerInitialized || !pluginEnabled) return;
        
        injectStyles();
        
        const observer = new MutationObserver((mutations) => {
            const elementsToProcess = new Set();
            
            for (const mutation of mutations) {
                // Handle added nodes
                for (const node of mutation.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if it's a message or contains messages
                        if (node.classList?.contains('message')) {
                            const content = node.querySelector('.message-content');
                            if (content) elementsToProcess.add(content);
                        } else if (node.classList?.contains('message-content')) {
                            elementsToProcess.add(node);
                        } else if (node.querySelector?.('.message-content')) {
                            node.querySelectorAll('.message-content').forEach(el => elementsToProcess.add(el));
                        }
                    }
                }
                
                // Handle character data changes (streaming content updates)
                if (mutation.type === 'characterData' || mutation.type === 'childList') {
                    // mutation.target can be a Text node (no .closest). Normalize to an Element first.
                    const targetEl = mutation.target?.nodeType === Node.TEXT_NODE
                        ? mutation.target.parentElement
                        : mutation.target;
                    const messageContent = targetEl?.closest?.('.message-content');
                    if (messageContent) {
                        elementsToProcess.add(messageContent);
                    }
                }
            }
            
            // Schedule processing for each element with stability detection
            for (const el of elementsToProcess) {
                scheduleProcessing(el);
            }
        });
        
        // Start observing - note: ChatRaw uses class "messages" not "messages-container"
        const container = document.querySelector('.messages') || document.querySelector('.messages-container') || document.body;
        observer.observe(container, {
            childList: true,
            subtree: true,
            characterData: true
        });
        
        // Process existing content
        const existingMessages = document.querySelectorAll('.message-content');
        if (existingMessages.length > 0) {
            for (const msg of existingMessages) {
                scheduleProcessing(msg);
            }
        }
        
        // Also ensure copy buttons are added to existing completed messages
        setTimeout(() => {
            document.querySelectorAll('.message.assistant .message-content').forEach(content => {
                if (!content.querySelector('.message-copy-container')) {
                    addMessageCopyButton(content);
                }
            });
        }, 1500);
        
        mainObserver = observer;
        observerInitialized = true;
        console.log('[MarkdownEnhancer] Observer initialized with content stability detection');
    }

    function stopObserver() {
        if (mainObserver) {
            mainObserver.disconnect();
            mainObserver = null;
        }
        observerInitialized = false;
    }

    function initHeadStyleGuard() {
        if (headStyleObserver) return;
        headStyleObserver = new MutationObserver(() => {
            removeMermaidHeadStyles();
        });
        headStyleObserver.observe(document.head, { childList: true, subtree: true });
    }

    async function refreshPluginState() {
        try {
            const res = await fetch('/api/plugins');
            if (!res.ok) return;
            const plugins = await res.json();
            const plugin = plugins.find(p => p.id === PLUGIN_ID);
            const enabled = plugin?.enabled !== false;
            if (enabled !== pluginEnabled) {
                pluginEnabled = enabled;
                if (!pluginEnabled) {
                    stopObserver();
                    cleanupPluginArtifacts();
                } else {
                    injectStyles();
                    initObserver();
                }
            }
        } catch (e) {
            // ignore transient errors
        }
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
                pluginEnabled = plugin?.enabled !== false;
            }
        } catch (e) {
            console.error('[MarkdownEnhancer] Failed to load settings:', e);
        }
    }
    
    // ============ Initialize ============
    async function init() {
        await loadSettings();
        initHeadStyleGuard();
        if (pluginEnabled) {
            initObserver();
        } else {
            cleanupPluginArtifacts();
        }
        // Periodically refresh plugin enabled state to handle toggles
        if (!pluginStateTimer) {
            pluginStateTimer = setInterval(refreshPluginState, 2000);
        }
        console.log('[MarkdownEnhancer] Plugin initialized');
    }
    
    // Start initialization when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})(window.ChatRawPlugin);
