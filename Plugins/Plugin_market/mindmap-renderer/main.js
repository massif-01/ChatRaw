/**
 * Mindmap Renderer - Parse structured content and render as interactive mind maps
 *
 * Features:
 * - after_receive: detect Markdown, JSON (title/children), markmap blocks
 * - MutationObserver: render ```markmap blocks with Markmap
 * - Shadow DOM style isolation
 *
 * Fully offline - Markmap bundled in lib/
 */
(function(ChatRawPlugin) {
    'use strict';

    const PLUGIN_ID = 'mindmap-renderer';
    const LIB_BASE = `/api/plugins/${PLUGIN_ID}/lib`;

    let markmapLoaded = false;
    let observerInitialized = false;
    let markmapCounter = 0;
    let settings = {};
    let mainObserver = null;

    const contentStabilityMap = new Map();
    const STABILITY_DELAY = 800;
    const DEBUG = typeof localStorage !== 'undefined' && localStorage.getItem('mindmap-debug') === '1';

    const i18n = {
        en: {
            loading: 'Loading...',
            renderError: 'Render error',
            emptyDiagram: 'Empty diagram',
            download: 'Download SVG'
        },
        zh: {
            loading: '加载中...',
            renderError: '渲染错误',
            emptyDiagram: '空图表',
            download: '下载 SVG'
        }
    };

    function t(key) {
        const lang = ChatRawPlugin?.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }

    function escapeHtml(str) {
        if (typeof str !== 'string') return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function downloadSvg(svg, filename) {
        const svgClone = svg.cloneNode(true);
        const bbox = svg.getBBox();
        const padding = 20;
        const width = Math.max(bbox.width + bbox.x + padding * 2, 800);
        const height = Math.max(bbox.height + bbox.y + padding * 2, 500);
        svgClone.setAttribute('width', width);
        svgClone.setAttribute('height', height);
        svgClone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('width', '100%');
        rect.setAttribute('height', '100%');
        rect.setAttribute('fill', '#ffffff');
        svgClone.insertBefore(rect, svgClone.firstChild);

        const serializer = new XMLSerializer();
        const svgString = '<?xml version="1.0" encoding="UTF-8"?>\n' + serializer.serializeToString(svgClone);
        const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename || 'mindmap.svg';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(a.href);
    }

    function loadScript(url) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(`script[src="${url}"]`)) {
                resolve();
                return;
            }
            const script = document.createElement('script');
            script.src = url;
            script.onload = resolve;
            script.onerror = () => reject(new Error(`Failed to load: ${url}`));
            document.head.appendChild(script);
        });
    }

    async function initMarkmap() {
        if (markmapLoaded) return !!window.markmap;
        try {
            await loadScript(`${LIB_BASE}/markmap-bundle.min.js`);
            if (window.markmap?.Transformer && window.markmap?.Markmap) {
                markmapLoaded = true;
                return true;
            }
        } catch (e) {
            console.error('[MindmapRenderer] Failed to load Markmap:', e);
        }
        return false;
    }

    // ---------- after_receive: detect and wrap structured content ----------
    function convertNumberedOutlineToMarkdown(lines) {
        const result = [];
        for (const line of lines) {
            const m = line.match(/^(\s*)(\d+(?:\.\d+)*)\.\s*(.*)$/);
            if (m) {
                const depth = (m[1]?.length || 0) / 2;
                const numParts = m[2].split('.').length;
                const hashes = '#'.repeat(Math.min(numParts + 1, 6));
                result.push(hashes + ' ' + m[3].trim());
            } else {
                result.push(line);
            }
        }
        return result.join('\n');
    }

    function detectStructuredBlocks(content, minLevels) {
        const blocks = [];
        const lines = content.split('\n');

        let i = 0;
        while (i < lines.length) {
            const line = lines[i];

            if (/^```\s*(?:markmap|mindmap)\s*$/i.test(line.trim())) {
                const start = i;
                i++;
                const blockLines = [];
                while (i < lines.length && !/^```\s*$/.test(lines[i])) {
                    blockLines.push(lines[i]);
                    i++;
                }
                i++;
                const inner = blockLines.join('\n').trim();
                if (inner) blocks.push({ type: 'markmap', content: inner, start, end: i });
                continue;
            }
            if (/^```\s*json\s*$/i.test(line.trim()) && settings.autoDetect !== false) {
                const start = i;
                i++;
                const blockLines = [];
                while (i < lines.length && !/^```\s*$/.test(lines[i])) {
                    blockLines.push(lines[i]);
                    i++;
                }
                i++;
                const inner = blockLines.join('\n').trim();
                if (inner && /^\s*\{\s*"title"\s*:/.test(inner)) {
                    blocks.push({ type: 'json', content: inner, start, end: i });
                }
                continue;
            }

            if ((/^#{2,6}\s+.+/).test(line) && settings.autoDetect !== false) {
                const start = i;
                const blockLines = [line];
                i++;
                while (i < lines.length) {
                    const l = lines[i];
                    if ((/^#{2,6}\s+.+/).test(l) || /^\s*[-*]\s+.+/.test(l) || /^\s*\d+(?:\.\d+)*\.\s*.+/.test(l) || /^\s*$/.test(l)) {
                        if (/^\s*$/.test(l) && blockLines.length > 0 && blockLines[blockLines.length - 1].trim() === '') {
                            i++;
                            break;
                        }
                        blockLines.push(l);
                        i++;
                    } else if (l.trim() === '') {
                        blockLines.push(l);
                        i++;
                    } else {
                        break;
                    }
                }
                const headingMatches = blockLines.filter(l => (/^#{2,6}\s+/).test(l)).map(l => {
                    const m = l.match(/^(#+)/);
                    return m ? m[1].length : 0;
                });
                const headingLevels = new Set(headingMatches);
                const hasList = blockLines.some(l => /^\s*[-*]/.test(l));
                if (headingLevels.size >= (minLevels || 2) || (headingLevels.size >= 1 && hasList)) {
                    const inner = blockLines.join('\n').trim();
                    if (inner) blocks.push({ type: 'headings', content: inner, start, end: i });
                }
                continue;
            }

            if (/^\s*[-*]\s+.+/.test(line) && settings.autoDetect !== false) {
                const start = i;
                const blockLines = [line];
                i++;
                while (i < lines.length && (/^\s*[-*]\s+.+/.test(lines[i]) || /^\s*$/.test(lines[i]))) {
                    blockLines.push(lines[i]);
                    i++;
                }
                if (blockLines.filter(l => l.trim()).length >= 2) {
                    const inner = blockLines.join('\n').trim();
                    if (inner) blocks.push({ type: 'list', content: inner, start, end: i });
                }
                continue;
            }

            if (/^\s*\d+(?:\.\d+)*\.\s*.+/.test(line) && settings.autoDetect !== false) {
                const start = i;
                const blockLines = [line];
                i++;
                while (i < lines.length && (/^\s*\d+(?:\.\d+)*\.\s*.+/.test(lines[i]) || /^\s*$/.test(lines[i]))) {
                    blockLines.push(lines[i]);
                    i++;
                }
                if (blockLines.filter(l => l.trim()).length >= 2) {
                    const inner = convertNumberedOutlineToMarkdown(blockLines);
                    if (inner) blocks.push({ type: 'outline', content: inner, start, end: i });
                }
                continue;
            }

            i++;
        }

        return blocks;
    }

    function transformContent(content) {
        if (!content || typeof content !== 'string') return content;
        if (settings.enableMindmap === false) return content;

        const minLevels = Math.max(1, parseInt(settings.minLevels, 10) || 2);
        const blocks = detectStructuredBlocks(content, minLevels);
        if (blocks.length === 0) return content;

        const lines = content.split('\n');
        function linePos(n) {
            return lines.slice(0, n).join('\n').length;
        }

        const result = [];
        let lastEnd = 0;

        for (const b of blocks) {
            result.push(content.slice(lastEnd, linePos(b.start)));
            result.push('\n```markmap\n');
            result.push(b.content);
            result.push('\n```\n');
            lastEnd = linePos(b.end);
        }
        result.push(content.slice(lastEnd));
        return result.join('');
    }

    // ---------- DOM: render markmap blocks ----------
    function injectStyles() {
        const id = 'mindmap-renderer-styles';
        if (document.getElementById(id)) return;
        const style = document.createElement('style');
        style.id = id;
        style.textContent = `
            .mindmap-container { display: block; margin: 1em 0; padding: 1em; position: relative;
                background: var(--bg-secondary, #f5f5f5); border-radius: 8px; overflow: auto; }
            .mindmap-loading { min-height: 100px; align-items: center; }
            .mindmap-loading-text { color: var(--text-secondary, #666); font-style: italic; }
            .mindmap-error-container { color: var(--error-color, #ef4444); background: rgba(239,68,68,0.1);
                padding: 1em; border-radius: 8px; }
            .mindmap-rendered svg { max-width: 100%; min-height: 400px; display: block; }
            .mindmap-rendered svg .markmap-node { cursor: pointer; }
            .mindmap-rendered svg .markmap-foreign { overflow: visible; }
            .mindmap-rendered svg line { stroke: inherit; }
            .mindmap-rendered svg path { fill: none; }
            .mindmap-rendered { overflow: visible; min-height: 420px; display: block; }
            .mindmap-download-btn { position: absolute; top: 8px; right: 8px; z-index: 10;
                width: 28px; height: 28px; padding: 0; border: none; border-radius: 4px; cursor: pointer;
                background: rgba(0,0,0,0.06); color: #666;
                opacity: 0.6; transition: opacity 0.2s, background 0.2s;
                display: flex; align-items: center; justify-content: center; }
            .mindmap-download-btn:hover { opacity: 1; background: rgba(0,0,0,0.12); }
            .mindmap-download-btn svg { width: 14px; height: 14px; }
        `;
        document.head.appendChild(style);
    }

    var NODE_TEXT_KEYS = ['title', 'label', 'text', 'name', 'topic', 'value', 'center'];
    var NODE_CHILDREN_KEYS = ['children', 'subBranches', 'branches', 'nodes'];

    function getNodeText(n) {
        if (n == null) return '';
        if (typeof n === 'string') return n.trim();
        if (typeof n !== 'object') return '';
        for (var i = 0; i < NODE_TEXT_KEYS.length; i++) {
            var v = n[NODE_TEXT_KEYS[i]];
            if (v != null) return String(v).trim();
        }
        if (n.data) {
            var vt = n.data.text != null ? n.data.text : n.data.title;
            if (vt != null) return String(vt).trim();
        }
        return '';
    }

    function getNodeChildren(obj) {
        if (!obj || typeof obj !== 'object') return [];
        for (var i = 0; i < NODE_CHILDREN_KEYS.length; i++) {
            var arr = obj[NODE_CHILDREN_KEYS[i]];
            if (Array.isArray(arr)) return arr;
        }
        if (obj.data && Array.isArray(obj.data.children)) return obj.data.children;
        return [];
    }

    function toMarkmapNode(obj) {
        if (obj == null) return null;
        if (typeof obj === 'string') return { content: obj.trim() || ' ', children: [] };
        if (typeof obj !== 'object') return null;
        var text = getNodeText(obj) || ' ';
        var kids = getNodeChildren(obj);
        return {
            content: text.trim() || ' ',
            children: kids.map(function(c) {
                var m = toMarkmapNode(c);
                return m || { content: getNodeText(c) || ' ', children: [] };
            }).filter(function(x) { return x && (x.content || x.children.length); })
        };
    }

    function treeToMarkdown(node, level) {
        if (!node || (!node.content && !node.children)) return '';
        level = level || 0;
        var hashes = '#'.repeat(Math.min(level + 1, 6));
        var lines = [];
        var text = (node.content && node.content.trim()) || (level === 0 ? '主题' : '');
        if (text) lines.push(hashes + ' ' + text);
        (node.children || []).forEach(function(c) { lines.push(treeToMarkdown(c, level + 1)); });
        return lines.filter(Boolean).join('\n');
    }

    function parseMindmapContent(raw) {
        var s = raw.trim();
        if (!s || s[0] !== '{') return null;
        s = s.replace(/\/\/[^\n]*/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
        try {
            var obj = JSON.parse(s);
            if (!obj) return null;
            var rootTitle = '';
            var children = [];
            if (Array.isArray(obj.branches) && obj.branches.length) {
                rootTitle = getNodeText(obj) || (obj.center != null ? String(obj.center) : '') || ' ';
                children = obj.branches.map(function(b) { return toMarkmapNode(b); }).filter(Boolean);
            } else if (obj.root && typeof obj.root === 'object' && (obj.root.children || obj.root.data || obj.root.branches)) {
                var r = obj.root;
                rootTitle = getNodeText(obj) || getNodeText(r) || ' ';
                children = getNodeChildren(r).length ? getNodeChildren(r).map(function(n) { return toMarkmapNode(n); }).filter(Boolean)
                    : (Array.isArray(r.branches) ? r.branches : []).map(function(b) { return toMarkmapNode(b); }).filter(Boolean);
            } else if (obj.data && (obj.data.children || obj.data.text != null)) {
                rootTitle = getNodeText(obj) || getNodeText(obj.data) || ' ';
                children = (obj.data.children || []).map(function(n) { return toMarkmapNode(n); }).filter(Boolean);
            } else if (obj.children && obj.children.length || getNodeText(obj) || getNodeChildren(obj).length) {
                return toMarkmapNode(obj);
            }
            if (rootTitle || children.length) {
                return { content: String(rootTitle).trim() || ' ', children: children };
            }
        } catch (_) {}
        return null;
    }

    async function renderMarkmapBlock(codeBlock) {
        const pre = codeBlock.parentElement;
        if (!pre || pre.dataset.markmapProcessed) return;

        pre.dataset.markmapProcessed = 'true';
        let raw = codeBlock.textContent.trim();
        if (!raw) {
            const err = document.createElement('div');
            err.className = 'mindmap-error-container';
            err.innerHTML = `<strong>${escapeHtml(t('renderError'))}:</strong> ${escapeHtml(t('emptyDiagram'))}`;
            pre.parentNode.replaceChild(err, pre);
            return;
        }

        const id = `mindmap-${Date.now()}-${markmapCounter++}`;
        const container = document.createElement('div');
        container.id = id;
        container.className = 'mindmap-container mindmap-loading';
        container.innerHTML = `<div class="mindmap-loading-text">${t('loading')}</div>`;
        pre.parentNode.replaceChild(container, pre);

        const ok = await initMarkmap();
        if (!ok || !window.markmap) {
            container.className = 'mindmap-error-container';
            container.innerHTML = `<strong>${escapeHtml(t('renderError'))}:</strong> Markmap failed to load`;
            return;
        }

        try {
            const { Transformer, Markmap, loadCSS, loadJS } = window.markmap;
            let root;
            let assets = { styles: [], scripts: [] };

            const jsonRoot = parseMindmapContent(raw);
            let markdown = raw;
            if (jsonRoot) {
                if (DEBUG) console.log('[MindmapRenderer] using JSON root:', JSON.stringify(jsonRoot).slice(0, 200));
                markdown = treeToMarkdown(jsonRoot);
                if (markdown) {
                    const transformer = new Transformer();
                    const result = transformer.transform(markdown);
                    root = result.root;
                    const a = transformer.getUsedAssets(result.features);
                    if (a) assets = a;
                } else {
                    root = jsonRoot;
                }
            }
            if (!root) {
                if (/^\s*mindmap\s/m.test(raw) || /^\s*mindmap\s*$/m.test(raw)) {
                    const converted = mermaidMindmapToMarkdown(raw);
                    if (converted) markdown = converted;
                }
                if (!root) {
                    if (/^#{2,6}\s+/m.test(markdown) && !/^#\s+/m.test(markdown)) {
                        markdown = '# 主题\n' + markdown;
                    }
                    const transformer = new Transformer();
                    const result = transformer.transform(markdown);
                    root = result.root;
                    const a = transformer.getUsedAssets(result.features);
                    if (a) assets = a;
                }
            }

            if (assets.styles && assets.styles.length) {
                for (let si = 0; si < assets.styles.length; si++) {
                    const s = assets.styles[si];
                    const href = typeof s === 'string' ? s : (s && (s.data && s.data.href || s.href));
                    if (href) {
                        try { await loadCSS(href); } catch (_) { /* ignore */ }
                    }
                }
            }
            if (assets.scripts && assets.scripts.length) {
                try {
                    await loadJS(assets.scripts, { getMarkmap: () => window.markmap });
                } catch (_) { /* ignore */ }
            }

            container.innerHTML = '';
            container.classList.remove('mindmap-loading');
            container.classList.add('mindmap-rendered');

            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', '800');
            svg.setAttribute('height', '500');
            svg.style.maxWidth = '100%';
            svg.style.display = 'block';
            svg.style.minHeight = '400px';
            container.appendChild(svg);

            const downloadBtn = document.createElement('button');
            downloadBtn.className = 'mindmap-download-btn';
            downloadBtn.title = t('download');
            downloadBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>';
            downloadBtn.onclick = function() {
                const timestamp = new Date().toISOString().slice(0, 10);
                downloadSvg(svg, 'mindmap-' + timestamp + '.svg');
            };
            container.appendChild(downloadBtn);

            const opts = { initialExpandLevel: -1, maxWidth: 280, autoFit: true, embedGlobalCSS: true, duration: 0 };
            const mm = new Markmap(svg, opts);
            await mm.setData(root);
            await mm.fit();
            if (DEBUG) console.log('[MindmapRenderer] SVG children:', svg.childNodes.length, 'innerHTML preview:', svg.innerHTML.slice(0, 500));
        } catch (e) {
            console.error('[MindmapRenderer] Render error:', e);
            container.className = 'mindmap-error-container';
            container.innerHTML = `<strong>${escapeHtml(t('renderError'))}:</strong> ${escapeHtml(e.message || 'Unknown')}<pre>${escapeHtml(raw)}</pre>`;
        }
    }

    function mermaidMindmapToMarkdown(raw) {
        const lines = raw.split('\n');
        const result = [];
        const stack = [{ depth: -1 }];
        for (const line of lines) {
            const trimmed = line.trimEnd();
            if (!trimmed || trimmed === 'mindmap') continue;
            const spaces = line.match(/^\s*/)[0].length;
            let text = trimmed.replace(/^\s+/, '');
            text = text.replace(/^\(\(([^)]*)\)\)$/, '$1').replace(/^\[([^\]]*)\]$/, '$1')
                .replace(/^\(([^)]*)\)$/, '$1').replace(/^\[\[([^\]]*)\]\]$/, '$1')
                .replace(/^root\s*\(\(([^)]*)\)\)$/i, '$1').replace(/^root\s*$/i, '主题').trim();
            if (!text) continue;
            while (stack.length > 1 && stack[stack.length - 1].depth >= spaces) stack.pop();
            const level = stack.length - 1;
            stack.push({ depth: spaces });
            const hashes = '#'.repeat(Math.min(level + 1, 6));
            result.push(hashes + ' ' + text);
        }
        return result.length ? result.join('\n') : null;
    }

    function looksLikeMindmap(raw) {
        var s = raw.trim();
        if (!s || s.length < 8) return false;
        if (/^\s*mindmap\s/m.test(s) || /^\s*mindmap\s*$/m.test(s)) return true;
        if (s[0] === '{' && (/"(?:title|label|root|branches|children)"\s*:/.test(s) || /"[^"]+"\s*:\s*[\[{]/.test(s))) return true;
        if (/^#+\s+\S+/m.test(s)) return true;
        return false;
    }

    async function processMarkmapInElement(element) {
        if (settings.enableMindmap === false) return;
        const explicit = element.querySelectorAll('pre > code.language-markmap, pre > code[class*="markmap"], pre > code.language-json, pre > code.language-mermaid');
        const fallback = element.querySelectorAll('pre > code');
        const seen = new Set();
        let processed = 0;
        for (const block of explicit) {
            if (seen.has(block)) continue;
            seen.add(block);
            const raw = block.textContent.trim();
            if (block.classList.contains('language-json') && !parseMindmapContent(raw)) continue;
            if (block.classList.contains('language-mermaid') && !looksLikeMindmap(raw)) continue;
            if (block.parentElement && block.parentElement.dataset.markmapProcessed) continue;
            if (DEBUG) console.log('[MindmapRenderer] explicit block:', block.className, raw.slice(0, 60) + '...');
            await renderMarkmapBlock(block);
            processed++;
        }
        for (const block of fallback) {
            if (seen.has(block)) continue;
            const raw = block.textContent.trim();
            if (!looksLikeMindmap(raw)) continue;
            if (block.parentElement && block.parentElement.dataset.markmapProcessed) continue;
            seen.add(block);
            if (DEBUG) console.log('[MindmapRenderer] fallback block:', block.className, raw.slice(0, 60) + '...');
            await renderMarkmapBlock(block);
            processed++;
        }
        if (DEBUG && processed === 0 && fallback.length > 0) {
            fallback.forEach((b, i) => { console.log('[MindmapRenderer] skip block', i, 'class:', b.className, 'preview:', b.textContent.trim().slice(0, 50)); });
        }
    }

    function scheduleProcessing(element) {
        const key = element;
        const existing = contentStabilityMap.get(key);
        if (existing) clearTimeout(existing);
        const timer = setTimeout(async () => {
            contentStabilityMap.delete(key);
            await processMarkmapInElement(element);
        }, STABILITY_DELAY);
        contentStabilityMap.set(key, timer);
    }

    function initObserver() {
        if (observerInitialized) return;
        injectStyles();

        const observer = new MutationObserver((mutations) => {
            const elements = new Set();
            for (const m of mutations) {
                for (const node of m.addedNodes) {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        if (node.classList?.contains('message')) {
                            const c = node.querySelector('.message-content');
                            if (c) elements.add(c);
                        } else if (node.classList?.contains('message-content')) {
                            elements.add(node);
                        } else if (node.querySelector?.('.message-content')) {
                            node.querySelectorAll('.message-content').forEach(el => elements.add(el));
                        }
                    }
                }
                if (m.type === 'characterData' || m.type === 'childList') {
                    const target = m.target?.nodeType === Node.TEXT_NODE ? m.target.parentElement : m.target;
                    const mc = target?.closest?.('.message-content');
                    if (mc) elements.add(mc);
                }
            }
            for (const el of elements) scheduleProcessing(el);
        });

        const container = document.querySelector('.messages') || document.querySelector('.messages-container') || document.body;
        observer.observe(container, { childList: true, subtree: true, characterData: true });

        const initial = document.querySelectorAll('.message-content');
        if (DEBUG) console.log('[MindmapRenderer] initObserver, container:', container?.className, 'message-contents:', initial.length);
        initial.forEach(el => scheduleProcessing(el));
        mainObserver = observer;
        observerInitialized = true;
    }

    async function loadSettings() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const p = plugins.find(x => x.id === PLUGIN_ID);
                if (p?.settings_values) settings = p.settings_values;
            }
        } catch (e) {
            console.error('[MindmapRenderer] Failed to load settings:', e);
        }
    }

    function init() {
        if (DEBUG) console.log('[MindmapRenderer] init, ChatRawPlugin:', !!window.ChatRawPlugin);
        loadSettings().then(() => {
            if (ChatRawPlugin?.hooks?.register) {
                ChatRawPlugin.hooks.register('after_receive', {
                    priority: 15,
                    handler: async (message) => {
                        if (!message?.content || settings.enableMindmap === false) return { success: false };
                        const modified = transformContent(message.content);
                        if (modified === message.content) return { success: false };
                        return { success: true, content: modified };
                    }
                });
            }
            initObserver();
        });
    }

    window.__mindmapReprocess = function() {
        if (!observerInitialized) return console.warn('[MindmapRenderer] Plugin not initialized');
        const elms = document.querySelectorAll('.message-content');
        console.log('[MindmapRenderer] Manual reprocess, message-contents:', elms.length);
        elms.forEach(el => scheduleProcessing(el));
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window.ChatRawPlugin);
