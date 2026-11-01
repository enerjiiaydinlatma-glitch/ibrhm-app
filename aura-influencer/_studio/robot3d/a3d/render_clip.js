// node render_clip.js <set> <clip> <start> <end> <outdir> [W H] [nomask]
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const [set, clip, a, b, out, W = '1080', H = '1920'] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const br = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox'] });
  const p = await br.newPage();
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('console:', m.text()); });
  p.on('pageerror', e => console.log('pageerror:', e.message));
  await p.goto('http://127.0.0.1:8765/a3d/aura3d.html');
  await p.waitForFunction('window.ready === true', null, { timeout: 60000 });
  console.log(await p.evaluate(([w, h, s]) => window.initA(w, h, s), [+W, +H, set]));
  const grids = {};
  for (let f = +a; f < +b; f++) {
    const t0 = Date.now();
    const r = await p.evaluate(([c, f2]) => window.clipFrame(c, f2, true), [clip, f]);
    const id = String(f).padStart(4, '0');
    fs.writeFileSync(`${out}/f_${id}.png`, Buffer.from(r.beauty.split(',')[1], 'base64'));
    if (r.mask) fs.writeFileSync(`${out}/m_${id}.png`, Buffer.from(r.mask.split(',')[1], 'base64'));
    grids[f] = r.grid;
    console.log('frame', f, ((Date.now() - t0) / 1000).toFixed(1) + 's');
  }
  fs.writeFileSync(`${out}/grid_${a}_${b}.json`, JSON.stringify(grids));
  await br.close();
})();
