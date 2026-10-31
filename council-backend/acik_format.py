"""ACIK FORMAT (aciklayici Short) - bir SORUYA cevap veren, kaynakli rakamli, TEK anlatici (aura), ~45 sn, arama dostu baslikli video.

Neden (31 Eki 2026): Konsey (karakter tartismasi) formati soguk izleyiciye anlasilmiyor (%71-92 kaydirma); trafigin %24'u ARAMADAN; kanalin tek abonesi
aciklayici bir videodan geldi. Karakter tartismasi yerine 'soru -> kaynakli cevap' deneniyor. Hicbir sey yuklemez.

Kurallar (kapi = kontrol_acik): yalniz rakam_bankasi olgularindaki rakamlar (+kosulu), kaynak adi sozlu gecer, gercek sirket/kisi adi yok (kaynak kurumlari serbest),
claim_lint engelleyicileri + niyet/suc dili yok, 5 satir (hepsi aura), 55-105 kelime, kanca = '?' ile biten 10 kelimeyi gecmeyen soru.
"""
import re

import claim_lint
import konsey_format
import rakam_bankasi

SIRA = ["aura"] * 5
TOPLAM_MIN, TOPLAM_MAX, SATIR_MAX, KANCA_MAX, BASLIK_MAX = 55, 105, 26, 10, 70

# anahtar -> baslik (arama ifadesi), olgularin bulundugu havuz konusu, olgu kimlikleri icin kisa kaynak adi
ACIK_KONULAR = {
    "deniz": {"baslik": "How Much Would Sea Level Rise If All the Ice Melted?", "konu": "What if all the ice on Earth melted?",
              "yasak": ["glacier", "glaciers"], "not": "Say 'all the ice on land' (mostly Antarctica and Greenland); NEVER say 'glaciers': the mountain glaciers alone hold far less ice, so the 60 meters figure would be wrong.",
              "kaynak_kisa": {"buz_toplam": "NASA", "gronland": "Scientific American", "deniz_1880": "NASA"}},
    "robot": {"baslik": "How Many Humanoid Robots Shipped in 2025?", "konu": "What if robots were built like cars, one a minute?",
              "kaynak_kisa": {"robot_18000": "IDC"}},
    "sel": {"baslik": "How Deep Must Flood Water Be To Move a Car?", "konu": "What if 60 centimeters of water ran down your street?",
            "kaynak_kisa": {"sel_15cm": "National Weather Service", "sel_30cm": "National Weather Service", "sel_60cm": "National Weather Service"}},
}

PROMPT = (
    "Write a vertical YouTube Short (about 45 seconds spoken) that ANSWERS one real question for curious viewers. ONE narrator (aura). No debate, no characters.\n\n"
    "QUESTION (the video's title idea): {baslik}\n\n"
    "VERIFIED FACTS - the ONLY numbers, measurements and years you may use; copy each number exactly, never round or invent another. "
    "Say the source's short name aloud when you state a number ('according to NASA'):\n{olgular}\n\n"
    "Output EXACTLY 5 lines in this format: aura | SCREEN | LINE | IMAGE\n"
    "- SCREEN: 2-4 word ALL-CAPS on-screen phrase (put the key number here when the line states it).\n"
    "- LINE: plain spoken English, short sentences, no jargon, no markdown. Line 1: 10 words or fewer. Lines 2-5: 26 words or fewer. TOTAL 55-105 words.\n"
    "- IMAGE: one-sentence cinematic photo prompt of a concrete scene for this line; no text, logos or people's faces. Line 1's image is the FIRST FRAME: "
    "the most dramatic, high-contrast close-up.\n\n"
    "STRUCTURE:\n"
    "1 HOOK: the question put directly to the viewer, ending with '?' (10 words or fewer).\n"
    "2 ANSWER: the key number straight away, with 'according to <source>'. State any condition it depends on (for example 'if ALL the ice melted').\n"
    "3 SCALE: what that number means in everyday terms, with NO new numbers.\n"
    "4 SECOND FACT or surprise, taken only from the facts above.\n"
    "5 CLOSE: one memorable thought, then ONE question inviting the viewer to guess or comment, ending with '?'. Say the source name once more.\n\n"
    "HARD RULES:\n"
    "- Do NOT name any company, product or person; naming the SOURCE institution from the facts is fine.\n"
    "- Never attribute intent or wrongdoing; no crime language. No medical advice. Never present a prediction as certain.\n"
    "- The linter matches word FRAGMENTS, so avoid: right, bright, origin, original, trigger, believe, belief, enforce, quiet, apply/applies, flying, flies, alien, lie, rig.\n"
    "- Use only the numbers given above (plus small counts like 'three'). Never use 'suddenly', 'every' or 'always' as a claim.\n"
    "{not}\n\n"
    "After the 5 lines add:\n"
    "TITLE: {baslik}\n"
    "HOOKTHUMB: <2-4 ALL CAPS words for the opening card>"
)


