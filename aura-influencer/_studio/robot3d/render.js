const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const cfgs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch({ args: ['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist','--no-sandbox','--allow-file-access-from-files'] });
  const p = await b.newPage();
  p.on('console', m => console.log('console:', m.text()));
  p.on('pageerror', e => console.log('pageerror:', e.message));
  await p.goto('http://127.0.0.1:8765/robot.html');
  await p.waitForFunction('window.ready === true', null, { timeout: 30000 });
  await p.evaluate(([w, h]) => window.initR(w, h), [cfgs.w, cfgs.h]);
  for (const s of cfgs.shots) {
    const url = await p.evaluate(c => window.shot(c), s);
    fs.writeFileSync(s.out, Buffer.from(url.split(',')[1], 'base64'));
    console.log('wrote', s.out);
  }
  await b.close();
})();
