import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';
import { startFixture } from './fixtures/browser-server.mjs';
const root = fileURLToPath(new URL('../', import.meta.url));
const fixture = await startFixture(fileURLToPath(new URL('./fixtures/agent-browser.py', import.meta.url)), { cwd: root });
let browser;
try {
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
    const page = await browser.newPage({ viewport: { width: 1280, height: 850 } });
    page.setDefaultTimeout(5000);
    await page.route('**/*', route => new URL(route.request().url()).origin === fixture.origin ? route.continue() : route.abort());
    const locked = await (await page.request.post(fixture.origin + '/api/chats')).json();
    const ordinary = await (await page.request.post(fixture.origin + '/api/chats')).json();
    let code = 'chat_run_unverified';
    await page.route(fixture.origin + '/api/chats/' + locked.id, route => route.request().method() === 'DELETE'
        ? route.fulfill({ status: 409, json: { detail: { code, message: 'Server reason' } } }) : route.fallback());
    await page.addInitScript(() => localStorage.setItem('justchat_lang', 'zh'));
    await page.goto(fixture.origin);
    const deleteButton = page.getByRole('button', { name: '删除 ' + locked.title, exact: true });
    for (const [reason, expected] of [
        ['chat_run_unverified', '请由管理员核实原生任务已停止'],
        ['chat_run_active', '请先停止任务或等待任务结束'],
        ['chat_binding_unverified', 'Agent 绑定尚未核实'],
        ['chat_submission_unverified', 'Agent 提交回执尚未确认']
    ]) {
        code = reason;
        await deleteButton.click();
        await page.waitForFunction(text => document.querySelector('.toast').textContent.includes(text), expected);
        assert((await page.request.get(fixture.origin + '/api/chats')).ok());
    }
    code = 'chat_run_unverified';
    page.once('dialog', dialog => dialog.accept());
    await page.locator('.btn-clear-all').click();
    await page.waitForFunction(() => document.querySelector('.toast').textContent.includes('有 1 个对话未删除'));
    assert((await page.locator('.toast').textContent()).includes('请由管理员核实'));
    const remaining = await (await page.request.get(fixture.origin + '/api/chats')).json();
    assert(remaining.some(chat => chat.id === locked.id));
    assert(!remaining.some(chat => chat.id === ordinary.id));
    console.log('Deletion feedback passed: four blocking reasons, partial clear preserves only locked chat.');
} finally {
    await browser?.close();
    await fixture.stop();
}
