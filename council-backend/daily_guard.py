"""
GUNLUK URETIM KORUYUCUSU - daily_auto.bat / daily_auto_evening.bat aura_engine.py'yi DOGRUDAN degil bunun
uzerinden calistirir.

Neden: 25 Eylul 2026 - bilgisayar 18:51'de gec acildi, internet/DNS henuz hazir degildi
("getaddrinfo failed"), planlama adimi cokti ve o gunun sabah videosu HIC cikmadi; motor cikis
kodu 0 dondugu icin kimse fark etmedi.

Ne yapar:
  1) Internet (DNS + TLS) gelene kadar bekler (en fazla 10 dk).
  2) aura_engine.py'yi calistirir, ciktisini oldugu gibi gecirir (log'a yazilir).
  3) Video YUKLENMEDIYSE ve hata gecici bir AG hatasiysa 5 dk bekleyip en fazla 2 kez tekrar dener.
     (Video yuklendiyse ASLA tekrar calistirmaz - cift yayin olmaz. Icerik/guvenlik reddi tekrar denenmez.)

Kullanim:  python daily_guard.py [aura_engine argumanlari]
"""
import re
import socket
import subprocess
import sys
import time

HOSTS = ["generativelanguage.googleapis.com", "www.googleapis.com", "api.openai.com"]
NET_MARKERS = re.compile(r"getaddrinfo failed|Errno 11001|Name or service not known|ConnectError|ConnectTimeout|"
                         r"ReadTimeout|Connection (?:reset|aborted)|10053|10054|timed out|"
                         r"Server error '5\d\d|503 Service|502 Bad Gateway", re.I)


def network_up(hosts=HOSTS, timeout=5):
    """En az bir API sunucusuna DNS + TCP:443 baglantisi kurulabiliyor mu."""
    for h in hosts:
        try:
            with socket.create_connection((h, 443), timeout=timeout):
                return True
        except OSError:
            continue
    return False


def wait_network(max_s=600, step=10, hosts=HOSTS):
    t0 = time.time()
    while time.time() - t0 < max_s:
        if network_up(hosts):
            return True
        time.sleep(step)
    return network_up(hosts)


def should_retry(output, uploaded):
    """Tekrar denenmeli mi: video yuklenmedi VE cikti gecici bir ag/sunucu hatasi iceriyor."""
    if uploaded:
        return False
    return bool(NET_MARKERS.search(output or ""))


def run_engine(args):
    p = subprocess.Popen([sys.executable, "-u", "aura_engine.py"] + args, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    buf = []
    for line in p.stdout:
        buf.append(line)
        sys.stdout.write(line)
        sys.stdout.flush()
    p.wait()
    return "".join(buf)


def main(args, max_retries=2, retry_wait=300):
    if not wait_network():
        print("[guard] internet 10 dk boyunca gelmedi - yine de deneniyor")
    else:
        print("[guard] internet hazir")
    for attempt in range(max_retries + 1):
        out = run_engine(args)
        uploaded = "YUKLENDI" in out
        if uploaded:
            print(f"[guard] video yuklendi (deneme {attempt + 1})")
            return 0
        if attempt < max_retries and should_retry(out, uploaded):
            print(f"[guard] gecici ag/sunucu hatasi - {retry_wait} sn sonra tekrar denenecek ({attempt + 1}/{max_retries})")
            time.sleep(retry_wait)
            wait_network()
            continue
        print("[guard] video yuklenmedi; tekrar denenmiyor (hata gecici ag hatasi degil ya da deneme hakki bitti)")
        return 0
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
