// Exercise renderer and bundled plugins in a real browser after a streaming pause.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = new URL('../', import.meta.url);
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined });
const page = await browser.newPage();
const origin = 'http://chatraw-render.test';
const response = '<div class="messages"><div class="message"><div class="message-content">' +
    '<div id="reply" class="message-markdown"></div></div></div></div>' +
    '<button id="copy"><i></i></button>' +
    '<script>window.ChatRawPlugin = { utils: { getLanguage: () => "en" } };</script>' +
    '<script src="/vendor/marked.js"></script><script src="/stream-markdown.js"></script>' +
    '<script src="/agents.js"></script><script src="/app.js"></script>' +
    '<script src="/api/plugins/markdown-enhancer/main.js"></script>';

const localPaths = new Map([
    ['/vendor/marked.js', 'backend/static/vendor/marked/9.1.6/marked.min.js'],
    ['/stream-markdown.js', 'backend/static/stream-markdown.js'],
    ['/agents.js', 'backend/static/agents.js'],
    ['/app.js', 'backend/static/app.js'],
    ['/vendor/highlight/11.9.0/github-dark.min.css', 'backend/static/vendor/highlight/11.9.0/github-dark.min.css'],
    ['/vendor/highlight/11.9.0/highlight.min.js', 'backend/static/vendor/highlight/11.9.0/highlight.min.js']
]);

try {
    await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== origin) return route.abort();
        if (url.pathname === '/') return route.fulfill({ contentType: 'text/html', body: response });
        if (url.pathname === '/api/plugins') return route.fulfill({
            json: [{ id: 'markdown-enhancer', enabled: true, settings_values: { enableExtraLanguages: false } }]
        });

        const pluginFile = url.pathname.match(/^\/api\/plugins\/(markdown-enhancer\/(?:main\.js|lib\/[a-zA-Z0-9_.\/-]+))$/)?.[1];
        const path = localPaths.get(url.pathname) || (pluginFile && 'Plugins/Plugin_market/' + pluginFile);
        if (!path) return route.abort();
        const type = path.endsWith('.css') ? 'text/css' : path.endsWith('.js') ? 'text/javascript' : 'application/octet-stream';
        return route.fulfill({ contentType: type, body: await readFile(fileURLToPath(new URL(path, root))) });
    });
    await page.goto(origin);
    const render = (source, live, replay = false) => page.evaluate(({ source, live, replay }) => {
        window.ChatRawMarkdown.render(document.querySelector('#reply'), source, { live, replay });
    }, { source, live, replay });

    const first = 'A stable paragraph.\n\nBefore $x^2$';
    await render(first, true, true);
    await page.waitForFunction(() => document.querySelector('#reply')?.textContent.includes('x^2'));
    await page.evaluate(() => { window.stableParagraph = document.querySelector('#reply p'); });

    const full = first + ' after.\n\n```mermaid\ngraph TD\nA[起点] --> B[完成]\n```' +
        '\n\n```python\nprint("ready")\n```';
    await render(full, true);
    await page.locator('#reply .markdown-reveal').first().waitFor({ state: 'attached' });
    assert.equal(await page.evaluate(() => window.stableParagraph === document.querySelector('#reply p')), true);
    // The previous plugin processed live content after this stability delay.
    await new Promise(resolve => setTimeout(resolve, 1000));
    assert.equal(await page.locator('#reply .katex').count(), 0);
    assert.equal(await page.locator('#reply pre code.language-mermaid').count(), 1);

    await render(full, false);
    await page.locator('#reply .katex').waitFor();
    await page.locator('#reply .mermaid-rendered').waitFor();
    await page.locator('#reply pre code.language-python.hljs').waitFor();
    const copied = await page.evaluate(async source => {
        let clipboard;
        Object.defineProperty(navigator, 'clipboard', { value: { writeText: async text => { clipboard = text; } } });
        await app().copyMessage(source, { currentTarget: document.querySelector('#copy') });
        return clipboard;
    }, full);
    assert.equal(copied, full);
    const label = await page.evaluate(() => window.ChatRawMarkdown.diagramLabel(
        '<strong onclick="window.bad = true">Label</strong><a href="java&#115;cript:alert(1)">Bad link</a>'
    ));
    assert.equal(label, '<strong>Label</strong><a>Bad link</a>');
    assert.equal(await page.locator('#reply [data-markdown-text], #reply .markdown-reveal').count(), 0);
    assert.equal(await page.evaluate(() => window.stableParagraph === document.querySelector('#reply p')), true);

    // An installed older plugin may already have replaced text within a live slot.
    await render('Previously decorated text', true, true);
    await page.locator('#reply [data-markdown-text]').waitFor();
    await page.evaluate(() => {
        const slot = document.querySelector('#reply [data-markdown-text]');
        const decoration = document.createElement('em');
        decoration.className = 'legacy-decoration';
        decoration.textContent = slot.textContent;
        slot.replaceChildren(decoration);
    });
    await render('Previously decorated text', false);
    assert.equal(await page.locator('#reply .legacy-decoration').count(), 1);

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await render('No reveal for reduced motion.', true);
    await page.locator('#reply p').waitFor();
    assert.equal(await page.locator('#reply .markdown-reveal').count(), 0);
    await render('', false);
    assert.equal(await page.locator('#reply').innerText(), '');
    console.log('Streaming Markdown plugin regression passed on Chromium ' + browser.version());
} finally {
    await browser.close();
}
