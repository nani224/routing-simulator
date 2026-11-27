import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const browser = await chromium.launch();
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ...(process.env.ROUTELAB_RECORD_DIR && { recordVideo: { dir: process.env.ROUTELAB_RECORD_DIR } }),
  });
  const page = await context.newPage();
  await page.goto(process.env.ROUTELAB_URL ?? 'http://127.0.0.1:5174/');
  await page.getByRole('button', { name: 'ROUTELAB SIMULATOR' }).click();
  const zoom = page.getByRole('status', { name: 'Canvas zoom' });
  const readZoom = async () => parseInt(await zoom.innerText(), 10);
  const fit = page.getByRole('button', { name: 'Fit topology' });
  await fit.click();
  const initialZoom = await readZoom();
  assert.ok(initialZoom > 100, `Desktop fit should enlarge the graph: ${initialZoom}`);
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  assert.ok(await readZoom() > initialZoom);
  await fit.click();
  assert.equal(await readZoom(), initialZoom);

  for (const width of [1440, 1024, 390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForFunction((expected) => {
      const toolbar = document.querySelector('.routing-toolbar');
      return toolbar?.clientWidth === expected && toolbar.scrollWidth <= expected;
    }, width);
    const boxes = await page.locator('.routing-canvas, .routing-tracer, .routing-inspector').evaluateAll((elements) =>
      elements.map((element) => {
        const { left, right, top, bottom, height } = element.getBoundingClientRect();
        return { left, right, top, bottom, height };
      }),
    );
    const [canvas, tracer, inspector] = boxes;
    assert.ok(canvas.height >= 224);
    for (const box of boxes) assert.ok(box.left >= 0 && box.right <= width + 1);
    if (width < 1200) assert.ok(tracer.top >= canvas.bottom && inspector.top >= canvas.bottom);
    else assert.ok(tracer.right <= canvas.left && canvas.right <= inspector.left);
    await page.getByRole('button', { name: 'Settings & Parameters' }).scrollIntoViewIfNeeded();
  }
  assert.equal(await readZoom(), initialZoom);
  await context.close();
  console.log('Verified auto-fit, zoom controls and unclipped workspace at desktop, tablet and phone widths.');
} finally {
  await browser.close();
}
