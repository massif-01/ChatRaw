import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { fileURLToPath } from 'node:url';
import { startFixture } from './fixtures/browser-server.mjs';
import { mkdir, writeFile } from 'node:fs/promises';
const root = fileURLToPath(new URL('../', import.meta.url));
const evidence = process.env.CHATRAW_EVIDENCE_DIR || root + 'outputs/agent-ui';
await mkdir(evidence, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || undefined, headless: true });
let fixture;
try {
    fixture = await startFixture(fileURLToPath(new URL('./fixtures/agent-browser.py', import.meta.url)), { cwd: root });
} catch (error) {
    await browser.close();
    throw error;
}
const { origin } = fixture;
const context = await browser.newContext({ hasTouch: true, viewport: { width: 1280, height: 860 }, acceptDownloads: true });
await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
const page = await context.newPage();
page.setDefaultTimeout(7000);
const errors = [];
let stage = 'install';
page.on('pageerror', error => errors.push(stage + ': ' + (error.stack || error.message)));
page.on('console', msg => { if (msg.type() === 'error' && !msg.text().includes('503')) errors.push(msg.text()); });
page.on('dialog', dialog => dialog.accept());
const mode = page.locator('.agent-mode-button');
const composer = page.locator('.input-wrapper textarea');
const settle = selector => page.locator(selector).waitFor({ state: 'visible' });
const logs = async () => (await page.request.get(origin + '/fixture/logs')).json();
const names = ['Hermes', 'Codex CLI', 'Claude Code', 'Pi', 'DeepSeek Harness'];

