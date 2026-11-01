"""Aura 3D klip uretici (gelistirici araci). Kullanim: python build_clips.py <out_root> <set> [<set>...] [--clips a,b] [--jobs 2] [--W 1080 --H 1920]
Cikti: <out_root>/<set>/<clip>.mp4 (renk), <clip>_mask.mp4 (vizor maskesi), <clip>.json (fps, n, yuz izgarasi)."""
import os, sys, json, subprocess, shutil, glob, time
HERE = os.path.dirname(os.path.abspath(__file__))
CLIP_N = {"intro": 138, "idle_M": 60, "idle_C": 60, "to_C": 20, "to_M": 20, "point_C": 54, "shrug_M": 48, "nod_M": 36}
args = sys.argv[1:]
def opt(name, default):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default
jobs = int(opt("--jobs", "2")); W = opt("--W", "1080"); H = opt("--H", "1920"); clips = opt("--clips", ",".join(CLIP_N)).split(",")
out_root = args[0]; sets = args[1:]
env = dict(os.environ, PLAYWRIGHT_BROWSERS_PATH=os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
for st in sets:
    for clip in clips:
        n = CLIP_N[clip]; outd = os.path.join(out_root, st); os.makedirs(outd, exist_ok=True)
        if os.path.exists(os.path.join(outd, clip + ".json")):
            print("var, atla", st, clip); continue
        tmp = os.path.join(out_root, "_tmp", st, clip); shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
        t0 = time.time(); per = -(-n // jobs); procs = []
        for j in range(jobs):
            a, b = j * per, min((j + 1) * per, n)
            if a >= b: break
            procs.append(subprocess.Popen(["node", os.path.join(HERE, "render_clip.js"), st, clip, str(a), str(b), tmp, W, H], cwd=os.path.dirname(HERE), env=env, stdout=subprocess.DEVNULL))
        for p in procs:
            if p.wait() != 0: raise SystemExit(f"render hata: {st} {clip}")
        grids = {}
        for gf in glob.glob(os.path.join(tmp, "grid_*.json")): grids.update(json.load(open(gf)))
        meta = {"fps": 30, "n": n, "set": st, "clip": clip, "W": int(W), "H": int(H), "grid": [grids[str(i)]["pts"] for i in range(n)], "vis": [grids[str(i)]["vis"] for i in range(n)]}
        json.dump(meta, open(os.path.join(outd, clip + ".json"), "w"), separators=(",", ":"))
        for kind, pat, crf in (("", "f_%04d.png", "20"), ("_mask", "m_%04d.png", "14")):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "30", "-i", os.path.join(tmp, pat), "-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", os.path.join(outd, clip + kind + ".mp4")], check=True)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"{st}/{clip}: {n} kare, {time.time()-t0:.0f} sn, {os.path.getsize(os.path.join(outd, clip + '.mp4'))/1e6:.1f} MB", flush=True)
