"""KONSEY KARAKTER TARTISMASI FORMATI - ~25 sn, 6 satir, gunluk-hayat konulari. Saf fonksiyonlar (LLM disaridan verilir; test edilebilir).

Tasarim (13 Ekim 2026, sahip onayi): her karakterin tekrar eden bir KUSURU/isareti (tell) var; izleyici onu yakalar, yorumda taraf tutar.
  1 aura  : kanca (<=8 kelime), konuyu acar, gizli favorisi var (Alpha)
  2 alpha : mekanizmayi soyler, daha kazanmadan "That's one for me." der (puan tutuyor)
  3 beta  : "Hold on." diye girer, itiraz eder, cozum onermez
  4 delta : "Actually... <isim>, you're correct." - son konusanin tarafina gecer ('right' YASAK: claim_lint 'rig' desenini kelime
            siniri olmadan arar ve 'right'i niyet atfi sayar; linter gevsetilmedi)
  5 gamma : kisa ahlak notu + "I do this too, honestly." itirafi
  6 aura  : kapanis - (varsa skor) + "Team Alpha or Team Beta?" + suclu aliskanlik sorusu
Skoru LLM YAZMAZ: _engine/konsey_skor.json'dan kod ekler; oylari sahip gercek yorumlardan sayip girer (python konsey_format.py --oy alpha 3).

Guvenlik (dokunulmaz kurallar korunur, GEVSETILMEZ):
- hook_gate (kanca/baslik/kapanis) + claim_lint engelleyici kurallari (NIYET ATFI, SUC DILI, KARSILASTIRMA/ETIKET) + RAKAM da engelleyici
  (uydurma istatistik riski) + gercek sirket/kisi ismi YASAK (sensitivity_gate._ENTITIES). Kapidan gecmeyen senaryodan video URETILMEZ.
- Bu modul yayin/yukleme yapmaz.
"""
import argparse
import json
import os
import re
import sys

import claim_lint
import hook_gate
import konsey_konular
import rakam_bankasi

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
SKOR_YOL = os.path.join(ENGINE, "konsey_skor.json")
KAYIT_YOL = os.path.join(HERE, "output", "shorts", "topic", "konsey_son_senaryo.json")   # make_topic_short.KONSEY_KAYIT ile ayni

SIRA = ["aura", "alpha", "beta", "delta", "gamma", "aura"]
BASLIK_MAX = 40
TOPLAM_KELIME_MAX = 80
SATIR_KELIME_MAX = 16      # 2-5. satirlar
KAPANIS_KELIME_MAX = 22    # skor cumlesi haric
ENGELLEYICI = set(claim_lint.BLOCKING) | {"RAKAM"}
SOYUT = re.compile(r"\b(access|trade[sd]?|values?|benefits?|systems?|models?|mechanisms?|consumers?|expenses?|optimi[sz]\w*|"
                   r"leverage[sd]?|framework|incentives?|efficien\w+|structure[sd]?)\b", re.I)

ORNEK = """aura | SMALL BILLS ADD UP | Small bills just add up. | a pile of unopened envelopes on a kitchen table
alpha | MONTHLY MATH | Each plan looks cheap alone. Together they eat your pay. That's one for me. | a calculator beside a stack of receipts
beta | HOLD ON | Hold on. So I pay monthly for things I forgot I own? | a person squinting at a phone screen
delta | SIDE SWITCH | Actually... Beta, you're correct. Forgetting is the real cost. | a seesaw tipping in an empty playground
gamma | CHECK YOUR LIST | Review your plans every few months. I do this too, honestly. I forgot a gym plan. | a gym bag collecting dust in a closet
aura | PICK A TEAM | Team Alpha or Team Beta? What's your guilty habit? | two doors, one red and one blue
TITLE: Are Small Plans Worth It?
HOOKTHUMB: SMALL BILLS ADD UP"""

