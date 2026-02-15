/**
 * Enhanced Export - Export assistant messages as TXT, MD, PDF, or HTML
 *
 * Features:
 * - Export button next to Copy on each assistant message
 * - 4 format toggles in settings (TXT, MD, PDF, HTML)
 * - Batch download when multiple formats enabled
 * - TXT strips Markdown symbols for plain text
 * - Includes thinking block when present
 *
 * Architecture: MutationObserver watches messages container, injects Export button
 * into .message-actions when at least one format is enabled.
 */
(function(ChatRawPlugin) {
    'use strict';
    if (!ChatRawPlugin) {
        console.error('[EnhancedExport] ChatRawPlugin not found');
        return;
    }

    const PLUGIN_ID = 'enhanced-export';
    const LIB_BASE = `/api/plugins/${PLUGIN_ID}/lib`;
    const EXPORT_BTN_CLASS = 'btn-export-ee';

    let settings = { exportTxt: true, exportMd: true, exportPdf: true, exportHtml: true };
    let html2pdfLoaded = false;
    let observerInitialized = false;

    const STABILITY_DELAY = 50;

    const i18n = {
        en: {
            export: 'Export',
            exporting: 'Exporting...',
            exportSuccess: 'Exported',
            exportFailed: 'Export failed',
            noFormatEnabled: 'Enable at least one format in settings'
        },
        zh: {
            export: '导出',
            exporting: '导出中...',
            exportSuccess: '已导出',
            exportFailed: '导出失败',
            noFormatEnabled: '请在设置中开启至少一种导出格式'
        }
    };

    function t(key) {
        const lang = ChatRawPlugin?.utils?.getLanguage?.() || 'en';
        return i18n[lang]?.[key] || i18n.en[key] || key;
    }

    function stripMarkdown(md) {
        if (typeof md !== 'string') return '';
        return md
            .replace(/```[\s\S]*?```/g, '')           // code blocks
            .replace(/`[^`]+`/g, (m) => m.slice(1, -1))
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/__([^_]+)__/g, '$1')
            .replace(/_([^_]+)_/g, '$1')
            .replace(/^#{1,6}\s+/gm, '')
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
            .replace(/^[-*+]\s+/gm, '')
            .replace(/^\d+\.\s+/gm, '')
            .replace(/^>\s+/gm, '')
            .replace(/^---+$/gm, '')
            .replace(/^\*\*\*+$/gm, '')
            .replace(/^___+$/gm, '')
            .replace(/\n{3,}/g, '\n\n')
            .trim();
    }

    function buildContent(msg) {
        const parts = [];
        if (msg.thinking && msg.thinking.trim()) {
            parts.push(msg.thinking.trim());
        }
        if (msg.content && msg.content.trim()) {
            parts.push(msg.content.trim());
        }
        return parts.join('\n\n');
    }

    function buildMdContent(msg) {
        const parts = [];
        if (msg.thinking && msg.thinking.trim()) {
            parts.push('## ' + t('thinking') + '\n\n' + msg.thinking.trim());
        }
        if (msg.content && msg.content.trim()) {
            parts.push('## ' + t('reply') + '\n\n' + msg.content.trim());
        }
        return parts.join('\n\n');
    }

    const thinkingI18n = { en: { thinking: 'Thinking Process', reply: 'Reply' }, zh: { thinking: '思考过程', reply: '回复' } };
    Object.assign(i18n.en, thinkingI18n.en);
    Object.assign(i18n.zh, thinkingI18n.zh);

    function downloadBlob(blob, filename) {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
    }

    function getMsgForActions(actionsEl) {
        var messages = ChatRawPlugin?.utils?.getMessages?.() || [];
        if (!messages.length) return null;
        var slot = actionsEl.querySelector('.message-actions-plugin-slot') || actionsEl.closest('.message-actions')?.querySelector('.message-actions-plugin-slot');
        if (slot && slot.getAttribute('data-msg-index') != null) {
            var idx = parseInt(slot.getAttribute('data-msg-index'), 10);
            if (!isNaN(idx) && idx >= 0 && idx < messages.length) return messages[idx];
        }
        var messageEl = actionsEl.closest('.message');
        if (!messageEl || !messageEl.classList.contains('assistant')) return null;
        var container = messageEl.closest('.messages');
        if (!container) return null;
        var assistantMsgs = messages.filter(function (m) { return m.role === 'assistant' && m.content; });
        if (!assistantMsgs.length) return null;
        var assistantElements = Array.from(container.querySelectorAll('.message.assistant')).filter(function (el) {
            return el.querySelector('.message-actions');
        });
        var idx = assistantElements.indexOf(messageEl);
        if (idx < 0 || idx >= assistantMsgs.length) return null;
        return assistantMsgs[idx];
    }

    async function loadHtml2pdf() {
        if (html2pdfLoaded || typeof window.html2pdf !== 'undefined') {
            html2pdfLoaded = true;
            return true;
        }
        try {
            await new Promise((resolve, reject) => {
                const s = document.createElement('script');
                s.src = `${LIB_BASE}/html2pdf.bundle.min.js`;
                s.onload = resolve;
                s.onerror = () => reject(new Error('Failed to load html2pdf'));
                document.head.appendChild(s);
            });
            html2pdfLoaded = true;
            return true;
        } catch (e) {
            console.error('[EnhancedExport] Failed to load html2pdf:', e);
            return false;
        }
    }

    function getHtmlTemplate(bodyContent) {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Export</title>
<style>
body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.6;color:#333;max-width:720px;margin:0 auto;padding:24px}
h1,h2,h3{font-weight:600;margin-top:1.5em}
pre,code{background:#f5f5f5;border-radius:4px;padding:2px 6px;font-family:ui-monospace,monospace}
pre{overflow-x:auto;padding:12px}
blockquote{border-left:4px solid #ddd;margin:0;padding-left:16px;color:#666}
</style>
</head>
<body>
<article>${bodyContent}</article>
</body>
</html>`;
    }

    async function doExport(msg, formats, btn) {
        if (!msg || !msg.content) return;
        const hasAny = formats.exportTxt || formats.exportMd || formats.exportPdf || formats.exportHtml;
        if (!hasAny) {
            ChatRawPlugin?.utils?.showToast?.(t('noFormatEnabled'), 'info');
            return;
        }
        const fullContent = buildContent(msg);
        if (!fullContent.trim()) return;

        const originalTitle = btn.getAttribute('title');
        btn.setAttribute('title', t('exporting'));
        btn.disabled = true;
        if (btn.querySelector('i')) btn.querySelector('i').className = 'ri-loader-4-line';

        try {
            const base = 'export';
            const delay = 200;

            if (formats.exportTxt) {
                const plain = stripMarkdown(fullContent);
                downloadBlob(new Blob([plain], { type: 'text/plain;charset=utf-8' }), `${base}.txt`);
                await new Promise(r => setTimeout(r, delay));
            }
            if (formats.exportMd) {
                const md = buildMdContent(msg);
                downloadBlob(new Blob([md], { type: 'text/markdown;charset=utf-8' }), `${base}.md`);
                await new Promise(r => setTimeout(r, delay));
            }
            if (formats.exportHtml) {
                const marked = window.marked;
                const htmlContent = marked ? marked.parse(fullContent) : fullContent.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
                const doc = getHtmlTemplate(htmlContent);
                downloadBlob(new Blob([doc], { type: 'text/html;charset=utf-8' }), `${base}.html`);
                await new Promise(r => setTimeout(r, delay));
            }
            if (formats.exportPdf) {
                const ok = await loadHtml2pdf();
                if (ok && window.html2pdf) {
                    const marked = window.marked;
                    const htmlContent = marked ? marked.parse(fullContent) : fullContent.replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>');
                    const div = document.createElement('div');
                    div.style.cssText = 'font-family:system-ui,sans-serif;line-height:1.6;color:#333;padding:20px;font-size:14px;max-width:600px';
                    div.innerHTML = htmlContent;
                    document.body.appendChild(div);
                    await window.html2pdf().set({
                        margin: 10,
                        filename: `${base}.pdf`,
                        image: { type: 'jpeg', quality: 0.98 },
                        html2canvas: { scale: 2 },
                        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                    }).from(div).save();
                    document.body.removeChild(div);
                } else {
                    ChatRawPlugin?.utils?.showToast?.(t('exportFailed') + ' (PDF)', 'error');
                }
            }

            ChatRawPlugin?.utils?.showToast?.(t('exportSuccess'), 'success');
        } catch (e) {
            console.error('[EnhancedExport] Export error:', e);
            ChatRawPlugin?.utils?.showToast?.(t('exportFailed'), 'error');
        } finally {
            btn.disabled = false;
            btn.setAttribute('title', originalTitle || t('export'));
            if (btn.querySelector('i')) btn.querySelector('i').className = 'ri-download-2-line';
        }
    }

    function getContentFromDom(messageEl) {
        var mc = messageEl.querySelector('.message-content');
        if (!mc) return null;
        var divs = Array.prototype.filter.call(mc.children, function (c) { return c.tagName === 'DIV'; });
        for (var i = 0; i < divs.length; i++) {
            var d = divs[i];
            if (!d.classList.contains('thinking-block') && !d.classList.contains('message-actions') && !d.classList.contains('rag-references') && !d.classList.contains('typing-indicator') && (d.innerHTML || d.innerText)) {
                return { content: d.innerText || d.textContent || '' };
            }
        }
        return null;
    }

    function injectExportButton(actionsEl) {
        var container = actionsEl.querySelector('.message-actions-plugin-slot') || actionsEl;
        if (container.querySelector && container.querySelector('.' + EXPORT_BTN_CLASS)) return;

        var hasAny = settings.exportTxt || settings.exportMd || settings.exportPdf || settings.exportHtml;
        if (!hasAny) return;

        var messageEl = actionsEl.closest('.message');
        if (!messageEl || !messageEl.classList.contains('assistant')) return;

        if (!actionsEl.querySelector('.btn-copy')) return;

        var btn = document.createElement('button');
        btn.className = 'btn-copy ' + EXPORT_BTN_CLASS;
        btn.setAttribute('title', t('export'));
        btn.innerHTML = '<i class="ri-download-2-line"></i>';
        btn.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopPropagation();
            var m = getMsgForActions(actionsEl);
            if (!m) {
                var domContent = getContentFromDom(messageEl);
                if (domContent && domContent.content) {
                    m = { role: 'assistant', content: domContent.content };
                }
            }
            if (m) {
                await doExport(m, settings, btn);
            } else {
                ChatRawPlugin?.utils?.showToast?.(t('exportFailed'), 'error');
            }
        });
        container.appendChild(btn);
    }

    function processActions(actionsEl) {
        if (!actionsEl || !document.body.contains(actionsEl)) return;
        var msg = actionsEl.closest('.message');
        if (!msg || !msg.classList.contains('assistant')) return;
        if (!actionsEl.querySelector('.btn-copy')) return;
        if (actionsEl.querySelector('.' + EXPORT_BTN_CLASS)) return;
        injectExportButton(actionsEl);
    }

    function scheduleProcessing(el) {
        var actionsEl = el;
        if (!el.classList || !el.classList.contains('message-actions')) {
            actionsEl = el.querySelector ? el.querySelector('.message-actions') : null;
        }
        if (!actionsEl || !document.body.contains(actionsEl)) return;
        processActions(actionsEl);
    }

    function processAllMessageActions() {
        var els = document.querySelectorAll('.messages .message-actions');
        els.forEach(function(el) { scheduleProcessing(el); });
    }

    function initObserver() {
        if (observerInitialized) return;

        var container = document.querySelector('.messages') || document.body;
        var observer = new MutationObserver(function() {
            processAllMessageActions();
        });
        observer.observe(container, { childList: true, subtree: true });

        processAllMessageActions();
        [50, 200, 500, 1000, 2000, 4000].forEach(function(ms) {
            setTimeout(processAllMessageActions, ms);
        });
        setInterval(processAllMessageActions, 1500);
        observerInitialized = true;
    }

    async function loadSettings() {
        try {
            const res = await fetch('/api/plugins');
            if (res.ok) {
                const plugins = await res.json();
                const p = plugins.find(x => x.id === PLUGIN_ID);
                if (p?.settings_values) {
                    settings = { ...settings, ...p.settings_values };
                }
            }
        } catch (e) {
            console.error('[EnhancedExport] Failed to load settings:', e);
        }
    }

    function onAfterReceive() {
        if (observerInitialized) {
            setTimeout(processAllMessageActions, 100);
            setTimeout(processAllMessageActions, 500);
        }
        return { success: false };
    }

    async function init() {
        try {
            await loadSettings();
            initObserver();
            if (ChatRawPlugin?.hooks?.register) {
                ChatRawPlugin.hooks.register('after_receive', { handler: onAfterReceive });
            }
        } catch (e) {
            console.error('[EnhancedExport] Init error:', e);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window.ChatRawPlugin);
