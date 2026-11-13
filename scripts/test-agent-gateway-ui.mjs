import assert from 'node:assert/strict';
import { mkdir, mkdtemp, readdir, readFile, rm } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { startFixture } from './fixtures/browser-server.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const code = process.env.CHATRAW_GATEWAY_CODE_ROOT || root;
const evidence = process.env.CHATRAW_EVIDENCE_DIR || resolve(root, 'outputs', 'agent-gateway-ui');
await mkdir(evidence, { recursive: true });
const engine = process.env.CHATRAW_TEST_ENGINE || 'chromium';
const playwright = process.env.CHATRAW_PLAYWRIGHT_MODULE
    ? pathToFileURL(resolve(process.env.CHATRAW_PLAYWRIGHT_MODULE)).href
    : 'playwright-core';
const browsers = await import(playwright);
const executablePath = engine === 'firefox' ? process.env.FIREFOX_PATH : process.env.CHROME_PATH;
const browser = await browsers[engine].launch({ executablePath });
const state = await mkdtemp(resolve(evidence, 'state-'));
let fixture;
try {
    fixture = await startFixture(fileURLToPath(new URL('./fixtures/agent-browser-gateway.py', import.meta.url)), {
        cwd: code, env: { PYTHONPATH: code, CHATRAW_GATEWAY_TEST_STATE: state }
    });
} catch (error) {
    await browser.close();
    await rm(state, { recursive: true, force: true });
    throw error;
}
const { origin } = fixture;
const errors = [];
const writes = [];
async function createContext() {
    const context = await browser.newContext({ viewport: { width: 1120, height: 800 } });
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage();
    page.setDefaultTimeout(8000);
    page.on('pageerror', error => errors.push(error.stack));
    page.on('request', request => {
        if (request.method() !== 'GET' && request.headers()['content-type']?.includes('application/json')) {
            writes.push({ path: new URL(request.url()).pathname, payload: request.postDataJSON() });
        }
    });
    return { page, context };
}

try {
    const first = await createContext();
    const { page } = first;
    await page.goto(origin);
    await page.locator('.btn-plugins').click();
    const modal = page.locator('.plugin-modal');
    await modal.locator('.plugin-card').filter({ has: page.getByText('Hermes', { exact: true }) })
        .getByRole('button', { name: 'Install plugin' }).click();
    await modal.getByRole('tab', { name: 'Installed', exact: true }).click();
    await modal.locator('.plugin-card:visible').filter({ has: page.getByText('Hermes', { exact: true }) }).getByTitle('Settings').click();
    const settings = page.locator('.plugin-settings-modal');
    await settings.getByLabel('Model', { exact: true }).fill('gateway-model');
    await settings.getByRole('button', { name: 'Check Agent' }).click();
    await settings.getByText('controlled-adapter', { exact: false }).waitFor();
    await settings.getByRole('button', { name: 'Save', exact: true }).click();
    await settings.waitFor({ state: 'hidden' });
    await modal.getByRole('button', { name: 'Close', exact: true }).click();

    await page.locator('.agent-mode-button').click();
    await page.locator('.agent-mode-panel').getByRole('radio', { name: 'Hermes', exact: true }).check();
    await page.locator('.agent-mode-panel').getByRole('button', { name: 'Apply', exact: true }).click();
    await page.getByRole('button', { name: 'Chat mode — Hermes' }).waitFor();
    await page.locator('input[x-ref=agentFileInput]').setInputFiles({
        name: 'evidence.txt', mimeType: 'text/plain', buffer: Buffer.from('browser gateway attachment')
    });
    await page.locator('.agent-attachments').getByText('evidence.txt').waitFor();
    await page.locator('.input-wrapper textarea').fill('approval');
    await page.getByRole('button', { name: 'send', exact: true }).click();
    await page.locator('.agent-request:visible').filter({ hasText: 'Write a file?' }).waitFor();
    const chat = await page.evaluate(() => localStorage.getItem('chatraw-selected-chat'));
    await first.context.close();

    const second = await createContext();
    await second.page.goto(origin);
    await second.page.locator('.chat-select').first().click();
    await second.page.locator('.agent-request:visible').filter({ hasText: 'Write a file?' }).click();
    const approval = second.page.getByRole('dialog', { name: 'Write a file?' });
    await approval.getByRole('radio', { name: 'Allow', exact: true }).check();
    assert.equal(writes.filter(item => item.path.endsWith('/reply')).length, 0);
    await approval.getByRole('button', { name: 'Send response' }).click();
    await approval.getByRole('button', { name: 'Close', exact: true }).click();
    await second.page.getByText('FINAL', { exact: true }).waitFor();
    assert.equal(await second.page.getByText('partial', { exact: true }).count(), 0);

    const stored = await second.page.evaluate(chatId => fetch('/api/chats/' + chatId + '/messages').then(r => r.json()), chat);
    const waitForProjection = async () => second.page.waitForFunction(async chatId => {
        const rows = await fetch('/api/chats/' + chatId + '/messages').then(r => r.json());
        return rows.filter(row => row.role === 'assistant' && row.content === 'FINAL').length === 1;
    }, chat);
    if (!stored.some(row => row.role === 'assistant')) await waitForProjection();
    await second.page.reload();
    await second.page.getByText('FINAL', { exact: true }).waitFor();
    assert.equal(await second.page.getByText('FINAL', { exact: true }).count(), 1);
    const body = writes.find(item => item.path === '/api/agents/runs')?.payload;
    assert.equal(body.message, 'approval');
    assert.deepEqual(Object.keys(body).sort(), ['attachments', 'chat_id', 'client_request_id', 'message']);
    assert.equal(body.attachments.length, 1);
    assert.equal(writes.filter(item => item.path.endsWith('/reply')).length, 1);
    assert.equal(writes.filter(item => item.path.endsWith('/cancel')).length, 0);
    assert.deepEqual(errors, []);
    await second.page.screenshot({ path: resolve(evidence, 'real-gateway-controlled-adapter.png') });

    const workspaces = await readdir(resolve(state, 'runner', 'workspaces'), { recursive: true });
    const approved = workspaces.find(file => file.endsWith('approved.txt'));
    assert(approved);
    assert.equal(await readFile(resolve(state, 'runner', 'workspaces', approved), 'utf8'), 'native action executed');
    console.log('Real ChatRaw gateway and Runner,', engine, browser.version(), 'local install/settings/attachment, tab close, second-device approval, final projection and reload passed; ControlledAdapter receiver');
} catch (error) {
    console.error(errors);
    throw error;
} finally {
    await browser.close();
    await fixture.stop();
    await rm(state, { recursive: true, force: true });
}