PROMPT = (
    "Write a vertical YouTube Short script (about 25 seconds spoken) for Sign Council: five AI characters argue about an "
    "EVERYDAY consumer/life topic, and the viewer takes a side in the comments.\n\n"
    "Topic: {topic}\n\n"
    "Output EXACTLY 6 lines, in this exact speaker order: aura, alpha, beta, delta, gamma, aura. Format per line:\n"
    "SPEAKER | SCREEN | LINE | IMAGE\n"
    "- SCREEN: 2-4 word ALL-CAPS on-screen phrase.\n"
    "- LINE: how friends argue out loud - short, plain, concrete words, no jargon, no markdown. Lines 2-5: 14 words or "
    "FEWER. Last line: 20 words or fewer. TOTAL under 75 words.\n"
    "- IMAGE: one-sentence cinematic photo prompt of a concrete everyday object or scene for this line; no text, logos, "
    "robots or AI cliches.\n\n"
    "CHARACTERS (each has a flaw that must show every time):\n"
    "1 AURA opens with the HOOK: 4-7 words, a bold CONTRADICTION or a small concrete number about the topic (not a slow "
    "'Why do...' question). Never start with 'The claim', 'Today', 'Hello', 'Did you know'. The hook MUST contain a digit, a question mark, or one "
    "of these exact words: but, not, never, why, how, wrong, missing, only, just, nobody, everyone, still, versus, worst, "
    "best, first, last, stop, before, after, instead. Aura secretly favors Alpha.\n"
    "2 ALPHA explains the mechanism coldly, then ends with the exact words 'That's one for me.' (he keeps score, "
    "prematurely).\n"
    "3 BETA starts with 'Hold on.' and pushes back with a sharp question. Beta never offers a solution.\n"
    "4 DELTA, people-pleaser, switches sides: 'Actually... <Alpha or Beta>, you're correct.' plus one short reason.\n"
    "5 GAMMA gives one short moral point, then confesses with the exact words 'I do this too, honestly.' followed by "
    "the guilty habit in a few words.\n"
    "6 AURA closes: exactly one sentence 'Team Alpha or Team Beta?' then asks the viewer for THEIR guilty habit "
    "(use the word 'guilty' or 'habit'). Do not write any score; the system adds it.\n\n"
    "STYLE: every line names ONE concrete everyday thing, moment or action (socks, a phone, a receipt, a cart, a Sunday "
    "night). Never abstract words like access, trade, value, benefit, system, model, mechanism, consumer, expense, "
    "structure, incentive, efficiency. Delta's reason must be a believable everyday consequence of what was just said, "
    "not a new topic.\n\n"
    "HARD RULES (a script that breaks one is thrown away):\n"
    "- Do NOT name any real company, brand, product, app or person. Use generic words (online stores, streaming "
    "services, a phone plan).\n"
    "- NO statistics, percentages, dollar/money amounts or 'million/billion/k' figures. Small counts of things are "
    "fine ('three fees'). The only exception: numbers listed under VERIFIED FACTS below, if any.\n"
    "- NEVER attribute intent or wrongdoing: do not use the words hidden, hide, trap, lie, scam, fraud, secret, "
    "deliberate, intentional, rigged, manipulate, force, illegal, crime, cheat. Explain the STRUCTURE and incentives "
    "in neutral words.\n"
    "- The linter matches word FRAGMENTS, so also avoid words like right, bright, origin, trigger, believe, belief, "
    "enforce, strap, quiet, FLYING, FLIES, alien - use simple synonyms (say 'correct', not 'right'; say 'fly' or 'airborne', never 'flying' or 'flies'; "
    "say 'visitors from space', never 'alien').\n"
    "- NO ratios or fractions of any kind ('1 in 3', 'half of', 'most of', 'thousands of', 'percent', '3 times') and NO claims about "
    "how accurate, safe, reliable or often wrong any group is (doctors, teachers, drivers, AI, stores). Ask a question or state a "
    "personal preference instead of a fact. On medical topics (doctors, pills, diagnosis, surgery) never claim anyone is wrong, "
    "accurate, safe, dangerous or harmful - ask questions only.\n"
    "- Do not use comparisons with the word 'than'. Avoid 'always', 'never', 'everyone', 'nobody' as claims.\n"
    "- Every claim must be common knowledge about how everyday things work; no news, no accusations.\n"
    "FORMAT EXAMPLE ONLY (different topic - copy the rhythm and the tells, never the content):\n"
    + ORNEK + "\n"
    "After the 6 lines add:\n"
    "TITLE: <max 40 characters, no colon, no quotes, a question or contradiction about the topic>\n"
    "HOOKTHUMB: <3-5 ALL CAPS words for the opening card, not generic>"
)

# --------------------------------------------------------------------------- EVREN formati (afet/sehir/robot/uzay/insan/son/fizik)
# Gunluk-hayat formati 'I do this too, honestly' + 'guilty habit' ile biter; buyuk what-if konularinda bu uymuyor (17 Ekim 2026, konu 79 denemesi).
# Evren formati: Gamma kisisel SECIM soyler ('I'd grab ...'), kapanis izleyiciye kisisel secim sorusu sorar (Which city would you save?) - yorumlari
# espri yerine kisisel cevaba ceker. Beta: en rahatsiz edici takip sorusu, olguyu asla inkar etmez.
EVREN_KATEGORILERI = {"afet", "sehir", "robot", "uzay", "insan", "son", "fizik"}

ZAMAN_SIMDI = re.compile(r"\b(now|today|tonight|breaking|happening|happens)\b", re.I)
KUCUK_OLCEK = re.compile(r"\b(benche?s?|chairs?|towels?|driveways?|pants|umbrellas?|sandals?|socks?|toys?)\b", re.I)

ORNEK_EVREN = """aura | RIVER STREETS | Your street, but it's a river? | a flooded city street at dusk, water reflecting neon signs
alpha | WATER MATH | Rain needs somewhere to go. Drains fill first, then streets. That's one for me. | storm drains overflowing at the curb
beta | HOLD ON | Hold on. Where do the cars sleep tonight? | rows of parked cars with water at the door handles
delta | SIDE SWITCH | Actually... Beta, you're correct. Parked cars are the first thing people lose. | a car roof barely above the water
gamma | MY PICK | Pack light, move early. I'd grab my photos and one warm coat. | a backpack by a front door
aura | PICK A TEAM | Team Alpha or Team Beta? Which room would you save first? | a dark apartment with one lit window
TITLE: Could Streets Become Rivers?
HOOKTHUMB: STREETS BECOME RIVERS"""

