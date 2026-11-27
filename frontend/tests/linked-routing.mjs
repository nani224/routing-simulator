import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    ...(process.env.ROUTELAB_RECORD_DIR && {
      recordVideo: { dir: process.env.ROUTELAB_RECORD_DIR },
    }),
  });
  const page = await context.newPage();
  await page.goto(process.env.ROUTELAB_URL ?? 'http://127.0.0.1:5174/');
  const mesh = page.getByRole('region', { name: 'Live RouteLab mesh' });
  await mesh.getByText('Routes settled').waitFor();
  const path = mesh.getByLabel('Current forwarding path');
  const initialPath = (await path.innerText()).split(' → ');
  assert.ok(initialPath.length > 1);
  const [source, target] = initialPath;
  const link = [source, target].sort().join(' ↔ ');
  try {
    await mesh.getByRole('combobox', { name: 'Simulation link' }).selectOption({ label: `${link} · Up` });
    await mesh.getByRole('button', { name: 'Fail link' }).click();
    await mesh.getByRole('button', { name: 'Restore link' }).waitFor();
    await mesh.getByText('Routes settled').waitFor();
    await page.waitForFunction(({ before, failedPeer }) => {
      const hops = document.querySelector('[aria-label="Current forwarding path"]')
        ?.textContent?.split(' → ');
      return hops && hops.length > 1 && hops.join(' → ') !== before && hops[1] !== failedPeer;
    }, { before: initialPath.join(' → '), failedPeer: target });
    await mesh.getByRole('button', { name: 'Open RouteLab' }).click();
    assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
    await page.getByText('1 Link(s) Down', { exact: false }).waitFor();
  } finally {
    await page.getByRole('button', { name: 'PHANTOM OBSERVATORY' }).click();
    await mesh.getByRole('combobox', { name: 'Simulation link' }).waitFor();
    const downLink = mesh.getByRole('option', { name: `${link} · Down`, exact: true });
    if (await downLink.count()) {
      await mesh.getByRole('combobox', { name: 'Simulation link' }).selectOption({ label: `${link} · Down` });
    }
    const restore = mesh.getByRole('button', { name: 'Restore link' });
    if (await restore.isVisible()) {
      await restore.click();
      await mesh.getByRole('button', { name: 'Fail link' }).waitFor();
    }
  }
  await context.close();
  console.log('Verified a live reroute, shared link state, restoration, and the dark theme.');
} finally {
  await browser.close();
}
