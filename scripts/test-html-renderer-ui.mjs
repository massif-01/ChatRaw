import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright-core';

const root = fileURLToPath(new URL('../', import.meta.url));
const browserPath = process.env.CHROME_PATH;
assert.ok(browserPath, 'Set CHROME_PATH to a Chrome or Chromium executable.');
const data = await mkdtemp(join(tmpdir(), 'chatraw-html-renderer-'));
let backend;
let browser;

try {
  backend = spawn(process.env.PYTHON || 'python3', [
    '-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', '0',
  ], {
    cwd: root,
    env: { ...process.env, DATA_DIR: data },
    stdio: ['ignore', 'ignore', 'pipe'],
  });
  const origin = await new Promise((resolve, reject) => {
    let log = '';
    const timeout = setTimeout(() => reject(new Error(`Backend startup timed out\n${log}`)), 15000);
    const fail = error => {
      clearTimeout(timeout);
      reject(error);
    };
    backend.once('error', fail);
    backend.once('exit', code => fail(new Error(`Backend exited ${code}\n${log}`)));
    backend.stderr.on('data', chunk => {
      log += chunk;
      const url = log.match(/Uvicorn running on (http:\/\/127\.0\.0\.1:\d+)/)?.[1];
      if (url) {
        clearTimeout(timeout);
        resolve(url);
      }
    });
  });

  const install = await fetch(`${origin}/api/plugins/install-bundled`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Origin: origin },
    body: JSON.stringify({ plugin_id: 'html-renderer' }),
  });
  assert.equal(install.status, 200);
  assert.equal((await install.json()).success, true);
  const installed = join(data, 'plugins/installed/html-renderer');
  assert.ok((await readFile(join(installed, 'bridge.py'), 'utf8')).includes('class PreviewServer'));
  assert.ok((await readFile(join(installed, 'install-mac.sh'), 'utf8')).includes('launchctl bootstrap'));

  browser = await chromium.launch({ executablePath: browserPath });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto(origin);
  await page.waitForFunction(() => window.__chatrawHtmlRenderer);
  const html = `<button id="increment">Count</button><output id="count">0</output>
    <script>
      let value = 0;
      const count = document.querySelector('#count');
      document.querySelector('#increment').onclick = () => { count.textContent = ++value; };
      document.addEventListener('keydown', e => { if (e.key === 'ArrowRight') count.textContent = ++value; });
      try { parent.document.body; document.body.dataset.parent = 'exposed'; }
      catch (_) { document.body.dataset.parent = 'isolated'; }
      fetch('${origin}/api/chats').then(() => { document.body.dataset.network = 'allowed'; })
        .catch(() => { document.body.dataset.network = 'blocked'; });
    </script>`;
  const fence = '```';
  await page.evaluate(({ html, fence }) => {
    const state = window.Alpine.$data(document.body);
    state.messages = [
      { id: 'user', role: 'user', content: `${fence}html\n<p>user code</p>\n${fence}` },
      { id: 'done', role: 'assistant', content: `${fence}html\n${html}\n${fence}\n\n${fence}python\nprint(1)\n${fence}\n\n${fence}html\n<p>second</p>\n${fence}` },
      { id: 'live', role: 'assistant', content: `${fence}html\n<p>streaming</p>\n${fence}`, streaming: true },
    ];
  }, { html, fence });
  await page.waitForFunction(() => document.querySelectorAll('.chatraw-html-render-action').length === 2);
  assert.equal(await page.locator('.message.user .chatraw-html-render-action').count(), 0);
  assert.equal(await page.locator('.message.assistant').nth(1).locator('.chatraw-html-render-action').count(), 0);

  const [preview] = await Promise.all([
    context.waitForEvent('page'),
    page.locator('.message.assistant').first().getByRole('button', { name: 'Render', exact: true }).first().click(),
  ]);
  const frame = preview.frameLocator('iframe');
  await frame.locator('#increment').click();
  await preview.keyboard.press('ArrowRight');
  assert.equal(await frame.locator('#count').textContent(), '2');
  await frame.locator('body[data-network="blocked"][data-parent="isolated"]').waitFor();
  const isolation = await frame.locator('body').evaluate(body => ({
    parent: body.dataset.parent,
    network: body.dataset.network,
  }));
  assert.deepEqual(isolation, { parent: 'isolated', network: 'blocked' });
  await preview.close();

  await page.evaluate(() => { window.Alpine.$data(document.body).messages[2].streaming = false; });
  await page.waitForFunction(() => document.querySelectorAll('.chatraw-html-render-action').length === 3);
  const toggle = () => page.evaluate(async () => {
    const state = window.Alpine.$data(document.body);
    await state.togglePlugin(state.installedPlugins.find(plugin => plugin.id === 'html-renderer'));
  });
  await toggle();
  await page.waitForFunction(() => document.querySelectorAll('.chatraw-html-render-action').length === 0);
  await toggle();
  await page.waitForFunction(() => document.querySelectorAll('.chatraw-html-render-action').length === 3);
  console.log('Bundled install, HTML detection, interactive preview, isolation and plugin lifecycle passed.');
} finally {
  if (browser) await browser.close();
  if (backend) backend.kill('SIGTERM');
  await rm(data, { recursive: true, force: true });
}