def evren_mi(topic):
    i = rakam_bankasi.konu_id(topic)
    k = konsey_konular.konu_bul(i) if i is not None else None
    return bool(k and k["kategori"] in EVREN_KATEGORILERI)


# EVREN_PROMPT asagida, ORNEK_EVREN tanimindan sonra

def _evren_prompt():
    t = PROMPT
    degisim = [
        ("an EVERYDAY consumer/life topic", "a BIG what-if topic (disasters, future cities, robots, space, the human body, the end of the world)"),
        ("(socks, a phone, a receipt, a cart, a Sunday night)", "(a coastline, a rocket, a street, a robot arm, a harbor)"),
        ("- Every claim must be common knowledge about how everyday things work; no news, no accusations.\n",
         "- Every claim is the topic's what-if premise, a VERIFIED FACT, or plain common sense. This is a WHAT-IF, not news: never say it is happening now, "
         "never use the words now, today, tonight, breaking. Consequences must match the SCALE of the event: for a big event name big things "
         "(coastlines, ports, whole streets, neighborhoods, power, water), never tiny objects (benches, chairs, towels, driveways, pants).\n"),
        (ORNEK, ORNEK_EVREN),
    ]
    for a, b in degisim:
        assert a in t, a
        t = t.replace(a, b)
    for desen, yeni in [
        (r"^3 BETA .*$", "3 BETA starts with 'Hold on.' and asks the most unsettling follow-up question about the scenario. Beta never denies the scenario and never offers a solution."),
        (r"^5 GAMMA .*$", "5 GAMMA gives one short practical point, then states a personal choice starting with the exact words \"I'd\" or \"I would\" (what Gamma would grab, do or choose)."),
        (r"^6 AURA closes.*$", "6 AURA closes: exactly one sentence 'Team Alpha or Team Beta?' then asks the viewer ONE personal-choice question starting with Which, Where or What would you (for example 'Which city would you save?'). Do not write any score; the system adds it."),
    ]:
        t, n = re.subn(desen, lambda m, y=yeni: y, t, flags=re.M)
        assert n == 1, desen
    return t


PROMPT_EVREN = _evren_prompt()


# Uydurma istatistik/oran: '1 in 3', 'half of', 'thousands of', 'percent', '3 times', 'twice as'. claim_lint RAKAM yalniz $, %, k/million/billion yakalar;
# duz rakam/kelimeyle yazilmis oranlar ('1 in 3 wrong') kaciyordu (15 Ekim 2026: doktor konusunda 'Human doctors get 1 in 3 wrong.').
_SAYI = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
ISTATISTIK = re.compile(
    rf"\b{_SAYI}\s+(?:in|out of)\s+{_SAYI}\b|\b(?:half|most|majority|minority|nearly all|almost all)\s+of\b|"
    r"\b(?:hundreds|thousands|millions|billions)\s+of\b|\bpercent\b|\b\d+\s*(?:x|times)\b|\b(?:twice|double|triple)\s+as\b", re.I)

# Tibbi konularda (doktor, hap, teshis...) dogruluk/guvenlik/zarar iddiasi YASAK: yanlis tibbi bilgi riski. Yalniz metinde tibbi kelime varsa calisir.
MEDIKAL = re.compile(r"\b(doctors?|nurses?|medicine|medical|pills?|prescri\w+|surgery|surgeons?|diagnos\w+|symptoms?|patients?|disease|illness|cancer|hospitals?|clinic|treatment)\b", re.I)
TIBBI_IDDIA = re.compile(r"\b(wrong|mistakes?|errors?|misdiagnos\w+|guess\w*|accura\w+|inaccura\w+|safer|safe|dangerous|harm\w*|kill\w*|die[sd]?|deadly|misses|missed)\b", re.I)

# Beden/cip/beyin konularinda 'tedavi eder / iyilestirir' gibi ETKI iddiasi: yalniz GELECEK/VARSAYIM kipinde (could, might, one day, what if...) serbest;
# bugun gecerliymis gibi (olgu kipi) yasak. Gelecek hakkinda dusunce/hayal ozgurdur; yasak olan, kanitsiz etkiyi olgu gibi sunmaktir (platform tibbi yanlis
# bilgi politikasi + yanlis umut riski). Yalniz metinde beden/tip kelimesi varsa calisir.
BEDEN = re.compile(r"\b(chips?|brains?|implants?|organs?|cyborgs?|bod(?:y|ies)|genes?|nanobots?|neurons?)\b", re.I)
ETKI_KELIME = re.compile(r"\b(cures?|cured|heals?|healed|treats?|treated|fix(?:es|ed)?|reverses?|prevents?|eliminates?)\b", re.I)
VARSAYIM = re.compile(r"\b(could|might|may|maybe|perhaps|one day|someday|imagine|what if|would|if|someday|someday)\b", re.I)

_ENTITY_RX = None


