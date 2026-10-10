"""Paneli guvenli yeniden baslatir (aura_studio.py tarafindan ayri surec olarak calistirilir).

1) Eski panelin portu birakmasini bekler.
2) aura_studio.py'yi baslatir ve saglikli acilmasini bekler.
3) Acilmazsa (sozdizimi/import/calisma hatasi) aura_studio.py'nin SON YEDEGINI geri yukleyip
   tekrar baslatir. Boylece panelden yapilan hatali bir duzenleme paneli kalici olarak oldurmez.
Kullanim: python safe_restart.py <port>
"""
import glob
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TARGET = os.path.join(ROOT, "aura_studio.py")
BACKUPS = os.path.join(HERE, "_backups")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8795
LOG = os.path.join(HERE, "_panel_run_log.txt")


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def port_open():
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def force_free_port():
    """Port hala acik durursa (cagiran kendi surecini kapatmayi unutmus/beklenmedik olum): onu tutan
    PID(ler)i bulup oldur. 2026-10-02: safe_restart.py dogrudan (restart_panel API disinda) cagrildiginda
    eski surec hic kapanmiyordu, sonraki start() port cakismasiyla sessizce basarisiz oluyordu ama
    wait_healthy() hala HAYATTA olan ESKI surecten 200 alip 'saglikli' saniyordu - port'u gercekten
    kimin tuttugunu dogrulamadan asla 'kapandi' denmeyecek."""
    if os.name != "nt":
        return
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        return
    pids = set()
    for line in out.splitlines():
        if f":{PORT} " in line and "LISTENING" in line:
            parts = line.split()
            if parts and parts[-1].isdigit():
                pids.add(parts[-1])
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
            log(f"Port {PORT}'u tutan PID {pid} zorla kapatildi.")
        except Exception:
            pass


def healthy():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/history", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def start():
    env = dict(os.environ, AURA_NO_OPEN="1", PYTHONIOENCODING="utf-8")
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    lf = open(LOG, "w", encoding="utf-8")
    return subprocess.Popen([sys.executable, TARGET], cwd=ROOT, env=env, stdout=lf,
                            stderr=subprocess.STDOUT, creationflags=flags)


def wait_healthy(proc, timeout=45):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return False
        if healthy():
            return True
        time.sleep(1)
    return False


def main():
    end = time.time() + 20
    while port_open() and time.time() < end:
        time.sleep(0.5)
    if port_open():
        log("Eski panel 20sn'de kendiliginden kapanmadi - port zorla serbest birakiliyor.")
        force_free_port()
        end2 = time.time() + 5
        while port_open() and time.time() < end2:
            time.sleep(0.5)
    else:
        log("Eski panel kapandi, yenisi baslatiliyor.")
    p = start()
    if wait_healthy(p):
        log("Panel saglikli acildi.")
        return 0
    log("Panel acilmadi! Son yedek geri yukleniyor.")
    try:
        p.kill()
    except Exception:
        pass
    time.sleep(1)
    baks = sorted(glob.glob(os.path.join(BACKUPS, "aura_studio.py.*.bak")), reverse=True)
    if not baks:
        log("Yedek yok - geri yukleme yapilamadi.")
        return 1
    shutil.copy2(baks[0], TARGET)
    log("Geri yuklendi: " + os.path.basename(baks[0]))
    p = start()
    if wait_healthy(p):
        log("Yedekle panel acildi.")
        return 0
    log("Yedekle de acilamadi. _panel_run_log.txt'ye bak.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
