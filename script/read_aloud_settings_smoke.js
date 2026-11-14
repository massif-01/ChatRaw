// Run after installing v1.0.1 in an isolated ChatRaw instance.
async (page) => {
  const results = [];
  const check = (ok, label) => { if (!ok) throw Error(label); results.push(label); };
  async function open() {
    await page.evaluate(async () => {
      const app = document.querySelector('[x-data]')._x_dataStack[0];
      app.lang = 'zh';
      await app.openPluginSettings(app.installedPlugins.find(p => p.id === 'answer-read-aloud'));
    });
    await page.getByRole('textbox', { name: '百炼 API Key' }).waitFor();
    await page.waitForFunction(() => !document.querySelector('.answer-read-aloud-footer button:last-child').disabled);
  }
  await open();
  check(await page.locator('.answer-read-aloud-settings').count() === 1, 'Settings render without host cleanup API');
  await page.evaluate(() => {
    const area = document.getElementById('plugin-custom-settings-area');
    const parent = area.parentElement;
    area.remove(); area.textContent = 'Loading...';
    window.dispatchEvent(new CustomEvent('plugin-settings-open', { detail: { pluginId: 'answer-read-aloud' } }));
    setTimeout(() => parent.appendChild(area), 100);
  });
  await page.getByRole('textbox', { name: '百炼 API Key' }).waitFor();
  check(await page.locator('.answer-read-aloud-settings').count() === 1, 'Settings render when event precedes DOM mount');
  await page.waitForFunction(() => !document.querySelector('.answer-read-aloud-footer button:last-child').disabled);
  await page.getByRole('textbox', { name: '百炼 API Key' }).fill('compat-test-not-a-real-key');
  await page.getByRole('combobox', { name: '音色', exact: true }).selectOption('Serena');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await page.waitForFunction(() => !document.querySelector('[x-data]')._x_dataStack[0].showPluginSettings);
  await open();
  check(await page.getByRole('combobox', { name: '音色', exact: true }).inputValue() === 'Serena', 'Settings persist and reopen');
  check(await page.getByRole('textbox', { name: '百炼 API Key' }).inputValue() === '', 'Saved key is not returned to input');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.evaluate(async () => {
    const app = document.querySelector('[x-data]')._x_dataStack[0];
    const plugin = app.installedPlugins.find(p => p.id === 'answer-read-aloud');
    await app.loadPluginJS(plugin); await app.loadPluginJS(plugin);
  });
  await open();
  check(await page.locator('.answer-read-aloud-settings').count() === 1, 'Reload keeps one settings runtime');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.evaluate(async () => {
    const app = document.querySelector('[x-data]')._x_dataStack[0];
    await app.togglePlugin(app.installedPlugins.find(p => p.id === 'answer-read-aloud'));
  });
  await open();
  check(await page.locator('.answer-read-aloud-settings').count() === 1, 'Settings remain available after disabling');
  await page.getByRole('button', { name: '取消', exact: true }).click();
  await page.evaluate(async () => {
    const app = document.querySelector('[x-data]')._x_dataStack[0];
    await app.togglePlugin(app.installedPlugins.find(p => p.id === 'answer-read-aloud'));
  });
  return { passed: results.length, results };
};