def _entities():
    global _ENTITY_RX
    if _ENTITY_RX is None:
        try:
            import sensitivity_gate
            ents = list(sensitivity_gate._ENTITIES)
        except Exception:
            ents = []
        ents += ["amazon", "netflix", "spotify", "uber", "walmart", "youtube", "facebook", "instagram", "paypal", "ebay",
                 "starbucks", "mcdonald", "disney", "samsung"]
        _ENTITY_RX = re.compile(r"\b(" + "|".join(re.escape(e) for e in sorted(set(ents), key=len, reverse=True)) + r")\b", re.I)
    return _ENTITY_RX


_SORU_BASI = ("is", "are", "why", "how", "do", "does", "can", "will", "should", "what", "who", "when", "did", "would")


def baslik_duzelt(title):
    """Yalniz bicim: bas harf buyuk, soru kelimesiyle basliyorsa '?' ekle. Icerige dokunmaz."""
    t = (title or "").strip()
    if not t:
        return t
    t = t[0].upper() + t[1:]
    if t.split()[0].lower() in _SORU_BASI and not t.endswith("?"):
        t += "?"
    return t


def _kelimeler(s):
    return re.findall(r"[A-Za-z0-9'%$.-]+", s or "")


# --------------------------------------------------------------------------- skor tablosu
def skor_oku(yol=None):
    try:
        with open(yol or SKOR_YOL, encoding="utf-8") as f:
            d = json.load(f)
        return {"alpha": int(d.get("alpha", 0)), "beta": int(d.get("beta", 0))}
    except Exception:
        return {"alpha": 0, "beta": 0}


def oy_ekle(taraf, n=1, yol=None):
    """Sahibin gercek yorumlardan saydigi oyu ekler. Yalniz 'alpha' / 'beta'; n >= 0."""
    if taraf not in ("alpha", "beta") or int(n) < 0:
        raise ValueError("taraf alpha|beta, n >= 0 olmali")
    yol = yol or SKOR_YOL
    s = skor_oku(yol)
    s[taraf] += int(n)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(s, f)
    return s


def skor_cumlesi(yol=None):
    """Hic oy yoksa bos (uydurma skor yok); varsa 'Score: Alpha 7, Beta 6.'"""
    s = skor_oku(yol)
    if s["alpha"] + s["beta"] == 0:
        return ""
    return f"Score: Alpha {s['alpha']}, Beta {s['beta']}."


def kapanisa_skor_ekle(beats, yol=None):
    sk = skor_cumlesi(yol)
    if not sk or not beats:
        return beats
    who, screen, line, img = beats[-1][0], beats[-1][1], beats[-1][2], (beats[-1][3] if len(beats[-1]) > 3 else "")
    if line.startswith("Score:"):
        return beats
    return beats[:-1] + [(who, screen, f"{sk} {line}", img)]


# --------------------------------------------------------------------------- kapi
def _norm(x):
    return re.sub(r"[^a-z0-9 ]", "", (x or "").lower()).strip()


