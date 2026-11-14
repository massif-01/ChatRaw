import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startFixture } from './fixtures/browser-server.mjs';

const engine = process.env.CHATRAW_TEST_ENGINE || 'chromium';
const executablePath = engine === 'firefox' ? process.env.FIREFOX_PATH : process.env.CHROME_PATH;
const playwright = process.env.CHATRAW_PLAYWRIGHT_MODULE
    ? pathToFileURL(resolve(process.env.CHATRAW_PLAYWRIGHT_MODULE)).href
    : 'playwright-core';
const browsers = await import(playwright);
const root = fileURLToPath(new URL('../', import.meta.url));
const fixture = await startFixture(fileURLToPath(new URL('./fixtures/agent-browser.py', import.meta.url)), { cwd: root });
let browser;
try {
    browser = await browsers[engine].launch({ executablePath });
    const touch = process.env.CHATRAW_TEST_TOUCH === '1';
    const page = await browser.newPage({ hasTouch: touch, viewport: { width: 1280, height: 860 } });
    page.setDefaultTimeout(5000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => new URL(route.request().url()).origin === fixture.origin ? route.continue() : route.abort());

    async function post(path, data) {
        const response = await page.request.post(fixture.origin + path, { data });
        assert(response.ok(), path + ' returned ' + response.status());
        return response.json();
    }

    for (const id of ['hermes', 'codex', 'claude', 'pi', 'deepseek']) {
        await post('/api/plugins/install-bundled', { plugin_id: id });
    }
    const chat = await post('/api/chats');
    const binding = await page.request.put(fixture.origin + '/api/chats/' + chat.id + '/agent', {
        data: { agent_id: 'codex', workspace: { kind: 'managed' } }
    });
    assert(binding.ok());
    await page.addInitScript(id => localStorage.setItem('chatraw-selected-chat', id), chat.id);
    await page.goto(fixture.origin);

    const button = page.getByRole('button', { name: 'Chat mode — Codex CLI' });
    const panel = page.locator('.agent-mode-panel');
    const apply = panel.getByRole('button', { name: 'Apply', exact: true });
    // The app loads installed plugin scripts during startup.
    await page.waitForFunction(() => window.Alpine.$data(document.body).selectableAgents.length === 5);
    const evidence = process.env.CHATRAW_EVIDENCE_DIR;
    if (evidence) await mkdir(evidence, { recursive: true });

    async function checkBounds(width, top, bottom, requireScroll = false) {
        const geometry = await panel.evaluate(el => {
            const bounds = el.getBoundingClientRect();
            return {
                left: bounds.left, right: bounds.right, top: bounds.top, bottom: bounds.bottom,
                client: el.clientHeight, scroll: el.scrollHeight
            };
        });
        assert(geometry.left >= 0 && geometry.right <= width && geometry.top >= top - 1 &&
            geometry.bottom <= bottom + 1 && geometry.client > 0, JSON.stringify(geometry));
        if (requireScroll) assert(geometry.scroll > geometry.client, 'Short viewport must scroll inside the menu');
        return geometry;
    }

    const viewports = [[1280, 860], [320, 740], [375, 740], [390, 844], [430, 844], [740, 320]];
    if (touch) viewports.push([844, 320]);
    for (const [width, height] of viewports) {
        await page.setViewportSize({ width, height });
        await button.focus();
        await page.keyboard.press('Enter');
        await panel.waitFor();
        await panel.getByRole('radio', { name: 'DeepSeek Harness', exact: true }).waitFor();
        await page.waitForFunction(() => document.activeElement.matches('.agent-mode-panel input:checked'));
        const geometry = await checkBounds(width, 0, height, height === 320);
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');
        assert(await apply.evaluate(el => document.activeElement === el), 'Apply must be reachable by Tab');
        await page.waitForFunction(el => {
            const bounds = el.getBoundingClientRect();
            const parent = el.closest('.agent-mode-panel').getBoundingClientRect();
            return bounds.top >= parent.top - 1 && bounds.bottom <= parent.bottom + 1;
        }, await apply.elementHandle());
        if (evidence && height === 320) await page.screenshot({ path: resolve(evidence, engine + '-landscape-' + width + '.png') });
        await page.keyboard.press('Escape');
        await panel.waitFor({ state: 'hidden' });
        assert(await button.evaluate(el => document.activeElement === el), 'Escape must restore focus to the menu button');
        console.log(width + '×' + height, JSON.stringify(geometry));
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await button.click();
    await panel.waitFor();
    await page.evaluate(() => {
        Object.defineProperties(window.visualViewport, {
            height: { configurable: true, value: 320 },
            offsetTop: { configurable: true, value: 22 }
        });
        window.visualViewport.dispatchEvent(new Event('resize'));
    });
    await page.waitForFunction(() => document.documentElement.style.getPropertyValue('--visual-height') === '320px');
    const geometry = await checkBounds(390, 22, 342, true);
    if (evidence) await page.screenshot({ path: resolve(evidence, engine + '-simulated-keyboard.png') });
    await apply.click();
    await panel.waitFor({ state: 'hidden' });
    assert(await button.evaluate(el => document.activeElement === el));
    assert.deepEqual(errors, []);
    console.log(engine + ' ' + browser.version() + ' passed, simulated keyboard bounds', JSON.stringify(geometry));
} finally {
    await browser?.close();
    await fixture.stop();
}