try {
    await page.goto(origin);
    await page.locator('.btn-plugins').click();
    const pluginModal = page.locator('.plugin-modal');
    for (const name of names) {
        const card = pluginModal.locator('.plugin-card').filter({ has: page.getByText(name, { exact: true }) });
        const install = card.getByRole('button', { name: 'Install plugin' });
        if (await install.isEnabled()) {
            await install.click();
            await page.waitForFunction(el => el.disabled && el.title !== 'Installing...', await install.elementHandle());
        }
    }
    await pluginModal.getByRole('tab', { name: 'Installed', exact: true }).click();
    stage = 'settings';
    for (const [index, name] of names.entries()) {
        await page.setViewportSize({ width: [320, 375, 390, 430, 320][index], height: 740 });
        const card = pluginModal.locator('.plugin-card:visible').filter({ has: page.getByText(name, { exact: true }) });
        await card.getByTitle('Settings').click();
        const pluginSettings = page.locator('.plugin-settings-modal');
        await pluginSettings.getByRole('button', { name: 'Check Agent' }).click();
        await pluginSettings.getByText('fixture-v1', { exact: false }).waitFor();
        assert.equal(await pluginSettings.getByText('Not checked', { exact: true }).count(), 1);
        await pluginSettings.getByLabel('Model', { exact: true }).fill('fixture-model-' + index);
        await pluginSettings.getByRole('combobox', { name: 'level', exact: true }).selectOption({ label: 'high' });
        await pluginSettings.getByRole('combobox', { name: 'trace', exact: true }).selectOption('false');
        await pluginSettings.getByRole('spinbutton', { name: 'budget', exact: true }).fill('4');
        assert.equal(await pluginSettings.locator('#agent-model-options option').count(), 1);
        const bounds = await pluginSettings.boundingBox();
        assert(bounds.x >= 0 && bounds.x + bounds.width <= page.viewportSize().width + 1);
        if (name === 'DeepSeek Harness') await page.screenshot({ path: evidence + '/mobile-settings-320.png' });
        await pluginSettings.getByRole('button', { name: 'Save', exact: true }).click();
        await pluginSettings.waitFor({ state: 'hidden' });
        const saved = (await logs()).filter(row => String(row[1]).endsWith('/settings')).at(-1)[2].settings;
        assert.deepEqual(saved, { model: 'fixture-model-' + index, level: 'high', trace: false, budget: 4 });
        await card.getByTitle('Settings').click();
        assert.equal(await pluginSettings.getByLabel('Model', { exact: true }).inputValue(), 'fixture-model-' + index);
        await pluginSettings.getByRole('button', { name: 'Cancel', exact: true }).click();
    }
    await pluginModal.getByRole('button', { name: 'Close', exact: true }).click();

    stage = 'mode';
    await page.setViewportSize({ width: 320, height: 740 });
    await mode.click();
    assert.equal(await page.locator('.agent-mode-panel input[type=radio]').count(), 6);
    const modePanel = page.locator('.agent-mode-panel');
    await modePanel.waitFor();
    await page.locator('.toast').waitFor({ state: 'hidden' });
    const panel = await modePanel.boundingBox();
    assert(panel.x >= 0 && panel.x + panel.width <= 321);
    await page.screenshot({ path: evidence + '/mobile-agent-menu-320.png' });
    await modePanel.getByRole('radio', { name: 'Codex CLI', exact: true }).check();
    await modePanel.getByRole('combobox', { name: 'Workspace' }).selectOption('chatraw-fixture');
    await modePanel.getByRole('button', { name: 'Apply', exact: true }).click();
    await page.getByRole('button', { name: 'Chat mode — Codex CLI' }).waitFor();

    await page.locator('input[type=file][x-ref=agentFileInput]').setInputFiles({
        name: 'input.txt', mimeType: 'text/plain', buffer: Buffer.from('demo')
    });
    await page.locator('.agent-attachments').getByText('input.txt').waitFor();
    stage = 'agent run';
    await composer.fill('lost-admission /skill install fixture');
    assert.equal(await page.locator('.composer-suggestions:visible').count(), 0);
    await page.getByRole('button', { name: 'send', exact: true }).click();
    await page.locator('.agent-request:visible').filter({ hasText: 'Choose how to run the checks' }).waitFor();
    const body = (await logs()).filter(row => row[1] === '/api/agents/runs');
    assert.equal(body.length, 1);
    assert.deepEqual(Object.keys(body[0][2]).sort(), ['attachments', 'chat_id', 'client_request_id', 'message']);
    assert.deepEqual(body[0][2].attachments, [{ attachment_id: 'fixture-file' }]);
    assert.equal(body[0][2].message, 'lost-admission /skill install fixture');
    assert((await logs()).some(row => row[0] === 'reconnect' && row[2] > 0));

    await composer.fill('Keep this draft while waiting');
    await composer.press('Enter');
    assert.equal(await composer.inputValue(), 'Keep this draft while waiting');
    assert.equal((await logs()).filter(row => row[1] === '/api/agents/runs').length, 1);

    await page.setViewportSize({ width: 390, height: 740 });
    await page.locator('.agent-request:visible').filter({ hasText: 'Choose how to run the checks' }).click();
    const question = page.getByRole('dialog', { name: 'Choose how to run the checks' });
    assert.equal(await question.getByRole('button', { name: 'Send response' }).isEnabled(), false);
    assert.equal(await question.getByRole('radio', { name: /Quick checks/ }).isChecked(), false);
    await question.getByRole('radio', { name: /Quick checks/ }).check();
    await question.getByRole('checkbox', { name: 'Log' }).check();
    await question.getByRole('checkbox', { name: 'Report' }).check();
    await question.getByRole('textbox', { name: 'Add a short note' }).fill('Keep the log.');
    assert.equal(await question.getByRole('button', { name: 'Send response' }).isEnabled(), true);
    assert.equal((await logs()).filter(row => String(row[1]).includes('/reply')).length, 0);
    await page.evaluate(() => {
        Object.defineProperties(window.visualViewport, {
            height: { configurable: true, value: 430 },
            offsetTop: { configurable: true, value: 22 }
        });
        window.visualViewport.dispatchEvent(new Event('resize'));
    });
    await page.waitForFunction(() => document.documentElement.style.getPropertyValue('--visual-height') === '430px');
    const dialogBounds = await question.boundingBox();
    assert(dialogBounds.y >= 22 && dialogBounds.y + dialogBounds.height <= 452);
    await page.waitForFunction(() => {
        const focused = document.activeElement;
        const body = focused?.closest('.agent-dialog-body');
        return body && focused.getBoundingClientRect().bottom <= body.getBoundingClientRect().bottom;
    });
    await page.screenshot({ path: evidence + '/simulated-keyboard-question-390.png' });
    await page.evaluate(() => {
        delete window.visualViewport.height;
        delete window.visualViewport.offsetTop;
        window.visualViewport.dispatchEvent(new Event('resize'));
    });
    await page.screenshot({ path: evidence + '/mobile-question-390.png' });
    await question.getByRole('button', { name: 'Close', exact: true }).last().click();
    assert.equal((await logs()).filter(row => String(row[1]).includes('/reply')).length, 0);
    await page.locator('.agent-request:visible').filter({ hasText: 'Choose how to run the checks' }).click();
    await question.getByRole('button', { name: 'Send response' }).click();
    const answer = (await logs()).find(row => String(row[1]).endsWith('/questions-1/reply'))?.[2];
    assert.deepEqual(answer, { answers: [
        { question_id: 'single', option_ids: ['fast'] },
        { question_id: 'multi', option_ids: ['log', 'report'] },
        { question_id: 'text', option_ids: [], text: 'Keep the log.' }
    ]});
    await question.getByRole('button', { name: 'Close', exact: true }).last().click();

    await page.reload();
    await page.getByRole('button', { name: 'Chat mode — Codex CLI' }).waitFor();
    await page.waitForFunction(() => document.querySelector('.input-wrapper textarea').value === 'Keep this draft while waiting');
    await page.locator('.agent-request:visible').filter({ hasText: 'Confirm test prerequisites' }).click();
    const approval = page.getByRole('dialog', { name: 'Confirm test prerequisites' });
    await approval.getByText('Plan review', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.fixtureUnsafe), undefined);
    await approval.getByRole('radio', { name: 'Reject the change' }).check();
    assert.equal((await logs()).filter(row => String(row[1]).includes('/reply')).length, 1);
    await page.setViewportSize({ width: 740, height: 320 });
    await page.screenshot({ path: evidence + '/landscape-approval.png' });
    await approval.getByRole('button', { name: 'Send response' }).click();
    await page.locator('.agent-artifacts a').waitFor({ state: 'attached' });
    await approval.getByRole('button', { name: 'Close', exact: true }).last().click();
    assert.deepEqual((await logs()).find(row => String(row[1]).endsWith('/parallel-1/reply'))?.[2], { decision_id: 'reject' });

    await page.setViewportSize({ width: 1280, height: 860 });
    await settle('.message-markdown table');
    await settle('.message-markdown pre code.hljs');
    await settle('.message-markdown .katex');
    await settle('.message-markdown .mindmap-rendered');
    assert.equal(await page.locator('.message-markdown h1').count(), 1);
    assert.equal(await page.locator('.message-markdown img').count(), 0);
    assert.equal(await page.locator('.message-markdown a[href^="javascript:"]').count(), 0);
    await page.evaluate(() => {
        Object.defineProperty(navigator, 'clipboard', { value: { writeText: async value => { window.copied = value; } } });
    });
    await page.locator('.message-actions').getByRole('button', { name: 'Copy', exact: true }).click();
    const copied = await page.evaluate(() => window.copied);
    assert(copied.includes('```python') && copied.includes('$$E = mc^2$$') && copied.includes('<img src=x onerror=alert(1)>'));
    const [download] = await Promise.all([page.waitForEvent('download'), page.locator('.agent-artifacts a').click()]);
    assert.equal(download.suggestedFilename(), 'report.txt');
    await page.screenshot({ path: evidence + '/desktop-agent-result.png' });

    await mode.click();
    await page.locator('.agent-mode-panel').getByRole('button', { name: 'Compress Agent context' }).click();
    await page.waitForFunction(() => getComputedStyle(document.querySelector('.btn-stop')).display === 'none');
    assert.equal(await composer.inputValue(), 'Keep this draft while waiting');
    assert((await logs()).some(row => String(row[1]).endsWith('/compact') && Object.keys(row[2]).join() === 'client_request_id'));

    stage = 'expiry';
    await composer.fill('expire');
    await page.getByRole('button', { name: 'send', exact: true }).click();
    await page.getByRole('button', { name: /Review file change/ }).click();
    const expired = page.getByRole('dialog', { name: 'Review file change' });
    await expired.getByRole('radio', { name: /Allow this change/ }).check();
    await expired.getByText('Request expired', { exact: true }).waitFor();
    assert.equal(await expired.getByRole('button', { name: 'Send response' }).isEnabled(), false);
    await expired.getByRole('button', { name: 'Close', exact: true }).last().click();
    await page.waitForFunction(() => getComputedStyle(document.querySelector('.btn-stop')).display === 'none');

    stage = 'stop and switch';
    await composer.fill('switch while running');
    await composer.press('Enter');
    await page.locator('.agent-request:visible').filter({ hasText: 'Choose how to run the checks' }).click();
    await question.getByRole('button', { name: 'Close', exact: true }).click();
    await page.locator('.btn-new-chat').click();
    await page.getByRole('button', { name: 'Chat mode — Ordinary chat' }).waitFor();
    assert.equal((await logs()).filter(row => String(row[1]).endsWith('/cancel')).length, 0);
    await page.getByRole('button', { name: 'Chat 1', exact: true }).click();
    await page.locator('.agent-request:visible').filter({ hasText: 'Choose how to run the checks' }).waitFor();
    await page.getByRole('button', { name: 'Stop', exact: true }).click();
    await page.getByText('Cancelled', { exact: true }).waitFor();
    assert.equal((await logs()).filter(row => String(row[1]).endsWith('/cancel')).length, 1);

    await mode.click();
    await page.locator('.agent-mode-panel').getByRole('radio', { name: 'Ordinary chat', exact: true }).check();
    await page.locator('.agent-mode-panel').getByRole('button', { name: 'Apply', exact: true }).click();
    await page.getByRole('button', { name: 'Chat mode — Ordinary chat' }).waitFor();
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await composer.fill('ordinary fixture');
    await composer.press('Enter');
    await settle('.message-markdown table');
    assert.equal(await page.locator('.markdown-reveal').count(), 0);
    const ordinary = (await logs()).find(row => row[1] === '/api/chat')?.[2];
    assert.equal(ordinary.message, 'ordinary fixture');
    for (const field of ['use_rag', 'use_thinking', 'image_base64', 'web_content']) assert(field in ordinary);

    stage = 'plugin lifecycle';
    await page.locator('.btn-plugins').click();
    await pluginModal.getByRole('tab', { name: 'Installed', exact: true }).click();
    for (const name of names) {
        const card = pluginModal.locator('.plugin-card:visible').filter({ has: page.getByText(name, { exact: true }) });
        const toggle = card.getByRole('switch');
        await toggle.click();
        await page.waitForFunction(el => el.getAttribute('aria-checked') === 'false', await toggle.elementHandle());
        await toggle.click();
        await page.waitForFunction(el => el.getAttribute('aria-checked') === 'true', await toggle.elementHandle());
        await card.getByTitle('Uninstall').click();
        await card.waitFor({ state: 'detached' });
    }

    const externalErrors = errors.filter(message => !message.includes('net::ERR_ABORTED'));
    assert.deepEqual(externalErrors, []);
    console.log('Browser', browser.version(), 'five plugins, mode binding, both sends, admission/replay, attachments, questions/approval, expiry, compact, Markdown and responsive screenshots passed');
} catch (error) {
    await page.screenshot({ path: evidence + '/test-failure.png', fullPage: true });
    await writeFile(evidence + '/test-failure.html', await page.content());
    console.error('Browser errors:', errors);
    throw error;
} finally {
    await browser.close();
    await fixture.stop();
}
