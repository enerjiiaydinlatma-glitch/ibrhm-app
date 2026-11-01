const { chromium } = require('playwright'); const fs = require('fs');
(async () => {
  const [W, H, out, ...jobs] = process.argv.slice(2); // jobs: set:clip:frame
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] });
  const bySet = {};
  for (const j of jobs) { const [s, c, f] = j.split(':'); (bySet[s] = bySet[s] || []).push([c, +f]); }
  for (const s of Object.keys(bySet)) {
    const p = await br.newPage(); p.on('pageerror', e => console.log('pageerror:', e.message));
    await p.goto('http://127.0.0.1:8765/a3d/aura3d.html'); await p.waitForFunction('window.ready === true');
    await p.evaluate(([w, h, st]) => window.initA(w, h, st), [+W, +H, s]);
    for (const [c, f] of bySet[s]) { const r = await p.evaluate(([c2, f2]) => window.clipFrame(c2, f2, false), [c, f]); fs.writeFileSync(`${out}/${s}_${c}_${f}.png`, Buffer.from(r.beauty.split(',')[1], 'base64')); console.log('ok', s, c, f); }
    await p.close();
  }
  await br.close();
})();