def kontrol(beats, title, hookthumb, gecmis_ilk=(), kanca=None, konu=None):
    """-> [(kod, mesaj)]. Bos liste = gecti. Hicbir guvenlik kuralini gevsetmez; hook_gate + claim_lint + isim yasagi dahil."""
    s = []
    if len(beats) != 6:
        return [("SATIR_SAYISI", f"6 satir olmali, {len(beats)} geldi.")]
    sira = [b[0] for b in beats]
    if sira != SIRA:
        s.append(("SIRA", f"Konusmaci sirasi {SIRA} olmali, {sira} geldi."))
    L = [b[2] for b in beats]
    toplam = sum(len(_kelimeler(x)) for x in L)
    if toplam > TOPLAM_KELIME_MAX:
        s.append(("UZUN", f"Toplam {toplam} kelime (en fazla {TOPLAM_KELIME_MAX}); ~25 sn hedefi."))
    for i, x in enumerate(L, 1):
        if i == 6:
            n, limit = len(_kelimeler(re.sub(r"^Score:[^.]*\.\s*", "", x))), KAPANIS_KELIME_MAX
        else:
            n, limit = len(_kelimeler(x)), SATIR_KELIME_MAX
        if i != 1 and n > limit:
            s.append(("SATIR_UZUN", f"{i}. satir {n} kelime (en fazla {limit})."))
    # kanca + baslik + kapanis: hook_gate (ayni kapi)
    for kod, msg in hook_gate.kontrol(title, L[0], L[-1], hookthumb):
        s.append((kod, msg))
    s += hook_gate.tekrar_kontrol(list(gecmis_ilk), L[0])
    if len((title or "").strip()) > BASLIK_MAX:
        s.append(("BASLIK_40", f"Baslik {len(title.strip())} karakter (en fazla {BASLIK_MAX})."))
    # karakter isaretleri (tell)
    if not re.search(r"that'?s one for me", L[1], re.I):
        s.append(("ALPHA_ISARET", "Alpha 'That's one for me.' demedi."))
    if not re.match(r"\s*hold on\b", L[2], re.I):
        s.append(("BETA_ISARET", "Beta 'Hold on.' ile baslamadi."))
    if not (re.search(r"\bactually\b", L[3], re.I) and re.search(r"\byou'?re correct\b|\byou are correct\b", L[3], re.I)):
        s.append(("DELTA_ISARET", "Delta taraf degistirmedi ('Actually... X, you're correct.')."))
    evren = evren_mi(konu)
    if evren:
        if not re.search(r"\bi(?:'d|\u2019d| would)\b", L[4], re.I):
            s.append(("GAMMA_ISARET", "Gamma kisisel secimini ('I'd ...' / 'I would ...') soylemedi."))
    elif not re.search(r"\bi do this too\b", L[4], re.I):
        s.append(("GAMMA_ISARET", "Gamma 'I do this too, honestly.' itirafini yapmadi."))
    if not re.search(r"team alpha or team beta", L[5], re.I):
        s.append(("KAPANIS_TAKIM", "Kapanista 'Team Alpha or Team Beta?' yok."))
    if evren:
        if not re.search(r"\b(which|where|what would you)\b", L[5], re.I):
            s.append(("KAPANIS_SECIM", "Kapanis izleyiciden kisisel secim istemiyor (Which/Where/What would you ...?)."))
    elif not re.search(r"\b(guilty|habit)\b", L[5], re.I):
        s.append(("KAPANIS_ITIRAF", "Kapanis izleyiciden 'guilty habit' istemiyor."))
    if evren:
        yasak_zaman = sorted({m.group(0).lower() for m in ZAMAN_SIMDI.finditer(" ".join(L) + " " + (title or "") + " " + (hookthumb or ""))
                              if m.group(0).lower() not in (konu or "").lower()})
        if yasak_zaman:
            s.append(("SIMDI_ZAMANI", f"Bu bir varsayim; 'simdi oluyor' gibi okunan kelime yasak: {', '.join(yasak_zaman)}."))
        if rakam_bankasi.olgu_rakami_var(tum_metin := " ".join(L) + " " + (title or ""), konu):
            kucuk = sorted({m.group(0).lower() for m in KUCUK_OLCEK.finditer(tum_metin)})
            if kucuk:
                s.append(("KUCUK_OLCEK", f"Buyuk olcekli rakamla kucuk nesneler uyusmuyor: {', '.join(kucuk)}. Kiyilar, limanlar, sokaklar, mahalleler gibi buyuk seyleri soyle."))
    stat = sorted({m.group(0).lower() for m in ISTATISTIK.finditer(" ".join(L) + " " + (title or ""))})
    if stat:
        s.append(("ISTATISTIK", f"Oran/istatistik/dogruluk iddiasi yasak (uydurma olabilir): {', '.join(stat)}."))
    tum = " ".join(L) + " " + (title or "")
    # rakam bankasi: bankada/konu sorusunda olmayan buyuk rakam, birimli rakam, yil, yazili 'sixty/hundred' -> red
    kaynaksiz = rakam_bankasi.yasakli_rakamlar(tum + " " + (hookthumb or ""), konu)
    if kaynaksiz:
        s.append(("RAKAM_KAYNAK", f"Kaynaksiz rakam: {', '.join(kaynaksiz)}. Yalniz VERIFIED FACTS'teki rakamlar kullanilabilir (rakam_bankasi.py)."))
    eksik = rakam_bankasi.onkosul_eksik(tum, konu)
    if eksik:
        s.append(("ONKOSUL_EKSIK", f"Rakam kullanildi ama bagli oldugu kosul soylenmedi ({', '.join(eksik)}): ornegin 'a quarter of the ice', 'all the ice', 'since 1880'."))
    if BEDEN.search(tum) or MEDIKAL.search(tum):
        for cumle in re.split(r"(?<=[.?!])\s+", tum):
            if ETKI_KELIME.search(cumle) and not VARSAYIM.search(cumle):
                s.append(("ETKI_IDDIA", f"Beden/cip konusunda etki iddiasi yalniz gelecek-varsayim kipinde olabilir (could/might/one day/what if): '{cumle.strip()[:80]}'."))
                break
    if MEDIKAL.search(tum):
        tibbi = sorted({m.group(0).lower() for m in TIBBI_IDDIA.finditer(tum)})
        if tibbi:
            s.append(("TIBBI_IDDIA", f"Tibbi konuda dogruluk/guvenlik/zarar iddiasi yasak: {', '.join(tibbi)}. Soru sor ya da kisisel tercih soyle."))
    soyut = sorted({m.group(0).lower() for m in SOYUT.finditer(" ".join(L))})
    if soyut:
        s.append(("SOYUT", f"Soyut kelime kullanma, somut bir nesne/an soyle: {', '.join(soyut)}."))
    if kanca and _norm(L[0]) != _norm(kanca):
        s.append(("KANCA_DEGISTI", f"1. satir secilen kancayla BIREBIR ayni olmali: '{kanca}'."))
    # guvenlik
    metin = " ".join(L + [title or "", hookthumb or ""])
    isim = sorted({m.group(0).lower() for m in _entities().finditer(metin)})
    if isim:
        s.append(("GERCEK_ISIM", f"Gercek sirket/urun adi yasak: {', '.join(isim)}."))
    for ad, hits, why in claim_lint.lint(metin):
        if ad in ENGELLEYICI:
            s.append(("LINT_" + ad.replace(" ", "_").replace("/", "_"), f"{ad}: {', '.join(hits)} - {why}"))
    return s


