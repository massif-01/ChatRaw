import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startFixture } from './fixtures/browser-server.mjs';

const engine = process.env.CHATRAW_TEST_ENGINE || 'chromium';
const executablePath = engine === 'webkit' ? process.env.WEBKIT_PATH : process.env.CHROME_PATH;
const playwright = process.env.CHATRAW_PLAYWRIGHT_MODULE
    ? pathToFileURL(resolve(process.env.CHATRAW_PLAYWRIGHT_MODULE)).href
    : 'playwright-core';
const browsers = await import(playwright);
const root = fileURLToPath(new URL('../', import.meta.url));
const fixture = await startFixture(fileURLToPath(new URL('./fixtures/agent-browser.py', import.meta.url)), { cwd: root });
const { origin } = fixture;
const chat = { id: 'details-chat', title: 'Run detail fixtures' };
const session = 'details-session';
const runs = ['text-only', 'tool-history', 'latest-text'];
const approval = {
    interaction_id: 'approval', kind: 'approval', title: 'Review workspace check',
    operation: { tool: 'inspect' }, decisions: [{ id: 'allow', label: 'Allow' }], allow_cancel: false
};
const streams = {
    'text-only': [['usage', {}]],
    'tool-history': [
        ['tool_started', { tool_call_id: 'inspect', name: 'inspect', title: 'Inspect workspace' }],
        ['interaction_requested', approval],
        ['interaction_resolved', { interaction_id: 'approval', outcome: 'answered', answer_summary: 'Approved' }],
        ['tool_completed', { tool_call_id: 'inspect', name: 'inspect', output_preview: 'Workspace checked' }],
        ['usage', { input_tokens: 0, output_tokens: 4 }]
    ],
    'latest-text': []
};
for (const run of runs) {
    streams[run] = [
        ['status', { status: 'running' }],
        ['text_delta', { text: run + ' reply' }],
        ...streams[run],
        ['status', { status: 'completed' }],
        ['done', { status: 'completed' }]
    ];
}

let browser;
try {
    browser = await browsers[engine].launch({ executablePath });
    const page = await browser.newPage();
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(error.message));
    page.setDefaultTimeout(7000);
    await page.addInitScript(id => localStorage.setItem('chatraw-selected-chat', id), chat.id);

    let releaseTextEvents;
    const textEventsReady = new Promise(resolveEvents => { releaseTextEvents = resolveEvents; });
    let releaseToolEvents;
    const toolEventsReady = new Promise(resolveEvents => { releaseToolEvents = resolveEvents; });
    const requested = [];
    const latestEvents = page.waitForResponse(r => r.url().includes('/latest-text/events') && r.ok());
    await page.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin !== origin || route.request().method() !== 'GET') return route.abort();
        const path = url.pathname;
        if (path === '/api/chats') return route.fulfill({ json: [chat] });
        if (path === '/api/chats/' + chat.id + '/messages') {
            return route.fulfill({ json: runs.map(run => ({ id: run, role: 'assistant', run_id: run, content: run + ' reply' })) });
        }
        if (path === '/api/chats/' + chat.id + '/agent') {
            return route.fulfill({ json: {
                chat_id: chat.id, session_id: session, agent_id: 'codex', workspace: { kind: 'managed' },
                active_run_id: null, last_run_id: runs[runs.length - 1]
            } });
        }
        const match = path.match(/^\/api\/agents\/runs\/([^/]+)(\/events)?$/);
        if (!match) return route.continue();
        const [, run, events] = match;
        if (!events) return route.fulfill({ json: {
            run_id: run, chat_id: chat.id, session_id: session, status: 'completed', last_seq: streams[run].length, interactions: []
        } });
        requested.push(run);
        if (run === 'text-only') await textEventsReady;
        if (run === 'tool-history') {
            if (requested.filter(item => item === run).length === 1) {
                return route.fulfill({ status: 503, json: { error: { message: 'Fixture replay unavailable' } } });
            }
            await toolEventsReady;
        }
        const body = streams[run].map(([type, data], index) => JSON.stringify({
            schema_version: 1, run_id: run, session_id: session, seq: index + 1, type, data
        })).join('\n');
        return route.fulfill({ contentType: 'application/x-ndjson', body: body + '\n' });
    });

    await page.goto(origin);
    await page.getByRole('button', { name: 'Chat mode — Codex CLI' }).waitFor();
    const message = run => page.locator('.message.assistant').filter({ hasText: run + ' reply' });
    const panel = run => message(run).locator('.agent-run-details');
    const open = run => panel(run).locator('summary').click();
    const status = (run, value) => panel(run).getByText(value, { exact: true }).waitFor();
    await latestEvents;
    assert.deepEqual(requested, ['latest-text']);
    await open('latest-text');
    await status('latest-text', 'No additional details for this run.');

    await open('text-only');
    await status('text-only', 'Loading run details…');
    await message('text-only').locator('.agent-status').getByText('Completed', { exact: true }).waitFor();
    assert.equal(await panel('text-only').getByText('No additional details for this run.', { exact: true }).count(), 0);
    releaseTextEvents();
    await status('text-only', 'No additional details for this run.');

    await open('tool-history');
    await status('tool-history', 'Could not load all run details. Reconnecting…');
    assert.equal(await panel('tool-history').getByText('No additional details for this run.', { exact: true }).count(), 0);
    releaseToolEvents();
    await panel('tool-history').getByText('Workspace checked', { exact: true }).waitFor();
    await panel('tool-history').getByText('Review workspace check', { exact: true }).waitFor();
    await panel('tool-history').getByText('Input tokens', { exact: true }).waitFor();
    assert.equal(await panel('tool-history').locator('dd').first().innerText(), '0');
    assert.equal(await panel('tool-history').locator('.agent-details-status').isVisible(), false);
    await panel('tool-history').getByRole('button', { name: /Review workspace check/ }).click();
    const dialog = page.getByRole('dialog', { name: 'Review workspace check' });
    await dialog.getByText('Approved', { exact: true }).waitFor();
    assert.equal(await dialog.getByRole('button', { name: 'Send response' }).isEnabled(), false);
    await dialog.getByRole('button', { name: 'Close', exact: true }).click();
    assert.deepEqual(pageErrors, []);

    if (process.env.CHATRAW_EVIDENCE_DIR) {
        await mkdir(process.env.CHATRAW_EVIDENCE_DIR, { recursive: true });
        await page.screenshot({ path: resolve(process.env.CHATRAW_EVIDENCE_DIR, engine + '-run-details.png') });
    }
    console.log(engine + ' ' + browser.version() + ': text-only, historical replay, reconnect, tool/approval, and zero usage passed');
} finally {
    await browser?.close();
    await fixture.stop();
}
