(function (chatraw) {
  'use strict';

  const id = 'html-renderer';
  const marker = 'chatraw-html-render-action';
  const rootKey = '__chatrawHtmlRenderer';
  const messages = document.querySelector('.messages');
  if (!chatraw || !messages) return;
  if (window[rootKey]) window[rootKey].destroy();

  const labels = {
    en: {
      render: 'Render', preview: 'Web preview',
      bridge: 'Enable the included Mac browser helper first.',
      failed: 'Could not open the browser. Check the browser helper.',
      tooLarge: 'This HTML exceeds the 8 MB preview limit.'
    },
    zh: {
      render: '渲染', preview: '网页预览',
      bridge: '请先启用插件附带的 Mac 浏览器辅助模块。',
      failed: '无法打开浏览器，请检查辅助模块。',
      tooLarge: 'HTML 超过 8 MB，无法预览。'
    }
  };
  const t = key => (labels[chatraw.utils.getLanguage()] || labels.en)[key];

  const style = document.createElement('style');
  style.textContent = `
        .${marker} { display: flex; justify-content: flex-end; margin: -10px 0 20px; }
        .${marker} button { font: inherit; font-size: .875rem; padding: 5px 12px; }
    `;
  document.head.appendChild(style);

  let pendingScan = null;
  let destroyed = false;

  const documentPrefix = '<!doctype html><meta http-equiv="Content-Security-Policy" ' +
        'content="connect-src &#39;none&#39;; form-action &#39;none&#39;; ' +
        'object-src &#39;none&#39;; base-uri &#39;none&#39;">';

  async function openPreview(source) {
    const tab = window.open('', '_blank');
    if (tab) {
      tab.opener = null;
      const doc = tab.document;
      doc.title = t('preview');
      const policy = doc.createElement('meta');
      policy.httpEquiv = 'Content-Security-Policy';
      policy.content = 'frame-src about:; connect-src \'none\'; form-action \'none\'; ' +
                'object-src \'none\'; base-uri \'none\'';
      doc.head.appendChild(policy);
      doc.documentElement.style.height = '100%';
      doc.body.style.cssText = 'margin:0;height:100%;overflow:hidden';
      const frame = doc.createElement('iframe');
      frame.title = t('preview');
      frame.setAttribute('sandbox', 'allow-scripts allow-forms allow-pointer-lock');
      frame.referrerPolicy = 'no-referrer';
      frame.style.cssText = 'display:block;width:100%;height:100%;border:0';
      frame.addEventListener('load', () => frame.focus(), { once: true });
      doc.body.appendChild(frame);
      frame.srcdoc = documentPrefix + source;
      return;
    }

    try {
      const response = await fetch('http://127.0.0.1:38479/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html: source, language: chatraw.utils.getLanguage() })
      });
      if (!response.ok) {
        chatraw.utils.showToast(t(response.status === 413 ? 'tooLarge' : 'failed'), 'error');
      }
    } catch (error) {
      console.error('[HTML Renderer] Browser helper unavailable:', error);
      chatraw.utils.showToast(t('bridge'), 'error');
    }
  }

  function isHtml(code) {
    const languages = Array.from(code.classList)
      .filter(name => /^language-/i.test(name))
      .map(name => name.slice(9).toLowerCase());
    if (languages.some(value => ['html', 'htm', 'xhtml'].includes(value))) return true;
    return (!languages.length || languages.includes('xml')) &&
            /^\s*(?:<!doctype\s+html\b|<html(?:\s|>))/i.test(code.textContent);
  }

  function makeButton(pre) {
    const wrap = document.createElement('div');
    wrap.className = marker;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn-secondary';
    button.textContent = t('render');
    button.addEventListener('click', () => {
      const code = pre.querySelector(':scope > code');
      if (code && isHtml(code)) openPreview(code.textContent);
    });
    wrap.appendChild(button);
    pre.insertAdjacentElement('afterend', wrap);
  }

  function scan() {
    pendingScan = null;
    if (destroyed) return;
    for (const action of messages.querySelectorAll(`.${marker}`)) {
      const pre = action.previousElementSibling;
      const code = pre?.matches('pre') && pre.querySelector(':scope > code');
      if (!code || !isHtml(code) || code.closest('[data-markdown-streaming]')) {
        action.remove();
      } else {
        const button = action.querySelector('button');
        if (button.textContent !== t('render')) button.textContent = t('render');
      }
    }
    for (const code of messages.querySelectorAll('.message.assistant .message-markdown pre > code')) {
      if (!isHtml(code) || code.closest('[data-markdown-streaming]')) continue;
      const pre = code.parentElement;
      if (!pre.nextElementSibling?.classList.contains(marker)) makeButton(pre);
    }
  }

  function scheduleScan() {
    if (pendingScan === null) pendingScan = setTimeout(scan, 0);
  }

  function isEnabled() {
    const app = window.Alpine?.$data(document.body);
    if (!app || !Array.isArray(app.installedPlugins)) return true;
    return app.installedPlugins.some(plugin => plugin.id === id && plugin.enabled);
  }

  const observer = new MutationObserver(scheduleScan);
  observer.observe(messages, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['data-markdown-streaming']
  });
  const timer = setInterval(() => {
    if (!isEnabled()) destroy();
    else scheduleScan();
  }, 1500);

  function destroy() {
    if (destroyed) return;
    destroyed = true;
    observer.disconnect();
    clearInterval(timer);
    if (pendingScan !== null) clearTimeout(pendingScan);
    messages.querySelectorAll(`.${marker}`).forEach(node => node.remove());
    style.remove();
    if (window[rootKey]?.destroy === destroy) delete window[rootKey];
  }

  window[rootKey] = { destroy };
  scheduleScan();
})(window.ChatRawPlugin);
