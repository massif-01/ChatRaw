import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = fileURLToPath(new URL('../', import.meta.url));
const browserPath = process.env.CHROME_PATH;
assert.ok(browserPath, 'Set CHROME_PATH to an installed Chrome or Chromium executable.');
const require109 = process.argv.includes('--require-109');

const markdown = [
    '## Offline fixture',
    '',
    '| Name | Value |',
    '| --- | --- |',
    '| Python | 109 |',
    '',
    '```python',
    'def answer():',
    '    return "<strong>escaped code</strong>"',
    '```',
    '',
    '```fixture-unknown',
    '<strong>literal code</strong>',
    '```',
].join('\n');
const pluginMarkdown = [
    'Formula: $x^2$',
    '',
    '```mermaid',
    'flowchart LR',
    '  A --> B',
    '```',
    '',
    '```markmap',
    '# Root',
    '- Leaf',
    '```',
].join('\n');

const requests = [];
const reasoningIntro = 'Offline reasoning fixture';
const reasoningContinuation = 'A paragraph of streamed reasoning.\n\n'.repeat(30) + 'Latest after opening';
let reasoningFixture;
const provider = createServer(async (request, response) => {
    if (request.method !== 'POST' || request.url !== '/v1/chat/completions') {
        response.writeHead(404).end();
        return;
    }
    let body = '';
    for await (const chunk of request) body += chunk;
    const input = JSON.parse(body);
    requests.push(input);
    const content = requests.length === 1 ? markdown : pluginMarkdown;
    if (!input.stream) {
        response.writeHead(200, { 'Content-Type': 'application/json' });
        response.end(JSON.stringify({ choices: [{ message: {
            content: 'Non-streaming answer', reasoning_content: 'Fixture transient thought',
        }, finish_reason: 'stop' }] }));
        return;
    }
    response.writeHead(200, { 'Content-Type': 'text/event-stream' });
    const send = delta => response.write(`data: ${JSON.stringify({ choices: [{ delta }] })}\n\n`);
    const startAnswer = () => send({ content: content.slice(0, 37) });
    const finishAnswer = () => {
        send({ content: content.slice(37) });
        response.end('data: [DONE]\n\n');
    };
    if (requests.length === 1 && input.enable_thinking) {
        reasoningFixture = {
            append: text => send({ reasoning_content: `${text}\n\n` }),
            startAnswer,
            finishAnswer,
        };
        reasoningFixture.append(reasoningIntro);
        return;
    }
    if (input.enable_thinking) send({ reasoning_content: `${reasoningIntro}\n\n${reasoningContinuation}` });
    startAnswer();
    finishAnswer();
});