def uyarilar(beats, title="", hookthumb=""):
    """Engellemeyen claim_lint uyarilari (MUTLAK IFADE vb.) - yalniz bilgi."""
    metin = " ".join([b[2] for b in beats] + [title or "", hookthumb or ""])
    return [(ad, hits) for ad, hits, _ in claim_lint.lint(metin) if ad not in ENGELLEYICI]


# --------------------------------------------------------------------------- kanca paketleme
KANCA_PROMPT = (
    "You are the head writer of Sign Council, a Shorts channel where five AI characters argue about everyday life.\n"
    "TOPIC: {topic}\n\n"
    "Write 5 DIFFERENT opening hooks for this topic (what the host says in the first two seconds). Each: 4-7 words, plain "
    "spoken English, a bold contradiction OR a small concrete number OR a sharp question about ONE concrete everyday thing. "
    "Each MUST contain a digit, a question mark, or one of these words: but, not, never, why, how, wrong, missing, only, "
    "just, nobody, everyone, still, versus, worst, best, first, last, stop, before, after, instead. No real brand or "
    "person names, no money amounts, percentages, ratios ('1 in 3') or accuracy claims about any group, no accusations (no hidden, lie, trap, scam, secret, force, rigged). "
    "A stranger scrolling past must want to hear the next sentence.\n"
    "Output EXACTLY:\n1: ...\n2: ...\n3: ...\n4: ...\n5: ...\nPICK: <number of the strongest>\n"
)


def kanca_gecerli(h, konu=None):
    """Tek bir kanca adayi kapidan (ilk cumle kurallari + guvenlik) gecer mi? -> [(kod,mesaj)]"""
    s = []
    n = len(_kelimeler(h))
    if not (4 <= n <= 7):
        s.append(("ADAY_UZUNLUK", f"{n} kelime (4-7 olmali)."))
    if hook_gate.YASAK_ACILIS.search(h or "") or not hook_gate.TETIK.search(h or ""):
        s.append(("ADAY_TETIK", "tetik kelimesi yok ya da yasak acilis."))
    if _entities().search(h or ""):
        s.append(("ADAY_ISIM", "gercek isim."))
    for ad, hits, _ in claim_lint.lint(h or ""):
        if ad in ENGELLEYICI:
            s.append(("ADAY_" + ad, ", ".join(hits)))
    if SOYUT.search(h or ""):
        s.append(("ADAY_SOYUT", "soyut kelime."))
    if ISTATISTIK.search(h or ""):
        s.append(("ADAY_ISTATISTIK", "oran/istatistik iddiasi."))
    kaynaksiz = rakam_bankasi.yasakli_rakamlar(h or "", konu)
    if kaynaksiz:
        s.append(("ADAY_RAKAM", "kaynaksiz rakam/sayim: " + ", ".join(kaynaksiz)))
    if rakam_bankasi.onkosul_eksik(h or "", konu):
        s.append(("ADAY_ONKOSUL", "rakamin kosulu (varsayim) kancada yok."))
    if MEDIKAL.search(h or "") and TIBBI_IDDIA.search(h or ""):
        s.append(("ADAY_TIBBI", "tibbi konuda dogruluk/guvenlik iddiasi."))
    return s


def kanca_sec(topic, llm):
    """5 aday yazdirir, kapidan gecenler arasindan modelin PICK'ini (yoksa ilk gecerliyi) secer.
    -> {"adaylar": [(metin, gecerli_mi)], "secilen": str|None}. Aday yoksa/LLM hata verirse secilen=None (senaryo yine yazilir)."""
    try:
        raw = llm(KANCA_PROMPT.format(topic=topic) + rakam_bankasi.prompt_bolumu(topic))
    except Exception:
        return {"adaylar": [], "secilen": None}
    adaylar = {int(m.group(1)): m.group(2).strip().strip('"') for m in re.finditer(r"^\s*([1-5])\s*[:.)]\s*(.+)$", raw, re.M)}
    liste = [(adaylar[k], not kanca_gecerli(adaylar[k], topic)) for k in sorted(adaylar)]
    pick = re.search(r"PICK:\s*([1-5])", raw)
    secilen = None
    if pick and int(pick.group(1)) in adaylar and not kanca_gecerli(adaylar[int(pick.group(1))], topic):
        secilen = adaylar[int(pick.group(1))]
    if secilen is None:
        secilen = next((h for h, ok in liste if ok), None)
    return {"adaylar": liste, "secilen": secilen}


