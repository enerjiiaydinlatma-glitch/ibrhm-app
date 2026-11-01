"""Aura 3B sahne kliplerinden video karesi uretimi (make_video_v2 face="scene3d").

Klipler (_studio/assets/aura_scenes/<set>/<klip>.mp4 + _mask.mp4 + .json) three.js ile onceden render edilmis
tam kare (1080x1920) 3B sahnelerdir: robot + set + yansimalar. Burada sadece:
  1) cumle/kart zamanlamasindan hangi klibin hangi karesinin gosterilecegi (plan),
  2) sesle konusan LED yuzun vizorun egriligine gore (izgara + perspektif) basilmasi,
  3) kart arkasi koyulastirma, zemin/ustte karartma (altyazi okunurlugu).
"""
import json
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE_DIR = os.path.join(HERE, "assets", "aura_scenes")
FACE = {"RU0": 0.15, "RU1": 0.85, "RV0": 0.24, "RV1": 0.82, "N": 5}   # scene3d JS ile ayni olmali (klip json'unda da var)
TW, TH = 330, 275
CLIP_N = {"intro": 138, "idle_M": 60, "idle_C": 60, "to_C": 20, "to_M": 20, "point_C": 54, "shrug_M": 48, "nod_M": 36}
LOOPS = ("idle_M", "idle_C")
GESTURES = {"sad": "shrug_M", "happy": "nod_M"}


def available_sets():
    if not os.path.isdir(SCENE_DIR):
        return []
    return sorted(d for d in os.listdir(SCENE_DIR) if os.path.exists(os.path.join(SCENE_DIR, d, "idle_M.json")))


def set_complete(name):
    return all(os.path.exists(os.path.join(SCENE_DIR, name, c + ".json")) for c in CLIP_N)


# ------------------------------------------------------------------ plan
def build_plan(nf, tl, cards, emos, spec):
    """Her video karesi icin (klip, klip_kare_no). tl = [(cumle, t0, sure)], cards = {cumle_idx: kart}."""
    fps = 30
    plan = ["idle_M"] * nf
    want_intro = spec.get("intro", True)
    # kart pencereleri (kare cinsinden), yakin olanlari birlestir
    wins = []
    for i in sorted(cards):
        if i >= len(tl):
            continue
        a = int(tl[i][1] * fps)
        b = min(int((tl[i][1] + tl[i][2]) * fps), nf)
        if wins and a - wins[-1][1] < 45:
            wins[-1][1] = b
        else:
            wins.append([a, b])
    if want_intro and wins and wins[0][0] - 20 < CLIP_N["intro"]:
        want_intro = False
    if want_intro:
        for f in range(min(CLIP_N["intro"], nf)):
            plan[f] = "intro"
    for a, b in wins:
        a0, b0 = max(a - CLIP_N["to_C"], 0), b
        for f in range(a0, min(a, nf)):
            plan[f] = "to_C"
        for f in range(a, min(b - CLIP_N["to_M"], nf)):
            plan[f] = "idle_C"
        for f in range(max(b - CLIP_N["to_M"], a), min(b, nf)):
            plan[f] = "to_M"
        # kartin ilk saniyelerinde rakama isaret
        p0 = a + 6
        if b - CLIP_N["to_M"] - p0 >= CLIP_N["point_C"] and spec.get("point", True):
            for f in range(p0, p0 + CLIP_N["point_C"]):
                plan[f] = "point_C"
    # jestler (M cercevesinde, bos idle_M uzerinde)
    gest = {int(k): v for k, v in (spec.get("gestures") or {}).items()}
    for i, (_, t0, d) in enumerate(tl):
        g = gest.get(i) or (GESTURES.get(emos[i]) if spec.get("auto_gestures", True) else None)
        if not g or g not in CLIP_N or d * fps < CLIP_N[g] + 6:
            continue
        a = int(t0 * fps) + 4
        if a + CLIP_N[g] <= nf and all(plan[f] == "idle_M" for f in range(a, a + CLIP_N[g])):
            for k in range(CLIP_N[g]):
                plan[a + k] = g
    # klip ici kare numaralari
    out, run_clip, run_start = [], None, 0
    for f, c in enumerate(plan):
        if c != run_clip:
            run_clip, run_start = c, f
        k = f - run_start
        out.append((c, k % CLIP_N[c] if c in LOOPS else min(k, CLIP_N[c] - 1)))
    return out


def card_frames(plan):
    """C cercevesinde (kart gorunur) olan kare araligi bilgisi: gorsel yogunluk icin kullanilir."""
    return [c in ("idle_C", "point_C", "to_C", "to_M") for c, _ in plan]


# ------------------------------------------------------------------ klip okuyucu
class _Pipe:
    def __init__(self, path, start, w, h, gray=False):
        self.w, self.h, self.pos = w, h, start
        fmt = "gray" if gray else "rgb24"
        self.size = w * h * (1 if gray else 3)
        self.gray = gray
        cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(start - 0.5, 0) / 30.0:.4f}", "-i", path, "-f", "rawvideo", "-pix_fmt", fmt, "-"]
        self.p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=self.size * 2)

    def read(self):
        buf = self.p.stdout.read(self.size)
        if len(buf) < self.size:
            return None
        self.pos += 1
        a = np.frombuffer(buf, np.uint8)
        return a.reshape(self.h, self.w) if self.gray else a.reshape(self.h, self.w, 3)

    def close(self):
        try:
            self.p.stdout.close()
            self.p.kill()
            self.p.wait()
        except Exception:
            pass