def olgu_metni(anahtar):
    k = ACIK_KONULAR[anahtar]
    return "\n".join(f"- {o['olgu']} (source: {k['kaynak_kisa'].get(o['id'], o['kaynak'])})" for o in rakam_bankasi.olgular(k["konu"]))


def prompt_uret(anahtar):
    k = ACIK_KONULAR[anahtar]
    return PROMPT.format(baslik=k["baslik"], olgular=olgu_metni(anahtar), **{"not": ("- " + k["not"]) if k.get("not") else ""})


def _kelime(s):
    return len(re.findall(r"[A-Za-z0-9'%$.,-]+", s or ""))


def kullanilan_olgular(anahtar, metin):
    k = ACIK_KONULAR[anahtar]
    return [o for o in rakam_bankasi.olgular(k["konu"]) if any(rakam_bankasi._sayi_var(n, metin) for n in o["sayilar"])]


def kontrol_acik(beats, title, hookthumb, anahtar):
    """-> [(kod, mesaj)]. Bos = gecti. Hicbir guvenlik kuralini gevsetmez."""
    k = ACIK_KONULAR[anahtar]
    konu = k["konu"]
    s = []
    if len(beats) != 5:
        return [("SATIR_SAYISI", f"5 satir olmali, {len(beats)} geldi.")]
    if [b[0] for b in beats] != SIRA:
        s.append(("SIRA", "Tum satirlar 'aura' olmali (tek anlatici)."))
    L = [b[2] for b in beats]
    metin = " ".join(L)
    toplam = sum(_kelime(x) for x in L)
    if not TOPLAM_MIN <= toplam <= TOPLAM_MAX:
        s.append(("UZUNLUK", f"Toplam {toplam} kelime ({TOPLAM_MIN}-{TOPLAM_MAX} olmali)."))
    for i, x in enumerate(L, 1):
        if _kelime(x) > (KANCA_MAX if i == 1 else SATIR_MAX):
            s.append(("SATIR_UZUN", f"{i}. satir {_kelime(x)} kelime (en fazla {KANCA_MAX if i == 1 else SATIR_MAX})."))
    if not L[0].strip().endswith("?"):
        s.append(("KANCA_SORU", "1. satir bir soruyla ('?') bitmeli."))
    if not L[4].strip().endswith("?"):
        s.append(("KAPANIS_SORU", "Kapanis izleyiciye bir soruyla ('?') bitmeli."))
    if not title or len(title) > BASLIK_MAX:
        s.append(("BASLIK", f"Baslik 1-{BASLIK_MAX} karakter olmali."))
    ekran = " ".join(b[1] for b in beats)          # ekrandaki yazilar da sozlu satirlar kadar denetlenir (sayi/iddia)
    tum = metin + " " + (title or "") + " " + (hookthumb or "") + " " + ekran
    # rakam bankasi
    kaynaksiz = rakam_bankasi.yasakli_rakamlar(tum, konu)
    if kaynaksiz:
        s.append(("RAKAM_KAYNAK", f"Kaynaksiz rakam: {', '.join(kaynaksiz)}. Yalniz VERIFIED FACTS'teki rakamlar."))
    eksik = rakam_bankasi.onkosul_eksik(metin, konu)      # kosul SOZLU satirlarda gecmeli (baslikta gecmesi yetmez)
    if eksik:
        s.append(("ONKOSUL_EKSIK", f"Rakamin bagli oldugu kosul soylenmedi ({', '.join(eksik)})."))
    kul = kullanilan_olgular(anahtar, metin)
    if not kul:
        s.append(("OLGU_YOK", "Kaynakli bir rakam (VERIFIED FACTS) kullanilmadi; aciklayici video rakamli olmali."))
    else:
        kisalar = {k["kaynak_kisa"].get(o["id"], o["kaynak"]) for o in kul}
        if not any(re.search(re.escape(x), metin, re.I) for x in kisalar):
            s.append(("KAYNAK_ADI", f"Kaynak adi sozlu gecmeli: {', '.join(sorted(kisalar))}."))
    # guvenlik: claim_lint engelleyicileri (kaynakli rakam muaf), isim yasagi (kaynak kurumlari serbest), davranis iddiasi
    for ad, hits, why in claim_lint.lint(tum):
        if ad == "RAKAM" and hits and all(rakam_bankasi.rakam_kaynakli(h, konu) for h in hits):
            continue
        if ad in konsey_format.ENGELLEYICI:
            s.append(("LINT_" + ad.replace(" ", "_").replace("/", "_"), f"{ad}: {', '.join(hits)} - {why}"))
    serbest = {x.lower() for v in k["kaynak_kisa"].values() for x in v.split()}
    isim = sorted({m.group(0).lower() for m in konsey_format._entities().finditer(tum)} - serbest)
    if isim:
        s.append(("GERCEK_ISIM", f"Gercek sirket/urun adi yasak: {', '.join(isim)}."))
    if konsey_format.DAVRANIS_IDDIA.search(metin):
        s.append(("DAVRANIS_IDDIA", "Kaynaksiz davranis/neden-sonuc iddiasi yasak."))
    yasak = [w for w in k.get("yasak", []) if re.search(rf"\b{re.escape(w)}\b", tum, re.I)]
    if yasak:
        s.append(("YASAK_KELIME", f"Bu konuda kullanilamaz: {', '.join(yasak)} ({k.get('not', '')})"))
    if re.search(r"\bsuddenly\b", tum, re.I):
        s.append(("YASAK_KELIME", "'suddenly' zaman iddiasi: kullanma."))
    if konsey_format.ISTATISTIK.search(tum):
        s.append(("ISTATISTIK", "Kaynaksiz oran/istatistik kalibi ('half of', '1 in 3' ...) yasak."))
    return s


