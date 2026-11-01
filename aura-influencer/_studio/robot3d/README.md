# Aura Robot 3B (gelistirici araci, panel icin GEREKMEZ)

`robot.html` (three.js, PBR malzeme/golge/yansima) ile insansi robotun poz sprite'lari render edilir:
`render.js` (playwright + headless Chromium/SwiftShader) `robot.html`'i yerel http sunucusundan acar ve
`window.shot(cfg)` ile PNG uretir. Cikti: `_studio/assets/aura_robot/c_p{0,1,2}.png` (guzellik render'i, vizor siyah cam)
ve `c_p*_uv.png` (vizor yuzeyinin UV haritasi: R=u, G=v, B=1). `make_video_v2.py` (`face="robot"`) bu UV haritasiyla
sesle konusan LED yuzu vizorun egriligine gore basar.

Yeniden uretmek icin (ayri bir klasorde): `npm i three@0.160.0 playwright@1.56.0`, `python3 -m http.server 8765`,
`PLAYWRIGHT_BROWSERS_PATH=... node render.js close.json` (kamera/poz ayarlari JSON'da: `cam`, `pose`, `mode: "uv"`).
Pozlar: p0 sakin, p1 el kaldirir/selam, p2 avuc acik (karta gecerken kullanilmiyor).
Tasarim: Figure/Digit/Optimus gibi insansi robotlardan ilham alan genel bir tasarim; muhendislik cizimi degildir.