def kanca_secimi(kk, cevap):
    """Sahibin cevabi: '' -> modelin secimi; '0' -> kanca dayatma (None); '1'-'5' -> o aday (yalniz kapidan gecmisse).
    -> (secilen|None, mesaj)"""
    c = (cevap or "").strip()
    if c == "":
        return kk["secilen"], "modelin secimi"
    if c == "0":
        return None, "kanca dayatilmadi"
    if c.isdigit() and 1 <= int(c) <= len(kk["adaylar"]):
        h, ok = kk["adaylar"][int(c) - 1]
        if ok:
            return h, f"senin secimin: {c}"
        return kk["secilen"], f"{c}. aday kapidan gecmemis, modelin secimi kullanildi"
    return kk["secilen"], "gecersiz cevap, modelin secimi kullanildi"


# --------------------------------------------------------------------------- kayit (onayla -> sonra uret)
def senaryo_kaydet(yol, topic, r):
    """Kapidan gecmis senaryoyu diske yazar; video uretimi bu dosyadan yapilabilir (model yeniden yazmaz)."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump({"topic": topic, "title": r["title"], "hookthumb": r["hookthumb"],
                   "beats": [list(b) for b in r["beats"]]}, f, ensure_ascii=False, indent=2)


def senaryo_yukle(yol):
    """-> (topic, beats(list of tuple), title, hookthumb). Dosya sahibi elle duzeltmis olabilir: cagiran kapiyi YENIDEN calistirmali."""
    with open(yol, encoding="utf-8") as f:
        d = json.load(f)
    return d["topic"], [tuple(b) for b in d["beats"]], d["title"], d["hookthumb"]


_ETIKET_DURAK = set("this that with from have your what when where which would could should about really worth many much more most too".split())


def etiketler(title):
    """Konsey Short'u icin YouTube etiketleri: sabit marka etiketleri + basliktan en fazla 3 anahtar kelime. AI-haber etiketi YOK."""
    kelimeler = []
    for w in re.findall(r"[a-z]{5,}", (title or "").lower()):
        if w not in _ETIKET_DURAK and w not in kelimeler:
            kelimeler.append(w)
    return ["Sign Council", "AI debate", "everyday life", "shorts"] + kelimeler[:3]


def duzenle(r, komut, kanca=None):
    """Senaryo sonucu r'yi (dict: beats, title, hookthumb) bellekte duzenler. komut: ('s', n, metin) | ('b', metin) | ('k', metin).
    Kapidan gecmezse r DEGISMEZ. -> (yeni_r | None, sorunlar)"""
    beats, title, kart = list(r["beats"]), r["title"], r["hookthumb"]
    if komut[0] == "s":
        n, metin = int(komut[1]), komut[2].strip()
        if not 1 <= n <= len(beats):
            return None, [("SATIR_NO", f"1-{len(beats)} arasi olmali.")]
        who, screen, _eski, img = beats[n - 1]
        beats[n - 1] = (who, screen, metin, img)
    elif komut[0] == "b":
        title = baslik_duzelt(komut[1])
    elif komut[0] == "k":
        kart = " ".join(komut[1].split()).upper()
    else:
        return None, [("KOMUT", "Bilinmeyen duzenleme.")]
    sorunlar = kontrol(beats, title, kart, kanca=kanca, konu=r.get("topic"))
    if sorunlar:
        return None, sorunlar
    return {**r, "beats": beats, "title": title, "hookthumb": kart, "uyarilar": uyarilar(beats, title, kart)}, []


def duzenleme_coz(cevap):
    """'s 2 yeni cumle' | 'b Yeni Baslik' | 'k YENI KART' -> komut tuple'i; degilse None."""
    import re as _re
    m = _re.match(r"^\s*s\s+([1-6])\s+(.+\S)\s*$", cevap or "", _re.I | _re.S)
    if m:
        return ("s", int(m.group(1)), m.group(2))
    m = _re.match(r"^\s*([bk])\s+(.+\S)\s*$", cevap or "", _re.I | _re.S)
    if m:
        return (m.group(1).lower(), m.group(2))
    return None


def satir_degistir(yol, n, metin):
    """Kayitli senaryonun n. satirinin (1-6) metnini degistirir. Yeni senaryo kapidan GECMEZSE dosya DEGISMEZ.
    -> (kaydedildi: bool, sorunlar)"""
    topic, beats, title, hookthumb = senaryo_yukle(yol)
    if not 1 <= int(n) <= len(beats):
        return False, [("SATIR_NO", f"1-{len(beats)} arasi olmali.")]
    who, screen, _eski, img = beats[int(n) - 1]
    yeni = beats[:int(n) - 1] + [(who, screen, metin.strip(), img)] + beats[int(n):]
    sorunlar = kontrol(yeni, title, hookthumb, konu=topic)
    if sorunlar:
        return False, sorunlar
    senaryo_kaydet(yol, topic, {"title": title, "hookthumb": hookthumb, "beats": yeni})
    return True, []


def baslik_degistir(yol, metin):
    """Kayitli senaryonun BASLIGINI degistirir (bicim duzeltilir). Kapidan gecmezse dosya DEGISMEZ. -> (kaydedildi, sorunlar)"""
    topic, beats, title, hookthumb = senaryo_yukle(yol)
    yeni = baslik_duzelt(metin)
    sorunlar = kontrol(beats, yeni, hookthumb, konu=topic)
    if sorunlar:
        return False, sorunlar
    senaryo_kaydet(yol, topic, {"title": yeni, "hookthumb": hookthumb, "beats": beats})
    return True, []