def aciklama(r, anahtar):
    """YouTube aciklamasi: kanca + kaynaklar satiri (rakam kullanildiysa) + etiketler."""
    kaynak = rakam_bankasi.kaynak_satiri(ACIK_KONULAR[anahtar]["konu"], " ".join(b[2] for b in r["beats"]) + " " + r["title"])
    return f"{r['beats'][0][2]}\n\n" + (f"{kaynak}\n\n" if kaynak else "") + "#Shorts #SignCouncil"


def uret(anahtar, llm, parse, deneme=5):
    """Kapidan gecmezse sorunlari geri besleyip yeniden yazdirir (en fazla 'deneme'). -> dict(ok, beats, title, hookthumb, sorunlar, deneme)"""
    temel = prompt_uret(anahtar)
    prompt, beats, title, hookthumb, sorunlar = temel, [], "", "", []
    for n in range(1, deneme + 1):
        beats, title, hookthumb = parse(llm(prompt))
        title = ACIK_KONULAR[anahtar]["baslik"]          # baslik arama ifadesi: modelin degil bizim
        sorunlar = kontrol_acik(beats, title, hookthumb, anahtar)
        if not sorunlar:
            return {"ok": True, "anahtar": anahtar, "beats": beats, "title": title, "hookthumb": hookthumb, "sorunlar": [], "deneme": n}
        prompt = temel + "\n\nYour previous attempt was REJECTED for these reasons - fix every one and keep all rules:\n" + "\n".join(f"- {m}" for _, m in sorunlar)
    return {"ok": False, "anahtar": anahtar, "beats": beats, "title": title, "hookthumb": hookthumb, "sorunlar": sorunlar, "deneme": deneme}


def duzenle(r, komut):
    """('s', n, metin) | ('e', n, EKRAN) | ('b', metin) | ('k', metin) -> (yeni_r | None, sorunlar). Gecmezse r DEGISMEZ."""
    beats, title, kart = list(r["beats"]), r["title"], r["hookthumb"]
    if komut[0] == "s":
        n = int(komut[1])
        if not 1 <= n <= len(beats):
            return None, [("SATIR_NO", f"1-{len(beats)} arasi olmali.")]
        who, screen, _eski, img = beats[n - 1]
        beats[n - 1] = (who, screen, komut[2].strip(), img)
    elif komut[0] == "e":
        n = int(komut[1])
        if not 1 <= n <= len(beats):
            return None, [("SATIR_NO", f"1-{len(beats)} arasi olmali.")]
        who, _eski, line, img = beats[n - 1]
        beats[n - 1] = (who, " ".join(komut[2].split()).upper(), line, img)
    elif komut[0] == "b":
        title = komut[1].strip()
    elif komut[0] == "k":
        kart = " ".join(komut[1].split()).upper()
    else:
        return None, [("KOMUT", "Bilinmeyen duzenleme.")]
    sorunlar = kontrol_acik(beats, title, kart, r["anahtar"])
    if sorunlar:
        return None, sorunlar
    return {**r, "beats": beats, "title": title, "hookthumb": kart}, []
