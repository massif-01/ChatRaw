import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const origin = new URL(process.env.CHATRAW_TEST_URL).origin;
const chat = process.env.CHATRAW_TEST_CHAT_ID;
assert.ok(chat, 'Set CHATRAW_TEST_CHAT_ID to a dedicated acceptance chat.');
const evidenceDir = resolve(process.env.CHATRAW_EVIDENCE_DIR || 'outputs/firefox-deployed');
await mkdir(evidenceDir, { recursive: true });
const playwright = process.env.CHATRAW_PLAYWRIGHT_MODULE
    ? pathToFileURL(resolve(process.env.CHATRAW_PLAYWRIGHT_MODULE)).href
    : 'playwright-core';
const { firefox } = await import(playwright);
const browser = await firefox.launch({ executablePath: process.env.FIREFOX_PATH });
const evidence = {
    origin, chat, version: browser.version(), platform: process.platform, arch: process.arch,
    resources: {}, errors: [], external: [], writes: [], layouts: [],
};
const sha256 = text => createHash('sha256').update(text).digest('hex');
try {
    const context = await browser.newContext({ viewport: { width: 1180, height: 800 } });
    await context.addInitScript(({ origin, chat }) => {
        if (location.origin === origin) localStorage.setItem('chatraw-selected-chat', chat);
    }, { origin, chat });
    await context.route('**/*', route => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.origin !== origin) {
            evidence.external.push(url.origin + url.pathname);
            return route.abort();
        }
        if (!['GET', 'HEAD'].includes(request.method())) {
            evidence.writes.push(request.method() + ' ' + url.pathname);
            return route.abort();
        }
        return route.continue();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(18000);
    page.on('pageerror', error => evidence.errors.push(error.message));
    page.on('console', message => {
        if (message.type() === 'error') evidence.errors.push(message.text());
    });
    page.on('response', response => {
        const url = new URL(response.url());
        if (!url.pathname.startsWith('/api/')) evidence.resources[url.pathname] = response.status();
        if (response.status() >= 400) evidence.errors.push(response.status() + ' ' + url.pathname);
    });

    const agentScript = page.waitForResponse(response => new URL(response.url()).pathname === '/agents.js');
    const document = await page.goto(origin);
    assert.ok(document.ok());
    evidence.assets = {
        index: sha256(await document.text()),
        agents: sha256(await (await agentScript).text()),
    };
    await page.getByRole('button', { name: 'Chat mode — Codex CLI' }).waitFor();
    const reply = page.locator('.message.assistant .message-markdown');
    await reply.getByText('E109-UI-OK', { exact: true }).waitFor();
    assert.equal(await reply.locator('li').count(), 6);
    const details = page.locator('.message.assistant .agent-run-details');
    await details.locator('summary').click();
    await details.getByText('No additional details for this run.', { exact: true }).waitFor();
    const getMessages = () => page.evaluate(id => fetch('/api/chats/' + id + '/messages').then(response => {
        if (!response.ok) throw new Error('Could not read acceptance chat');
        return response.json();
    }), chat);
    const messages = await getMessages();
    const originals = messages.filter(row => row.role === 'assistant');
    assert.equal(originals.length, 1);
    assert.match(originals[0].content, /\*\*E109-UI-OK\*\*/);
    evidence.run = originals[0].run_id;
    evidence.originalSha256 = sha256(originals[0].content);
    await page.evaluate(() => {
        document.addEventListener('copy', event => {
            const input = document.activeElement;
            window.acceptanceCopy = input instanceof HTMLTextAreaElement
                ? input.value.slice(input.selectionStart, input.selectionEnd)
                : window.getSelection()?.toString();
            event.preventDefault();
        }, { once: true, capture: true });
    });
    await page.locator('.message.assistant').getByRole('button', { name: 'Copy', exact: true }).click();
    assert.equal(await page.evaluate(() => window.acceptanceCopy), originals[0].content);
    evidence.copyMatches = true;
    await page.screenshot({ path: resolve(evidenceDir, 'deployed-replay.png') });

    const menu = page.locator('.agent-mode-panel');
    const layoutFailures = [];
    for (const [width, height] of [[320, 740], [390, 844], [740, 320]]) {
        await page.setViewportSize({ width, height });
        await page.locator('.agent-mode-button').click();
        const options = ['Ordinary chat', 'Hermes', 'Codex CLI', 'Claude Code', 'Pi', 'DeepSeek Harness'];
        for (const name of options) await menu.getByRole('radio', { name, exact: true }).waitFor();
        const box = await menu.evaluate(element => {
            const bounds = element.getBoundingClientRect();
            const old = element.scrollTop;
            element.scrollTop = element.scrollHeight;
            const scroll = element.scrollTop;
            element.scrollTop = old;
            return {
                x: bounds.x, right: bounds.right, y: bounds.y, bottom: bounds.bottom,
                width: innerWidth, height: innerHeight, rootWidth: document.documentElement.scrollWidth,
                scrollWidth: element.scrollWidth, clientWidth: element.clientWidth,
                scrollHeight: element.scrollHeight, clientHeight: element.clientHeight, scroll,
                pointerCoarse: matchMedia('(pointer: coarse)').matches,
                visualHeight: window.visualViewport?.height,
                maxHeight: getComputedStyle(element).maxHeight,
            };
        });
        evidence.layouts.push({ width, height, box });
        await page.screenshot({ path: resolve(evidenceDir, 'deployed-menu-' + width + '.png') });
        if (box.x < -1 || box.right > width + 1 || box.y < -1 || box.bottom > height + 1) {
            layoutFailures.push(`${width}×${height}: menu outside viewport`);
        }
        if (box.rootWidth > width + 1 || box.scrollWidth > box.clientWidth + 1) {
            layoutFailures.push(`${width}×${height}: horizontal overflow`);
        }
        if (box.scrollHeight > box.clientHeight + 1 && box.scroll <= 0) {
            layoutFailures.push(`${width}×${height}: clipped menu cannot scroll`);
        }
        await menu.getByRole('radio', { name: 'Codex CLI', exact: true }).press('Escape');
        await menu.waitFor({ state: 'hidden' });
    }
    for (const path of [
        '/', '/agents.js', '/stream-markdown.js', '/app.min.js', '/styles.min.css',
        '/vendor/alpinejs/3.13.3/alpine.min.js', '/vendor/marked/9.1.6/marked.min.js',
        '/vendor/collapse/3.13.3/collapse.min.js', '/fonts/remixicon/remixicon.woff2',
    ]) assert.equal(evidence.resources[path], 200, path);
    assert.deepEqual(await getMessages(), messages);
    assert.deepEqual(evidence.writes, []);
    assert.deepEqual(evidence.external, []);
    assert.deepEqual(evidence.errors, []);
    evidence.layoutFailures = layoutFailures;
    assert.deepEqual(layoutFailures, []);
    console.log('Firefox', browser.version(), 'deployed resources, existing Codex Markdown replay, copy event, run details and three narrow layouts passed; zero external requests or writes');
} catch (error) {
    evidence.failure = error.message;
    throw error;
} finally {
    await writeFile(resolve(evidenceDir, 'deployed-readonly.json'), JSON.stringify(evidence, null, 2) + '\n');
    await browser.close();
}
