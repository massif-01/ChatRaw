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
    response.writeHead(200, { 'Content-Type': 'text/event-stream' });
    const send = delta => response.write(`data: ${JSON.stringify({ choices: [{ delta }] })}\n\n`);
    if (input.enable_thinking) send({ reasoning_content: 'Offline reasoning fixture' });
    send({ content: content.slice(0, 37) });
    send({ content: content.slice(37) });
    response.end('data: [DONE]\n\n');
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
    await page.locator('.thinking-toggle').click();
    await send('Check normal chat without Markdown Enhancer');
    const assistant = page.locator('.message.assistant').filter({ has: page.locator('.message-actions') }).last();
    await assistant.locator('table').waitFor({ state: 'visible' });
    await assistant.locator('.thinking-header').click();
    await assistant.locator('.thinking-content').getByText('Offline reasoning fixture').waitFor({ state: 'visible' });
    await assistant.locator('code.language-python.hljs .hljs-keyword').first().waitFor({ state: 'visible' });
    const literal = assistant.locator('code.language-fixture-unknown');
    assert.equal((await literal.textContent()).trim(), '<strong>literal code</strong>');
    assert.equal(await literal.locator('strong').count(), 0);
    await page.waitForFunction(() => [...document.styleSheets].some(sheet => sheet.href?.endsWith('/github-dark.min.css')));
    assert.equal(await page.evaluate(() => [Alpine.version, hljs.versionString, XLSX.version].join(',')), '3.13.3,11.9.0,0.20.1');
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
    await send('Check plugins and parse the CSV');
    await assistant.locator('.katex').first().waitFor({ state: 'visible' });
    await assistant.locator('.mermaid-rendered .mermaid-shadow-host').first().waitFor({ state: 'visible' });
    await assistant.locator('.mindmap-rendered svg .markmap-node').first().waitFor({ state: 'visible' });
    await page.evaluate(() => document.fonts.ready.then(() => undefined));
    assert.ok([...loaded].some(path => /\/lib\/fonts\/KaTeX_.*\.woff2$/.test(path)), 'No KaTeX font served');
    assert.match(requests[1].messages.at(-1).content, /\| legacy \| 109 \|/);

    const pdfEvent = page.waitForEvent('download', download => download.suggestedFilename().endsWith('.pdf'));
    await assistant.locator('.btn-export-ee').click();
    const pdf = await pdfEvent;
    assert.equal((await readFile(await pdf.path())).subarray(0, 5).toString(), '%PDF-');
    console.log('Plugins: legacy CSV upload, KaTeX fonts, Mermaid, Markmap, PDF download and market icons passed.');

    assert.deepEqual(blocked, [], 'External browser requests were attempted');
    assert.deepEqual(failures, [], 'Browser or HTTP errors');
    if (process.env.OFFLINE_UI_SCREENSHOT) {
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
