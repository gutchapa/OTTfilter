import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1145, height: 1610 }, deviceScaleFactor: 1 });
await p.goto('file://' + process.cwd() + '/cover.html', { waitUntil: 'networkidle' });
await p.evaluate(() => document.fonts.ready);
await p.pdf({ path: 'scratchpad-cover-A3-with-bleed.pdf', width: '303mm', height: '426mm', printBackground: true });
const pages = await p.$$('.page');
for (const [i, el] of pages.entries()) await el.screenshot({ path: `preview-${i ? 'back' : 'front'}.png` });
await b.close();
