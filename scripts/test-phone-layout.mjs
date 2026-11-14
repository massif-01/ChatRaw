// Real browser engines; viewport/keyboard geometry is simulated, not an iPhone hardware test.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startFixture } from './fixtures/browser-server.mjs';

const engine = process.env.CHATRAW_TEST_ENGINE || 'chromium';
const modulePath = process.env.CHATRAW_PLAYWRIGHT_MODULE;
const browsers = await import(modulePath ? pathToFileURL(resolve(modulePath)).href : 'playwright-core');
const executablePath = { chromium: process.env.CHROME_PATH, webkit: process.env.WEBKIT_PATH, firefox: process.env.FIREFOX_PATH }[engine];
const root = fileURLToPath(new URL('../', import.meta.url));
const fixture = await startFixture(fileURLToPath(new URL('./fixtures/agent-browser.py', import.meta.url)), { cwd: root });
let browser;
try {
    browser = await browsers[engine].launch({ executablePath });
    const page = await browser.newPage({ hasTouch: true, viewport: { width: 393, height: 684 } });
    page.setDefaultTimeout(5000);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.route('**/*', route => new URL(route.request().url()).origin === fixture.origin ? route.continue() : route.abort());
    for (const id of ['hermes', 'codex', 'claude', 'pi', 'deepseek']) {
        assert((await page.request.post(fixture.origin + '/api/plugins/install-bundled', { data: { plugin_id: id } })).ok());
    }
    for (let i = 0; i < 12; i++) assert((await page.request.post(fixture.origin + '/api/chats')).ok());
    await page.addInitScript(() => localStorage.setItem('justchat_lang', 'zh'));
    await page.goto(fixture.origin);
    await page.waitForFunction(() => window.Alpine?.$data(document.body).selectableAgents.length === 5);
    const evidence = process.env.CHATRAW_EVIDENCE_DIR;
    if (evidence) await mkdir(evidence, { recursive: true });
    const shot = async name => { if (evidence) await page.screenshot({ path: resolve(evidence, `${engine}-${name}.png`) }); };
    const state = async fn => page.evaluate(fn);
    const sidebar = page.locator('.sidebar');
    assert.equal(await sidebar.evaluate(el => getComputedStyle(el).boxShadow), 'none', 'Closed drawer shadow must not leak');
    const gap = await page.locator('.input-area').evaluate(el => parseFloat(getComputedStyle(el).paddingBottom));
    assert(gap <= 12, `Unnecessary composer bottom gap: ${gap}`);
    await shot('portrait');

    await page.locator('.agent-mode-button').click();
    const panel = page.locator('.agent-mode-panel');
    await panel.waitFor();
    await panel.locator('input[value="deepseek"]').check();
    await page.waitForFunction(() => window.Alpine.$data(document.body).agentMenuChoice === 'deepseek');
    await panel.locator('.agent-workspace').waitFor();
    assert((await panel.locator('.agent-workspace select').boundingBox()).height >= 44, 'Workspace selector needs a 44px touch target');
    const row = panel.locator('.agent-option').last();
    const centers = await row.evaluate(el => {
        const box = el.getBoundingClientRect();
        const label = el.querySelector('span').getBoundingClientRect();
        const radio = el.querySelector('input').getBoundingClientRect();
        return [box.y + box.height / 2, label.y + label.height / 2, radio.y + radio.height / 2];
    });
    assert(Math.max(...centers) - Math.min(...centers) <= 1, JSON.stringify(centers));
    const overflow = await panel.evaluate(el => el.scrollHeight - el.clientHeight);
    assert(overflow <= 1, `Portrait Agent/workspace menu should fit: overflow ${overflow}`);
    await shot('agent-workspace');
    await page.keyboard.press('Escape');

    await state(() => window.Alpine.$data(document.body).openSettingsPanel());
    const settings = page.locator('.modal-overlay').filter({ has: page.locator('#settings-modal-title') });
    await settings.waitFor();
    await page.waitForFunction(() => {
        const modal = document.getElementById('settings-modal-title').closest('.modal-overlay');
        const outer = modal.getBoundingClientRect();
        const inner = modal.querySelector('.settings-modal').getBoundingClientRect();
        return Math.abs(inner.top - outer.top) <= 1 && Math.abs(inner.bottom - outer.bottom) <= 1;
    });
    const edges = await settings.evaluate(el => {
        const outer = el.getBoundingClientRect();
        const inner = el.querySelector('.settings-modal').getBoundingClientRect();
        return [inner.top - outer.top, outer.bottom - inner.bottom];
    });
    assert(edges.every(value => Math.abs(value) <= 1), `Settings backdrop strips: ${edges}`);
    await shot('settings');
    await settings.getByRole('button', { name: '取消', exact: true }).click();
    await settings.waitFor({ state: 'hidden' });

    await page.setViewportSize({ width: 852, height: 283 });
    await page.waitForFunction(() => document.documentElement.style.getPropertyValue('--visual-height') === '283px');
    await state(() => window.Alpine.$data(document.body).sidebarCollapsed = false);
    await page.locator('.chat-list').waitFor();
    const list = await page.locator('.chat-list').boundingBox();
    assert(list.height >= 88, 'Landscape conversation list collapsed');
    assert(await sidebar.evaluate(el => el.scrollHeight > el.clientHeight), 'Whole short drawer must scroll');
    await sidebar.evaluate(el => { el.scrollTop = el.scrollHeight; });
    const settingsButton = sidebar.locator('.btn-settings');
    const bounds = await settingsButton.boundingBox();
    assert(bounds.y >= 0 && bounds.y + bounds.height <= 284, JSON.stringify(bounds));
    await shot('landscape-drawer-bottom');
    await settingsButton.click();
    await settings.waitFor();
    await settings.getByRole('button', { name: '取消', exact: true }).click();
    await settings.waitFor({ state: 'hidden' });

    await page.setViewportSize({ width: 393, height: 684 });
    await page.locator('textarea').first().focus();
    await page.evaluate(() => {
        Object.defineProperties(window.visualViewport, {
            height: { configurable: true, value: 360 }, offsetTop: { configurable: true, value: 20 }
        });
        window.visualViewport.dispatchEvent(new Event('resize'));
    });
    await page.waitForFunction(() => document.documentElement.style.getPropertyValue('--visual-height') === '360px');
    const input = await page.locator('.input-wrapper').boundingBox();
    assert(input.y + input.height <= 380 && 380 - (input.y + input.height) <= 12, JSON.stringify(input));
    await shot('simulated-keyboard');
    console.log(engine, browser.version(), 'phone regression passed', { gap, centers, overflow, edges });
} finally {
    await browser?.close();
    await fixture.stop();
}
