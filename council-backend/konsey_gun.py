"""KONSEY GUN - TEK KOMUTLA bir Konsey Short'u: konu -> kanca -> senaryo -> kapi -> (senin onayin) -> video -> (zamanli) ozel yukleme.

Kullanim:
  python konsey_gun.py                       # havuzdan siradaki kullanilmamis konu
  python konsey_gun.py --konu 21             # belirli konu (python konsey_konular.py ile listele)
  python konsey_gun.py --kategori gelecek    # o kategoriden siradaki konu
  python konsey_gun.py --saat "2026-10-16 02:30"   # yayin saatini bastan ver (TURKIYE saati); verilmezse sorar

Senin vereceğin kararlar (yalniz bunlar):
  1) Senaryo iyi mi?   evet = uret | 1-5 = o kancayla yeniden yaz | s 2 yeni cumle | b Yeni Baslik | k YENI KART | hayir = iptal
  2) Yayin saati (TR)  'YYYY-MM-DD HH:MM' = o saatte otomatik herkese acik | Enter = zamansiz ozel yukle | hayir = yukleme yok
  3) Ozeti onayla (evet)

Otomatik yaptigi: gunluk sinir kontrolu, ses sunucusunu (yalniz KAPALIYSA) acma, kanca adaylari, senaryo, kapilar (hook_gate, claim_lint,
isim yasagi, sensitivity_gate), video, yukleme. Ses sunucusu hazir degilse VIDEO URETMEZ (sessizce Groq sesine dusmez).
Guvenlik degismez: gunde en fazla 2 video, gercek isim/niyet atfi/suc dili/uydurma rakam yok, onaysiz yayin yok, zamanlayicilar yok.
"""
import argparse
import os
import socket
import subprocess
import sys
import time

import daily_limit
import konsey_format
import konsey_konular
import konsey_yukle

HERE = os.path.dirname(os.path.abspath(__file__))
SES_PORT = 8124
SES_BAT = os.path.join(HERE, "sign_council_voice.bat")


# --------------------------------------------------------------------------- yardimcilar (test edilebilir)
def sonraki_konu(kullanilan, kategori=None, konular=None, oncelik=None, elenen=None):
    """Kullanilmamis ilk konu: once oncelik listesi (ONERILEN_ILK), sonra id sirasi; ELENEN konular atlanir. kategori verilirse yalniz o kategori. Yoksa None."""
    if elenen is None:
        elenen = konsey_konular.ELENENLER if konular is None else set()     # disaridan konu listesi verilirse (test) eleme uygulanmaz
    konular = konular if konular is not None else konsey_konular.KONULAR
    oncelik = oncelik if oncelik is not None else konsey_konular.ONERILEN_ILK
    sira = [k for i in oncelik for k in konular if k["id"] == i] + [k for k in konular if k["id"] not in oncelik]
    for k in sira:
        if k["id"] in elenen:
            continue
        if kategori and k["kategori"] != kategori:
            continue
        if k["konu"].lower() not in kullanilan:
            return k
    return None