class Clips:
    def __init__(self, set_name):
        self.dir = os.path.join(SCENE_DIR, set_name)
        self.meta, self.pipes, self.last = {}, {}, {}

    def get_meta(self, clip):
        if clip not in self.meta:
            self.meta[clip] = json.load(open(os.path.join(self.dir, clip + ".json")))
        return self.meta[clip]

    def frame(self, clip, idx):
        m = self.get_meta(clip)
        w, h = m["W"], m["H"]
        out = []
        for kind, gray in (("", False), ("_mask", True)):
            key = (clip, kind)
            pp = self.pipes.get(key)
            if pp is None or pp.pos != idx:
                if pp is not None:
                    pp.close()
                pp = self.pipes[key] = _Pipe(os.path.join(self.dir, clip + kind + ".mp4"), idx, w, h, gray)
            a = pp.read()
            if a is None:                      # beklenmedik bitis: son kareyi tekrar et
                a = self.last.get(key)
                if a is None:
                    a = np.zeros((h, w) if gray else (h, w, 3), np.uint8)
            else:
                self.last[key] = a
            out.append(a)
        return out[0], out[1], m

    def close(self):
        for pp in self.pipes.values():
            pp.close()
        self.pipes = {}


# ------------------------------------------------------------------ yuz yerlestirme
def _homography(dst, src):
    """dst (cikti) 4 nokta -> src (kaynak) 4 nokta: PIL PERSPECTIVE katsayilari (cikti->kaynak)."""
    A, b = [], []
    for (x, y), (u, v) in zip(dst, src):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    try:
        return np.linalg.solve(np.array(A, np.float64), np.array(b, np.float64)).tolist()
    except np.linalg.LinAlgError:
        return None


def warp_face(tex_img, pts, vis, N, frame_w, frame_h):
    """tex_img: PIL RGBA (TW x TH). Donus: (bbox, emission float32 HxWx3) ya da None."""
    P = np.array(pts, np.float64).reshape(N + 1, N + 1, 2)
    V = np.array(vis, np.float64).reshape(N + 1, N + 1)
    if V.max() < 0.05:
        return None
    x0 = int(max(np.floor(P[..., 0].min()) - 6, 0))
    y0 = int(max(np.floor(P[..., 1].min()) - 6, 0))
    x1 = int(min(np.ceil(P[..., 0].max()) + 6, frame_w))
    y1 = int(min(np.ceil(P[..., 1].max()) + 6, frame_h))
    bw, bh = x1 - x0, y1 - y0
    if bw < 8 or bh < 8:
        return None
    emis = np.zeros((bh, bw, 3), np.float32)
    tw, th = tex_img.size
    for j in range(N):
        for i in range(N):
            if min(V[j, i], V[j, i + 1], V[j + 1, i + 1], V[j + 1, i]) < 0.05:
                continue
            dst = [P[j, i], P[j, i + 1], P[j + 1, i + 1], P[j + 1, i]]
            dst = [(float(p[0] - x0), float(p[1] - y0)) for p in dst]
            src = [(i * tw / N, j * th / N), ((i + 1) * tw / N, j * th / N), ((i + 1) * tw / N, (j + 1) * th / N), (i * tw / N, (j + 1) * th / N)]
            co = _homography(dst, src)
            if co is None:
                continue
            warped = tex_img.transform((bw, bh), Image.PERSPECTIVE, co, resample=Image.BILINEAR)
            poly = Image.new("L", (bw, bh), 0)
            ImageDraw.Draw(poly).polygon(dst, fill=255)
            a = np.asarray(warped).astype(np.float32)
            m = (np.asarray(poly).astype(np.float32) / 255.0)[..., None]
            rgb = a[..., :3] * (a[..., 3:4] / 255.0) * m
            emis = np.maximum(emis, rgb)
    return (x0, y0, x1, y1), emis


def draw_face(frame, mask, pts, vis, tex_img, N):
    """frame: uint8 HxWx3 (yerinde degistirilir). mask: uint8 HxW (vizor gorunurlugu)."""
    h, w = frame.shape[:2]
    r = warp_face(tex_img, pts, vis, N, w, h)
    if r is None:
        return frame
    (x0, y0, x1, y1), emis = r
    vm = (mask[y0:y1, x0:x1].astype(np.float32) / 255.0)[..., None]
    if vm.max() < 0.02:
        return frame
    rad = max((x1 - x0) / 38.0, 1.5)
    glow = np.asarray(Image.fromarray(np.clip(emis, 0, 255).astype(np.uint8), "RGB").filter(ImageFilter.GaussianBlur(rad))).astype(np.float32)
    reg = frame[y0:y1, x0:x1].astype(np.float32)
    reg += (emis * 1.15 + glow * 0.75) * vm
    frame[y0:y1, x0:x1] = np.clip(reg, 0, 255).astype(np.uint8)
    return frame


_GRAD = {}


def shade(frame):
    """Altyazi/kart okunurlugu: altta ve hafifce ustte karartma (onceden hesaplanmis carpan)."""
    h, w = frame.shape[:2]
    if h not in _GRAD:
        y = np.arange(h, dtype=np.float32)
        lo = np.clip((y - 1050.0) / 420.0, 0, 1)
        lo = lo * lo * (3 - 2 * lo)
        hi = np.clip((120.0 - y) / 120.0, 0, 1)
        _GRAD[h] = (1.0 - 0.52 * lo - 0.25 * hi)[:, None, None].astype(np.float32)
    return np.clip(frame.astype(np.float32) * _GRAD[h], 0, 255).astype(np.uint8)
