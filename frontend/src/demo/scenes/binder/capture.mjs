// Manual visual capture, not a Playwright test. Run under the shared browser flock (README).
import { createServer } from 'vite';
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { mkdir, rename, writeFile } from 'node:fs/promises';
import path from 'node:path';
const dir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(dir, '../../../..');
const output = path.join(dir, 'assets');
await mkdir(output, { recursive: true });
const server = await createServer({ root, configFile: false, cacheDir: '/tmp/binder-v2-vite', esbuild: { jsx: 'automatic' }, optimizeDeps: { entries: ['src/demo/scenes/binder/preview.html'] }, server: { host: '127.0.0.1', port: 0 } });
let browser;
try {
  await server.listen();
  const base = server.resolvedUrls.local[0];
  browser = await chromium.launch({ headless: true, args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${base}src/demo/scenes/binder/preview.html?time=15&capture=1`);
  await page.waitForSelector('canvas');
  await page.waitForTimeout(1800);
  for (const [time, name] of [[15, 'binder-v2'], [0, 'binder-v2-opening'], [8, 'binder-v2-approach'], [11, 'binder-v2-seated'], [18, 'binder-v2-held']]) {
    await page.evaluate(t => window.dispatchEvent(new CustomEvent('binder-time', { detail: t })), time);
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(output, `${name}.png`) });
  }
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('binder-time', { detail: 15 })));
  await page.waitForTimeout(600);
  const repeat = await page.screenshot();
  const { readFile } = await import('node:fs/promises');
  const deterministic = repeat.equals(await readFile(path.join(output, 'binder-v2.png')));
  await context.close();
  if (!process.argv.includes('--still-only')) {
    const videoContext = await browser.newContext({ viewport: { width: 1280, height: 720 }, recordVideo: { dir: output, size: { width: 1280, height: 720 } } });
    const videoPage = await videoContext.newPage();
    await videoPage.goto(`${base}src/demo/scenes/binder/preview.html?time=0&capture=1`);
    await videoPage.waitForTimeout(1500);
    await videoPage.evaluate(() => {
      const start = performance.now();
      function step(now) {
        const t = Math.min(18, (now - start) / 1000);
        window.dispatchEvent(new CustomEvent('binder-time', { detail: t }));
        if (t < 18) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
    await videoPage.waitForTimeout(19000);
    const video = videoPage.video();
    await videoContext.close();
    await rename(await video.path(), path.join(output, 'binder-v2.webm'));
  }
  await writeFile(path.join(output, 'binder-v2-capture.json'), JSON.stringify({ renderer: 'Chromium SwiftShader', viewport: [1920, 1080], stillTime: 15, repeatedTimePixelIdentical: deterministic, errors, provenance: 'Illustrative seeded geometry; not a scientific result' }, null, 2) + '\n');
  if (errors.length || !deterministic) throw Error(JSON.stringify({ errors, deterministic }));
} finally { await browser?.close(); await server.close(); }
