const { chromium } = require('playwright');
(async () => { const b = await chromium.launch(); const p = await b.newPage({viewport:{width:900,height:1250}});
 await p.goto('file://' + process.argv[2]); await p.pdf({ path: process.argv[3], format: 'A4', printBackground: true });
 await p.screenshot({ path: process.argv[4] }); await b.close(); })();