const data = await mkdtemp(join(tmpdir(), 'chatraw-offline-'));
const plugins = join(data, 'plugins');
const installed = join(plugins, 'installed');
const markdownSettings = { enableCopyButton: false };
let browser;
let backend;
const blocked = [];
const failures = [];
try {
    await mkdir(installed, { recursive: true });
    for (const id of ['csv-parser', 'markdown-enhancer']) {
        await cp(join(root, 'Plugins/Plugin_market', id), join(installed, id), { recursive: true });
    }
    // Verify compatibility with the manifest persisted by existing installs.
    const csvPath = join(installed, 'csv-parser/manifest.json');
    const csvManifest = JSON.parse(await readFile(csvPath, 'utf8'));
    csvManifest.dependencies.papaparse = 'https://cdn.jsdelivr.net/npm/papaparse@5.4.1/papaparse.min.js';
    await writeFile(csvPath, JSON.stringify(csvManifest));
    // Older URL installs could copy listed libraries and omit nested fonts.
    const markdownPath = join(installed, 'markdown-enhancer/manifest.json');
    const markdownManifest = JSON.parse(await readFile(markdownPath, 'utf8'));
    markdownManifest.version = '1.0.0';
    await writeFile(markdownPath, JSON.stringify(markdownManifest));
    await rm(join(installed, 'markdown-enhancer/lib/fonts'), { recursive: true });
    await writeFile(join(plugins, 'config.json'), JSON.stringify({
        plugins: {
            'csv-parser': { enabled: true },
            'markdown-enhancer': { enabled: false, settings_values: markdownSettings },
        },
    }));

    provider.listen(0, '127.0.0.1');
    await once(provider, 'listening');
    backend = spawn(process.env.PYTHON || 'python3', [
        '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '0',
    ], {
        cwd: root,
        env: {
            ...process.env,
            DATA_DIR: data,
            CHATRAW_RUNNER_URL: 'http://127.0.0.1:51112',
            CHATRAW_RUNNER_TOKEN_FILE: '',
        },
        stdio: ['ignore', 'ignore', 'pipe'],
    });
    const origin = await new Promise((resolve, reject) => {
        let startup = '';
        const timeout = setTimeout(() => reject(new Error(`ChatRaw startup timed out\n${startup}`)), 15000);
        backend.once('error', error => {
            clearTimeout(timeout);
            reject(error);
        });
        backend.once('exit', code => {
            clearTimeout(timeout);
            reject(new Error(`ChatRaw exited with code ${code}\n${startup}`));
        });
        backend.stderr.on('data', chunk => {
            startup += chunk;
            const url = startup.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
            if (url) {
                clearTimeout(timeout);
                resolve(url);
            }
        });
    });
    const post = async (path, payload) => {
        const response = await fetch(origin + path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        assert.ok(response.ok, `${path} returned ${response.status}: ${await response.text()}`);
    };
    await post('/api/models', {
        id: 'default-chat',
        name: 'Offline fixture',
        api_url: `http://127.0.0.1:${provider.address().port}/v1`,
        model_id: 'offline-fixture',
        capability: { thinking_control: { request_format: 'enable_thinking' } },
    });

    browser = await chromium.launch({
        executablePath: browserPath,
        chromiumSandbox: process.env.CHROME_NO_SANDBOX !== '1',
        args: ['--disable-background-networking'],
    });
    const cdp = await browser.newBrowserCDPSession();
    const { product, revision } = await cdp.send('Browser.getVersion');
    console.log(`Browser reported: ${product} (${revision}, ${process.platform}/${process.arch})`);
    if (require109) assert.match(product, /\/109\./, 'This check requires an actual version 109 browser.');
    await cdp.detach();
    const context = await browser.newContext({ acceptDownloads: true, serviceWorkers: 'block' });
    const loaded = new Set();
    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== origin) {
            blocked.push(url.href);
            await route.abort();
        } else {
            await route.continue();
        }
    });

    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', error => failures.push(error.message));
    page.on('console', message => {
        if (message.type() === 'error') failures.push(message.text());
    });
    page.on('response', response => {
        const path = new URL(response.url()).pathname;
        if (response.ok()) loaded.add(path);
        else if (response.status() >= 400) failures.push(`${response.status()} ${path}`);
    });
    const send = async text => {
        await page.locator('textarea[x-ref="inputBox"]').fill(text);
        await page.locator('.btn-send:visible').click();
    };
    const market = page.locator('.plugin-modal');
    const installFromMarket = async (id, name, action = 'Install plugin') => {
        const card = market.locator('.plugin-card-market').filter({ has: page.getByText(name, { exact: true }) });
        const [response] = await Promise.all([
            page.waitForResponse(result =>
                new URL(result.url()).pathname === '/api/plugins/install-bundled'
                && result.request().method() === 'POST'
                && result.request().postDataJSON().plugin_id === id),
            card.getByRole('button', { name: action, exact: true }).click(),
        ]);
        const body = await response.json();
        assert.ok(response.ok() && body.success, `Bundled ${id}: ${JSON.stringify(body)}`);
        assert.equal(body.plugin_id, id);
        await page.waitForFunction(pluginId => {
            const state = Alpine.$data(document.body);
            return state.installedPlugins.some(plugin => plugin.id === pluginId) && !state.pluginInstalling;
        }, id);
    };
    await page.goto(origin);
    const marketIcon = page.waitForResponse(response =>
        response.ok() && /\/api\/plugins\/market\/[^/]+\/icon$/.test(new URL(response.url()).pathname));
    await page.locator('.btn-plugins:visible').click();
    await marketIcon;
    await installFromMarket('excel-parser', 'Excel Parser Pro');
    await installFromMarket('mindmap-renderer', 'Mindmap Renderer');
    await installFromMarket('enhanced-export', 'Enhanced Export');
    await installFromMarket('markdown-enhancer', 'Markdown Renderer Plus', 'Update plugin');
    const installedPlugins = await (await fetch(origin + '/api/plugins')).json();
    const upgraded = installedPlugins.find(plugin => plugin.id === 'markdown-enhancer');
    assert.notEqual(upgraded.version, markdownManifest.version);
    assert.equal(upgraded.enabled, false);
    assert.deepEqual(upgraded.settings_values, markdownSettings);
    await market.getByRole('button', { name: 'Close', exact: true }).click();
    console.log('Bundled market: three fresh installs, partial Markdown Enhancer upgrade and retained settings passed.');
    await page.waitForFunction(() => window.Papa && window.XLSX && window.html2pdf && window.markmap);
    await page.locator('.thinking-mode').selectOption('on');
    await send('Check normal chat without Markdown Enhancer');
    const assistant = page.locator('.message.assistant').filter({ has: page.locator('.message-actions') }).last();
    const thinkingHeader = assistant.getByRole('button', { name: 'Thinking Process' });
    const thinking = assistant.locator('.thinking-content');
    const waitForThinkingTail = async text => {
        await thinking.getByText(text, { exact: true }).waitFor();
        await page.waitForFunction(panel => {
            const tail = panel.querySelector('p:last-child').getBoundingClientRect();
            const visibleBottom = Math.min(panel.getBoundingClientRect().bottom, panel.closest('.messages').getBoundingClientRect().bottom);
            return panel.scrollHeight > panel.clientHeight &&
                panel.scrollHeight - panel.clientHeight - panel.scrollTop <= 1 && tail.bottom <= visibleBottom + 1;
        }, await thinking.elementHandle());
    };
    await thinking.getByText(reasoningIntro, { exact: true }).waitFor({ state: 'attached' });
    await thinkingHeader.click();
    reasoningFixture.append(reasoningContinuation);
    await waitForThinkingTail('Latest after opening');
    await thinkingHeader.click();
    await thinking.waitFor({ state: 'hidden' });
    await thinkingHeader.click();
    await waitForThinkingTail('Latest after opening');
    reasoningFixture.append('Latest while following');
    await waitForThinkingTail('Latest while following');

    await thinking.evaluate(panel => { panel.scrollTop = 120; });
    for (const text of ['Latest while reading earlier lines', 'Another line while reading earlier lines']) {
        reasoningFixture.append(text);
        await thinking.getByText(text, { exact: true }).waitFor();
        assert.equal(await thinking.evaluate(panel => panel.scrollTop), 120);
    }
    await thinking.evaluate(panel => { panel.scrollTop = panel.scrollHeight; });
    reasoningFixture.append('Latest after returning to the bottom');
    await waitForThinkingTail('Latest after returning to the bottom');
    await thinking.evaluate(panel => { panel.scrollTop = 0; });
    await thinkingHeader.click();
    await thinking.waitFor({ state: 'hidden' });
    reasoningFixture.startAnswer();
    await assistant.locator('.message-markdown h2').waitFor();
    await thinkingHeader.focus();
    await page.keyboard.press('Enter');
    await thinking.getByText('Offline reasoning fixture', { exact: true }).waitFor();
    assert.equal(await thinkingHeader.getAttribute('aria-expanded'), 'true');
    assert.equal(await thinking.evaluate(panel => panel.scrollTop), 0);
    await page.keyboard.press('Tab');
    assert.equal(await thinking.evaluate(panel => panel === document.activeElement), true);
    await page.keyboard.press('PageDown');
    await page.waitForFunction(panel => panel.scrollTop > 0, await thinking.elementHandle());
    await thinkingHeader.click();
    await thinking.waitFor({ state: 'hidden' });
    reasoningFixture.append('Latest when reasoning resumes after an answer delta');
    await thinking.getByText('Latest when reasoning resumes after an answer delta', { exact: true }).waitFor({ state: 'attached' });
    await thinkingHeader.click();
    await waitForThinkingTail('Latest when reasoning resumes after an answer delta');
    reasoningFixture.finishAnswer();

    await assistant.locator('table').waitFor({ state: 'visible' });
    await assistant.locator('code.language-python.hljs .hljs-keyword').first().waitFor({ state: 'visible' });
    const literal = assistant.locator('code.language-fixture-unknown');
    assert.equal((await literal.textContent()).trim(), '<strong>literal code</strong>');
    assert.equal(await literal.locator('strong').count(), 0);
    await page.waitForFunction(() => [...document.styleSheets].some(sheet => sheet.href?.endsWith('/github-dark.min.css')));
    assert.equal(await page.evaluate(() => [Alpine.version, hljs.versionString, XLSX.version].join(',')), '3.13.3,11.9.0,0.20.1');
    await page.reload();
    await assistant.locator('table').waitFor();
    assert.equal(await thinkingHeader.getAttribute('aria-expanded'), 'false');
    assert.doesNotMatch(await assistant.locator('.message-markdown').textContent(), /Offline reasoning fixture/);
    await thinkingHeader.click();
    await thinking.getByText('Offline reasoning fixture', { exact: true }).waitFor();
    assert.equal(await thinking.evaluate(panel => panel.scrollTop), 0);
    console.log('Thinking: live expansion, follow, pause, resume, keyboard, answer transition and history reload passed.');
    console.log('Core chat: streamed Markdown, table, syntax colors and escaped code passed.');

    await post('/api/plugins/markdown-enhancer/toggle', { enabled: true });
    await page.reload();
    await page.waitForFunction(() => window.Papa && window.katex && window.mermaid && window.markmap && window.html2pdf);
    await page.waitForFunction(() => Alpine.$data(document.body).pluginHooks.parse_document
        .some(hook => hook._pluginId === 'csv-parser'));
    await page.locator('.input-toolbar input[type="file"][accept*=".csv"]').setInputFiles({
        name: 'fixture.csv', mimeType: 'text/csv', buffer: Buffer.from('Name,Value\nlegacy,109\n'),
    });
    await page.locator('.attached-doc-name').waitFor({ state: 'visible' });
    await page.locator('.thinking-mode').selectOption('on');
    await send('Check plugins and parse the CSV');
    await assistant.locator('.katex').first().waitFor({ state: 'visible' });
    await assistant.locator('.mermaid-rendered .mermaid-shadow-host').first().waitFor({ state: 'visible' });
    await assistant.locator('.mindmap-rendered svg .markmap-node').first().waitFor({ state: 'visible' });
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    assert.ok([...loaded].some(path => /\/lib\/fonts\/KaTeX_.*\.woff2$/.test(path)), 'No KaTeX font served');
    assert.match(requests[1].messages.at(-1).content, /\| legacy \| 109 \|/);
    assert.equal(requests[1].messages.find(message => message.role === 'assistant').content, markdown);
    assert.equal(requests[1].enable_thinking, true);
    assert.equal('stream_options' in requests[1], false);

    await assistant.locator('.message-actions').waitFor();
    await thinkingHeader.click();
    await thinking.getByText('Offline reasoning fixture', { exact: true }).waitFor();
    assert.equal(await thinking.evaluate(panel => panel.scrollTop), 0);
    await thinkingHeader.click();
    await thinking.waitFor({ state: 'hidden' });
    console.log('Thinking: first expansion after completion starts at the top.');

    const pdfEvent = page.waitForEvent('download', download => download.suggestedFilename().endsWith('.pdf'));
    await assistant.locator('.btn-export-ee').click();
    const pdf = await pdfEvent;
    assert.equal((await readFile(await pdf.path())).subarray(0, 5).toString(), '%PDF-');
    console.log('Plugins: legacy CSV upload, KaTeX fonts, Mermaid, Markmap, PDF download and market icons passed.');

    const settings = await (await fetch(origin + '/api/settings')).json();
    settings.chat_settings.stream = false;
    await post('/api/settings', settings);
    await page.reload();
    await page.locator('.thinking-mode').waitFor({ state: 'visible' });
    assert.equal(await page.locator('.thinking-mode').inputValue(), 'default');
    await page.evaluate(() => {
        const state = Alpine.$data(document.body);
        state.pluginHooks.after_receive.unshift({ handler: message => {
            window.capturedThinkingMessage = message;
        } });
    });
    await send('Follow model default in non-streaming chat');
    const lastAnswer = assistant;
    const nonStreamingAnswer = lastAnswer.locator('.message-markdown').filter({ hasText: 'Non-streaming answer' });
    await nonStreamingAnswer.waitFor();
    assert.equal((await nonStreamingAnswer.textContent()).trim(), 'Non-streaming answer');
    await lastAnswer.getByRole('button', { name: 'Thinking Process' }).click();
    await lastAnswer.locator('.thinking-content').filter({ hasText: 'Fixture transient thought' }).waitFor();
    assert.equal(requests[2].stream, false);
    assert.equal('enable_thinking' in requests[2], false);
    await page.waitForFunction(() => window.capturedThinkingMessage?.content === 'Non-streaming answer');
    assert.deepEqual(await page.evaluate(() => ({
        thinking: window.capturedThinkingMessage.thinking,
        previewThinking: window.capturedThinkingMessage.previewThinking,
    })), { thinking: '', previewThinking: undefined });
    const chatId = await page.evaluate(() => Alpine.$data(document.body).currentChatId);
    const storedMessages = await (await fetch(origin + '/api/chats/' + chatId + '/messages')).json();
    assert.equal('thinking' in storedMessages.at(-1), false);

    await page.evaluate(() => Alpine.$data(document.body).pluginHooks.before_send.unshift({
        handler: body => ({ success: true, body: { ...body, use_thinking: true } }),
    }));
    await Promise.all([
        page.waitForResponse(response => new URL(response.url()).pathname === '/api/chat'),
        send('Legacy plugin overrides the thinking mode'),
    ]);
    await page.waitForFunction(() => !Alpine.$data(document.body).isGenerating);
    assert.equal(requests[3].enable_thinking, true);

    await page.evaluate(() => Alpine.$data(document.body).pluginHooks.before_send.unshift({
        handler: (body, { thinking_mode }) => ({ success: true, body: { ...body, use_thinking: true, thinking_mode } }),
    }));
    await Promise.all([
        page.waitForResponse(response => new URL(response.url()).pathname === '/api/chat'),
        send('Explicit new mode takes priority in a plugin'),
    ]);
    await page.waitForFunction(() => !Alpine.$data(document.body).isGenerating);
    assert.equal('enable_thinking' in requests[4], false);
    console.log('Thinking: non-streaming default, transient display, storage and legacy/new plugin precedence passed.');

    await page.locator('.btn-settings:visible').click();
    const modelForm = page.locator('.settings-modal:visible .model-card:visible');
    const policy = modelForm.locator('select[id^="thinking-control-"]');
    await policy.selectOption('default');
    await policy.selectOption('switchable');
    const requestFormat = modelForm.locator('.thinking-request select').first();
    await requestFormat.waitFor({ state: 'visible' });
    await page.evaluate(() => { Alpine.$data(document.body).settings.chat_settings.stream = true; });
    await page.locator('.settings-modal:visible .modal-actions-bar .btn-primary').click();
    await page.waitForFunction(() => Alpine.$data(document.body).toast.type === 'error');
    assert.equal(await policy.isVisible(), true);
    assert.equal(await requestFormat.inputValue(), '');
    assert.equal((await (await fetch(origin + '/api/settings')).json()).chat_settings.stream, false);

    const rejected = await fetch(origin + '/api/models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: 'default-chat', capability: { thinking_control: { request_format: '' } } }),
    });
    assert.equal(rejected.status, 422);

    await requestFormat.selectOption('template-enable');
    await page.locator('.settings-modal:visible .modal-actions-bar .btn-primary').click();
    await page.locator('.settings-modal:visible').waitFor({ state: 'hidden' });
    assert.equal((await (await fetch(origin + '/api/settings')).json()).chat_settings.stream, true);
    await page.setViewportSize({ width: 390, height: 844 });
    const control = page.locator('.thinking-mode');
    await control.waitFor({ state: 'visible' });
    const mobile = await control.evaluate(element => {
        const select = element.getBoundingClientRect();
        const send = document.querySelector('.btn-send').getBoundingClientRect();
        return select.left >= 0 && select.right < send.left && select.bottom <= innerHeight;
    });
    assert.equal(mobile, true);
    console.log('Settings: invalid thinking draft leaves saved settings intact, valid save applies, and the mobile selector fits.');

    assert.deepEqual(blocked, [], 'External browser requests were attempted');
    assert.deepEqual(failures, [], 'Browser or HTTP errors');
    if (process.env.OFFLINE_UI_SCREENSHOT) {
        await page.waitForFunction(() => !Alpine.$data(document.body).toast.show);
        await page.screenshot({ path: process.env.OFFLINE_UI_SCREENSHOT });
    }
    console.log('Zero external requests, HTTP errors or browser errors.');
} catch (error) {
    if (blocked.length || failures.length) console.error({ blocked, failures });
    throw error;
} finally {
    await browser?.close();
    if (backend && backend.exitCode === null) {
        const exited = once(backend, 'exit');
        if (backend.kill()) await exited;
    }
    provider.close();
    await rm(data, { recursive: true, force: true });
}