def port_acik(port=SES_PORT, host="127.0.0.1", timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False


def sunucu_baslat():
    """Ses sunucusunu YENI pencerede acar (Windows: cift tiklamayla ayni). Yalniz port KAPALIYKEN cagrilir."""
    if hasattr(os, "startfile"):
        os.startfile(SES_BAT)          # noqa: S606 - yerel, repodaki .bat
    else:
        subprocess.Popen(["bash", SES_BAT], cwd=HERE)


def sunucu_bekle(acik=port_acik, bekle_sn=150, uyku=2, simdi=time.monotonic, uyu=time.sleep):
    """Port acilana kadar bekler. -> bool"""
    bitis = simdi() + bekle_sn
    while simdi() < bitis:
        if acik():
            return True
        uyu(uyku)
    return acik()


def sunucu_hazirla(acik=port_acik, baslat=sunucu_baslat, yaz=print):
    """Acik degilse bir kez baslatir (ikinci pencere ACMAZ: bat eskisini oldururdu). -> baslatildi_mi"""
    if acik():
        yaz("  [ses sunucusu] zaten acik, dokunulmadi.")
        return False
    yaz("  [ses sunucusu] kapali - aciliyor (~30 sn, arka planda yuklenir)...")
    baslat()
    return True


# --------------------------------------------------------------------------- ana akis
def calistir(a, d):
    """a: argparse sonucu (konu, kategori, saat). d: bagimlilik sozlugu (hepsi enjekte edilebilir):
    gir(prompt)->str, yaz(str), llm(prompt)->str, parse, render(topic, r)->meta, yukle(meta, yayin_utc)->(vid, mesajlar),
    izle(yol), kullanilan()->set, gunluk()->(izin, info), sunucu_hazirla(), sunucu_bekle()->bool, kaydet(topic, r)
    -> cikis kodu"""
    yaz, gir = d["yaz"], d["gir"]

    izin, info = d["gunluk"]()
    if not izin:
        yaz(f"Gunluk sinira ulasildi ({info['count']}/{daily_limit.MAX_DAILY}); bugun yeni video YOK. Yarin tekrar dene.")
        return 0

    # 1) konu
    if a.konu is not None:
        k = konsey_konular.konu_bul(a.konu)
        if k is None:
            yaz(f"Havuzda {a.konu} numarali konu yok (python konsey_konular.py).")
            return 2
    else:
        k = sonraki_konu(d["kullanilan"](), a.kategori)
        if k is None:
            yaz("Havuzda kullanilmamis konu kalmadi" + (f" ({a.kategori} kategorisinde)" if a.kategori else "") + ". Yeni konu ekleyelim.")
            return 2
    topic = k["konu"]
    yaz(f"\nKONU {k['id']}: {topic}\n  ({k['tr']})  [{k['kategori']}]")
    if k["id"] in konsey_konular.ELENENLER:
        yaz(f"  [uyari] Bu konu ELENMIS: {konsey_konular.ELENENLER[k['id']]} (elle secildigi icin devam ediliyor)")

    # 2) ses sunucusu (arka planda yuklensin diye hemen)
    d["sunucu_hazirla"]()

    # 3) kanca adaylari + senaryo
    kk = konsey_format.kanca_sec(topic, d["llm"])
    yaz("\nKANCA ADAYLARI:")
    for i, (h, ok) in enumerate(kk["adaylar"], 1):
        yaz(f"  {i}. [{'+' if ok else '-'}] {h}{'   <== SECILEN' if h == kk['secilen'] else ''}")
    secilen = kk["secilen"]

    r = None
    gecersiz = False
    yeniden = True
    for _tur in range(12):
        if yeniden:
            r = konsey_format.uret(topic, d["llm"], d["parse"], kanca=secilen)
            gecersiz = not r["ok"]
            if gecersiz:
                yaz("\nSENARYO (deneme %d):" % r["deneme"])
                for i, (who, screen, line, _img) in enumerate(r["beats"], 1):
                    yaz(f"  {i}. {who:5} | {line}")
                yaz(f"  BASLIK: {r['title']}   KART: {r['hookthumb']}")
                yaz("\nKAPIDAN GECMEDI - video uretilmeyecek:")
                for kod, msg in r["sorunlar"]:
                    yaz(f"  - {kod}: {msg}")
                if not d.get("tamir"):
                    return 2
                yaz("\n[tamir modu] Satirlari elle duzeltebilirsin (s N yeni cumle | b Baslik | k KART); her degisiklik kapidan gecer; "
                    "senaryo kapidan gecene kadar 'evet' KABUL EDILMEZ. hayir = iptal.")
        if not gecersiz:
            yaz("\nSENARYO (deneme %d):" % r["deneme"])
            for i, (who, screen, line, _img) in enumerate(r["beats"], 1):
                yaz(f"  {i}. {who:5} | {line}")
            yaz(f"  BASLIK: {r['title']}   KART: {r['hookthumb']}")
            for ad, hits in r.get("uyarilar", []):
                yaz(f"  [uyari] {ad}: {', '.join(hits)}")
            g = d["duyarlilik"](topic, r)
            yaz(f"  [sensitivity_gate: sensitive={g['sensitive']} severity={g['severity']}]")
            if g["sensitive"]:
                yaz("DUYARLILIK KAPISI: insan incelemesi gerekir - video uretilmeyecek. " + g.get("reason", ""))
                return 2
        ham = gir("\nSenaryo iyi mi?  evet = uret | 1-5 = o kancayla yeniden yaz | s 2 yeni cumle = 2. satiri degistir | "
                  "b Yeni Baslik | k YENI KART | hayir = iptal > ")
        cevap = ham.strip().lower()
        if cevap in ("evet", "e", "yes", "y"):
            if gecersiz:
                yaz("  Senaryo henuz kapidan gecmedi: once yukaridaki sorunlari s/b/k komutlariyla duzelt.")
                continue
            break
        komut = konsey_format.duzenleme_coz(ham)
        if komut:
            yeni_r, sorun = konsey_format.duzenle(r, komut, kanca=secilen)
            if yeni_r is None:
                yaz("  DEGISIKLIK KAPIDAN GECMEDI (senaryo ayni kaldi):")
                for kod, msg in sorun:
                    yaz(f"  - {kod}: {msg}")
            else:
                r = yeni_r
                gecersiz = False
                yaz("  -> degisti.")
            yeniden = False
            continue
        if cevap.isdigit() and 1 <= int(cevap) <= len(kk["adaylar"]) and kk["adaylar"][int(cevap) - 1][1]:
            secilen = kk["adaylar"][int(cevap) - 1][0]
            yaz(f"  -> kanca: {secilen}")
            yeniden = True
            gecersiz = False
            continue
        yaz("Iptal edildi. Hicbir sey uretilmedi/yuklenmedi.")
        return 0
    else:
        yaz("Cok fazla tur; iptal.")
        return 0

    d["kaydet"](topic, r)

    # 4) video - ses sunucusu HAZIR degilse uretme (sessizce Groq'a dusmesin)
    if not d["sunucu_bekle"]():
        yaz("\nSes sunucusu (:8124) hazir olmadi - video URETILMEDI (yanlis sesle uretmemek icin). Pencereyi kontrol edip tekrar calistir.")
        return 2
    yaz("\nVideo uretiliyor (~2-3 dk)...")
    meta = d["render"](topic, r)
    yaz(f"\nVIDEO HAZIR: {meta['file']}  (~{meta.get('seconds', '?')} sn)")
    d["izle"](meta["file"])
    yaz("  (video oynaticida acildi - izle)")

    # 5) yayin saati + yukleme
    yayin = None
    saat = a.saat
    for _ in range(3):
        if saat is None:
            saat = gir("\nYayin saati (TR) 'YYYY-MM-DD HH:MM' = o saatte otomatik herkese acik | Enter = zamansiz ozel yukle | hayir = yukleme yok > ").strip()
        if saat.lower() in ("hayir", "h", "no", "n"):
            yaz("Yukleme yapilmadi. Video hazir: " + meta["file"])
            return 0
        if saat == "":
            break
        try:
            yayin = konsey_yukle.zamanla_utc(saat)
            break
        except ValueError as e:
            yaz(str(e))
            saat = None
    else:
        yaz("Gecerli saat girilmedi; yukleme yapilmadi. Video hazir: " + meta["file"])
        return 0

    vid, mesajlar = d["yukle"](meta, yayin)
    if not vid:
        for m in mesajlar:
            yaz(m)
        return 2
    if yayin:
        yaz(f"\nYUKLENDI ve ZAMANLANDI: https://youtu.be/{vid}  ({saat} TR saatinde kendiliginden herkese acik olacak)")
    else:
        yaz(f"\nYUKLENDI (OZEL, zamanlanmadi): https://youtu.be/{vid}   (yayinlamak icin Studio'dan zamanla/yayinla; sonraki videoda --saat kullanabilirsin)")
    yaz("\nTEK ELLE ISIN (API sabitlemeyi desteklemez): video yayinlaninca su yorumu yaz ve SABITLE:")
    yaz(f"  {meta['sabit_yorum']}")
    return 0


# --------------------------------------------------------------------------- gercek bagimliliklar
def _gercek():
    import make_topic_short as mts
    from sensitivity_gate import assess

    def llm(prompt):
        return mts.call_gemini([{"role": "user", "content": prompt}], "You are the Sign Council head writer. Follow the format exactly.")

    def yukle(meta, yayin_utc):
        def upload(file, title, desc, tags, publish_at=None):
            from upload_youtube import upload_video
            return upload_video(file, title, desc, tags=tags, privacy_status="private", publish_at=publish_at)

        def onay(ozet):
            print(ozet)
            return input("Onayliyor musun? (evet/hayir) > ").strip().lower() in ("evet", "e", "yes", "y")
        return konsey_yukle.yukle(meta, upload, onay, yayin_utc=yayin_utc)

    def izle(yol):
        if hasattr(os, "startfile"):
            os.startfile(yol)          # noqa: S606 - varsayilan oynatici

    return {
        "yaz": print, "gir": input, "llm": llm, "parse": mts._parse_script, "tamir": True,
        "render": mts.konsey_video, "yukle": yukle, "izle": izle,
        "kullanilan": konsey_konular.kullanilanlar,
        "gunluk": lambda: daily_limit.can_upload(konsey_yukle.gunluk_dosya()),
        "sunucu_hazirla": sunucu_hazirla, "sunucu_bekle": sunucu_bekle,
        "duyarlilik": lambda topic, r: assess(topic, " ".join(b[2] for b in r["beats"]), r["title"]),
        "kaydet": lambda topic, r: konsey_format.senaryo_kaydet(konsey_format.KAYIT_YOL, topic, r),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Konsey Short'u - tek komut")
    ap.add_argument("--konu", type=int, default=None, help="havuz konu numarasi")
    ap.add_argument("--kategori", default=None, help="siradaki konuyu yalniz bu kategoriden sec (afet, sehir, robot, uzay, insan, son, fizik, gelecek, para, yemek, teknoloji, sosyal, iş, ev)")
    ap.add_argument("--saat", default=None, help="yayin saati, TURKIYE saati 'YYYY-MM-DD HH:MM' (verilmezse sorulur)")
    a = ap.parse_args(argv)
    if not sys.stdin.isatty():
        print("Etkilesimli terminal gerekli (onay sorulari var).")
        return 2
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    return calistir(a, _gercek())


if __name__ == "__main__":
    sys.exit(main())