def ekran_degistir(yol, metin):
    """Kayitli senaryonun ilk kart metnini (HOOKTHUMB) degistirir (BUYUK HARF). Kapidan gecmezse dosya DEGISMEZ. -> (kaydedildi, sorunlar)"""
    topic, beats, title, hookthumb = senaryo_yukle(yol)
    yeni = " ".join((metin or "").split()).upper()
    sorunlar = kontrol(beats, title, yeni, konu=topic)
    if sorunlar:
        return False, sorunlar
    senaryo_kaydet(yol, topic, {"title": title, "hookthumb": yeni, "beats": beats})
    return True, []


# --------------------------------------------------------------------------- uretim
def uret(topic, llm, parse, skor_yolu=None, gecmis_ilk=(), deneme=3, kanca=None):
    """llm(prompt:str)->str; parse(raw)->(beats,title,hookthumb) (make_topic_short._parse_script).
    Kapidan gecmezse sorunlari geri besleyip yeniden yazdirir (en fazla 3 deneme). -> dict(ok, beats, title, hookthumb, sorunlar, ham, deneme)"""
    temel = (PROMPT_EVREN if evren_mi(topic) else PROMPT).format(topic=topic) + rakam_bankasi.prompt_bolumu(topic)
    if kanca:
        temel += f"\n\nPACKAGED HOOK (already chosen): line 1 must be EXACTLY this, word for word: {kanca}"
    prompt = temel
    ham, sorunlar, beats, title, hookthumb = "", [], [], "", ""
    for n in range(1, deneme + 1):
        ham = llm(prompt)
        beats, title, hookthumb = parse(ham)
        title = baslik_duzelt(title)
        beats = kapanisa_skor_ekle(beats, skor_yolu)
        sorunlar = kontrol(beats, title, hookthumb, gecmis_ilk, kanca, konu=topic)
        if not sorunlar:
            return {"ok": True, "topic": topic, "beats": beats, "title": title, "hookthumb": hookthumb, "sorunlar": [], "ham": ham, "deneme": n,
                    "uyarilar": uyarilar(beats, title, hookthumb)}
        prompt = temel + (
            "\n\nYour previous attempt was REJECTED for these reasons - fix every one and keep all rules:\n"
            + "\n".join(f"- {m}" for _, m in sorunlar))
    return {"ok": False, "topic": topic, "beats": beats, "title": title, "hookthumb": hookthumb, "sorunlar": sorunlar, "ham": ham, "deneme": deneme,
            "uyarilar": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Konsey formati skor tablosu")
    ap.add_argument("--oy", nargs=2, metavar=("TARAF", "N"), help="gercek yorumlardan sayilan oy ekle: alpha|beta N")
    ap.add_argument("--skor", action="store_true", help="skoru goster")
    ap.add_argument("--satir", nargs=2, metavar=("N", "METIN"), help="kayitli senaryonun N. satirini degistir (kapidan gecerse)")
    ap.add_argument("--baslik", metavar="METIN", help="kayitli senaryonun basligini degistir (kapidan gecerse)")
    ap.add_argument("--ekran", metavar="METIN", help="kayitli senaryonun ilk kart metnini (3-5 kelime) degistir (kapidan gecerse)")
    ap.add_argument("--dosya", default=KAYIT_YOL, help="--satir/--baslik/--ekran icin senaryo dosyasi")
    a = ap.parse_args(argv)
    if a.ekran:
        ok, sorunlar = ekran_degistir(a.dosya, a.ekran)
        if ok:
            print(f"Ilk kart degisti, kapidan gecti, kaydedildi: {' '.join(a.ekran.split()).upper()}")
            return 0
        print("KAPIDAN GECMEDI - dosya DEGISMEDI:")
        for kod, msg in sorunlar:
            print(f"  - {kod}: {msg}")
        return 2
    if a.baslik:
        ok, sorunlar = baslik_degistir(a.dosya, a.baslik)
        if ok:
            print(f"Baslik degisti, kapidan gecti, kaydedildi: {baslik_duzelt(a.baslik)}")
            return 0
        print("KAPIDAN GECMEDI - dosya DEGISMEDI:")
        for kod, msg in sorunlar:
            print(f"  - {kod}: {msg}")
        return 2
    if a.satir:
        ok, sorunlar = satir_degistir(a.dosya, int(a.satir[0]), a.satir[1])
        if ok:
            print(f"{a.satir[0]}. satir degisti, kapidan gecti, kaydedildi.")
            return 0
        print("KAPIDAN GECMEDI - dosya DEGISMEDI:")
        for kod, msg in sorunlar:
            print(f"  - {kod}: {msg}")
        return 2
    if a.oy:
        s = oy_ekle(a.oy[0].lower(), int(a.oy[1]))
        print(f"Skor: Alpha {s['alpha']}, Beta {s['beta']}")
    else:
        s = skor_oku()
        print(f"Skor: Alpha {s['alpha']}, Beta {s['beta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
