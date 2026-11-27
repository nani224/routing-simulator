import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 960 },
    ...(process.env.ROUTELAB_RECORD_DIR && { recordVideo: { dir: process.env.ROUTELAB_RECORD_DIR } }),
  });
  const page = await context.newPage();
  const url = process.env.ROUTELAB_URL ?? 'http://127.0.0.1:5174/';
  await page.goto(url);
  await page.getByRole('button', { name: 'ROUTELAB SIMULATOR' }).click();
  await page.getByRole('button', { name: 'Build topology' }).click();
  const builder = page.getByRole('dialog', { name: 'Topology builder' });
  await builder.getByLabel('Network name').fill('Field network');
  for (const router of ['Alpha', 'Bravo', 'Charlie']) {
    await builder.getByLabel('Router name').fill(router);
    await builder.getByRole('button', { name: 'Add router' }).click();
  }
  for (const [source, target, cost] of [['Alpha', 'Bravo', '1'], ['Bravo', 'Charlie', '1'], ['Alpha', 'Charlie', '7']]) {
    await builder.getByLabel('From router').selectOption(source);
    await builder.getByLabel('To router').selectOption(target);
    await builder.getByLabel('Link cost').fill(cost);
    await builder.getByLabel('Delay (ms)').fill('18');
    await builder.getByRole('button', { name: 'Add link' }).click();
  }
  await builder.getByRole('button', { name: 'Save and run' }).click();
  await builder.waitFor({ state: 'hidden' });
  await page.getByRole('button', { name: /Send Live Probe Packet/ }).click();
  await page.waitForFunction(async () => {
    const log = await (await fetch('/api/export/json')).json();
    return log.events.some((event) =>
      event.type === 'packet_delivered' && event.data.proto === 'probe'
      && event.data.src === 'Alpha' && event.data.dst === 'Charlie');
  });
  const log = await (await page.request.get(new URL('/api/export/json', url).href)).json();
  const probeHops = log.events.filter((event) => event.type === 'packet_sent' && event.data.proto === 'probe');
  assert.deepEqual(probeHops.map((event) => [event.data.src, event.data.dst]), [['Alpha', 'Bravo'], ['Bravo', 'Charlie']]);
  assert.equal(log.state.topology_name, 'Field network');
  assert.equal(log.state.links['Alpha<->Bravo'].latency_ms, 18);

  await page.getByRole('button', { name: 'Compare', exact: true }).click();
  const comparison = page.waitForResponse((response) => response.url().endsWith('/api/simulation/compare'));
  await page.getByRole('button', { name: 'Run Visual Comparison Race' }).click();
  const result = await (await comparison).json();
  assert.equal(result.topology_name, 'Field network');
  assert.ok(result.final_routes.distance_vector.Alpha.some((route) => route.dst === 'Charlie' && route.next_hop === 'Bravo'));
  await page.getByRole('button', { name: 'Close comparison' }).click();
  await page.getByRole('button', { name: 'PHANTOM OBSERVATORY' }).click();
  const mesh = page.getByRole('region', { name: 'Live RouteLab mesh' });
  const path = mesh.getByLabel('Current forwarding path');
  await mesh.getByText('Alpha → Bravo → Charlie', { exact: true }).waitFor();
  await mesh.getByRole('combobox', { name: 'Simulation link' }).selectOption({ label: 'Alpha ↔ Bravo · Up' });
  await mesh.getByRole('button', { name: 'Fail link' }).click();
  await page.waitForFunction(() => document.querySelector('[aria-label="Current forwarding path"]')?.textContent === 'Alpha → Charlie');
  await mesh.getByRole('button', { name: 'Send probe' }).click();
  await page.waitForFunction(async () => {
    const log = await (await fetch('/api/export/json')).json();
    return log.events.some((event) => event.type === 'packet_sent' && event.data.proto === 'probe'
      && event.data.src === 'Alpha' && event.data.dst === 'Charlie');
  });
  await mesh.getByRole('button', { name: 'Restore link' }).click();
  await mesh.getByText('Alpha → Bravo → Charlie', { exact: true }).waitFor();
  await page.reload();
  await mesh.getByText('Alpha → Bravo → Charlie', { exact: true }).waitFor();
  assert.match(await path.innerText(), /Bravo/);
  await context.close();
  console.log('Custom config, backend probe delivery, comparison, Observatory failover and reload passed.');
} finally {
  await browser.close();
}
