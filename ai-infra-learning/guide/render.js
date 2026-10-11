const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://' + process.cwd() + '/guide.html', { waitUntil: 'networkidle' });
  await p.pdf({ path: 'AI_Infrastructure_Field_Guide.pdf', format: 'A4', printBackground: true,
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="font-family:Inter,sans-serif;font-size:8px;color:#8a8f9c;width:100%;padding:0 18mm;display:flex;justify-content:space-between"><span>AI Infrastructure Field Guide</span><span class="pageNumber"></span></div>',
    margin: { top: '18mm', bottom: '20mm', left: '18mm', right: '18mm' } });
  await b.close();
})();
