"""Aura Voice Mesh - quick tunnel + Railway otomatik senkron.

cloudflared quick tunnel'i baslatir, cikan trycloudflare adresini yakalar,
Railway'de AURA_VOICE_URL degiskenini o adrese gunceller (Railway degisiklikte
otomatik yeniden deploy eder). Tunnel koparsa yeniden baslatir ve tekrar
senkronlar - boylece adres degisse bile kullanicinin elle mudahalesi gerekmez.

Gizli degerler: yaninda 'sync_secrets.txt' (bkz. sync_secrets.example.txt).
Calistir: tunel_kalici.bat  (ya da: python tunel_sync.py)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CF = r"C:\Program Files (x86)\cloudflared\cloudflared.exe"
LOCAL_URL = "http://localhost:8123"
RAILWAY_API = "https://backboard.railway.com/graphql/v2"
URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def load_secrets() -> dict:
    path = os.path.join(HERE, "sync_secrets.txt")
    if not os.path.exists(path):
        sys.exit(f"HATA: {path} yok. sync_secrets.example.txt'i kopyalayip doldur.")
    cfg = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    for req in ("RAILWAY_TOKEN", "PROJECT_ID", "ENVIRONMENT_ID", "SERVICE_ID"):
        if not cfg.get(req):
            sys.exit(f"HATA: sync_secrets.txt icinde {req} eksik.")
    return cfg


def railway_set_var(cfg: dict, name: str, value: str) -> None:
    body = json.dumps({
        "query": "mutation($i: VariableUpsertInput!){variableUpsert(input:$i)}",
        "variables": {"i": {
            "projectId": cfg["PROJECT_ID"],
            "environmentId": cfg["ENVIRONMENT_ID"],
            "serviceId": cfg["SERVICE_ID"],
            "name": name,
            "value": value,
        }},
    }).encode()
    req = urllib.request.Request(RAILWAY_API, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + cfg["RAILWAY_TOKEN"])
    req.add_header("User-Agent", "aura-voice-sync/1.0")
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    if data.get("errors"):
        raise RuntimeError(f"Railway API hata: {data['errors']}")
    print(f"[sync] Railway {name} = {value}  -> guncellendi (otomatik redeploy)", flush=True)


def _sync_after_delay(cfg: dict, url: str) -> None:
    """Ayri thread: birkac sn 'reachable' olmasi icin bekle, sonra Railway'i
    guncelle. Ana dongude yapilsaydi time.sleep + urlopen cloudflared'in
    stdout pipe'ini bloklayip onu stall edebilirdi (gece incelemesi)."""
    time.sleep(5)
    try:
        railway_set_var(cfg, "AURA_VOICE_URL", url)
    except Exception as e:
        print(f"[sync] UYARI: Railway guncellenemedi: {e}", flush=True)


def run_once(cfg: dict) -> None:
    print("[sync] cloudflared quick tunnel baslatiliyor...", flush=True)
    proc = subprocess.Popen(
        [CF, "tunnel", "--url", LOCAL_URL],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    url_sent = None
    try:
        for line in proc.stdout:  # type: ignore
            sys.stdout.write(line)
            sys.stdout.flush()
            m = URL_RE.search(line)
            if m and m.group(0) != url_sent:
                url_sent = m.group(0)
                threading.Thread(
                    target=_sync_after_delay, args=(cfg, url_sent), daemon=True
                ).start()
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.terminate()
    print(f"[sync] tunnel kapandi (exit {proc.returncode})", flush=True)


def main() -> None:
    cfg = load_secrets()
    while True:
        try:
            run_once(cfg)
        except KeyboardInterrupt:
            print("\n[sync] durduruldu.")
            return
        except Exception as e:
            print(f"[sync] hata: {e}", flush=True)
        print("[sync] 5 sn sonra tunnel yeniden baslatiliyor...", flush=True)
        time.sleep(5)


if __name__ == "__main__":
    main()
