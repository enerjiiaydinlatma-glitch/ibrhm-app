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

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
SKOR_YOL = os.path.join(ENGINE, "konsey_skor.json")

SIRA = ["aura", "alpha", "beta", "delta", "gamma", "aura"]
BASLIK_MAX = 40
TOPLAM_KELIME_MAX = 90
SATIR_KELIME_MAX = 24
ENGELLEYICI = set(claim_lint.BLOCKING) | {"RAKAM"}

PROMPT = (
    "Write a vertical YouTube Short script (about 25 seconds spoken) for Sign Council: five AI characters argue about an "
    "EVERYDAY consumer/life topic, and the viewer takes a side in the comments.\n\n"
    "Topic: {topic}\n\n"
    "Output EXACTLY 6 lines, in this exact speaker order: aura, alpha, beta, delta, gamma, aura. Format per line:\n"
    "SPEAKER | SCREEN | LINE | IMAGE\n"
    "- SCREEN: 2-4 word ALL-CAPS on-screen phrase.\n"
    "- LINE: plain spoken English, no markdown, max 20 words (the last line max 24).\n"
    "- IMAGE: one-sentence cinematic photo prompt of a concrete everyday object or scene for this line; no text, logos, "
    "robots or AI cliches.\n\n"
    "CHARACTERS (each has a flaw that must show every time):\n"
    "1 AURA opens with the HOOK: a line of 8 words or FEWER that holds a question, a number, or a contradiction. Never "
    "start with 'The claim', 'Today', 'Hello', 'Did you know'. Aura secretly favors Alpha.\n"
    "2 ALPHA explains the mechanism coldly, then ends with the exact words 'That's one for me.' (he keeps score, "
    "prematurely).\n"
    "3 BETA starts with 'Hold on.' and pushes back with a sharp question. Beta never offers a solution.\n"
    "4 DELTA, people-pleaser, switches sides: 'Actually... <Alpha or Beta>, you're correct.' plus one short reason.\n"
    "5 GAMMA gives one short moral point, then confesses with the exact words 'I do this too, honestly.' followed by "
    "the guilty habit in a few words.\n"
    "6 AURA closes: exactly one sentence 'Team Alpha or Team Beta?' then asks the viewer for THEIR guilty habit "
    "(use the word 'guilty' or 'habit'). Do not write any score; the system adds it.\n\n"
    "HARD RULES (a script that breaks one is thrown away):\n"
    "- Do NOT name any real company, brand, product, app or person. Use generic words (online stores, streaming "
    "services, a phone plan).\n"
    "- NO statistics, percentages, dollar/money amounts or 'million/billion/k' figures. Small counts of things are "
    "fine ('three fees').\n"
    "- NEVER attribute intent or wrongdoing: do not use the words hidden, hide, trap, lie, scam, fraud, secret, "
    "deliberate, intentional, rigged, manipulate, force, illegal, crime, cheat. Explain the STRUCTURE and incentives "
    "in neutral words.\n"
    "- The linter matches word FRAGMENTS, so also avoid words like right, bright, origin, trigger, believe, belief, "
    "enforce, strap, quiet - use simple synonyms (say 'correct', not 'right').\n"
    "- Do not use comparisons with the word 'than'. Avoid 'always', 'never', 'everyone', 'nobody' as claims.\n"
    "- Every claim must be common knowledge about how everyday things work; no news, no accusations.\n"
    "After the 6 lines add:\n"
    "TITLE: <max 40 characters, no colon, no quotes, a question or contradiction about the topic>\n"
    "HOOKTHUMB: <3-5 ALL CAPS words for the opening card, not generic>"
)

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
def kontrol(beats, title, hookthumb, gecmis_ilk=()):
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
        if len(_kelimeler(x)) > SATIR_KELIME_MAX and i != 1:
            s.append(("SATIR_UZUN", f"{i}. satir {len(_kelimeler(x))} kelime (en fazla {SATIR_KELIME_MAX})."))
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
    if not re.search(r"\bi do this too\b", L[4], re.I):
        s.append(("GAMMA_ISARET", "Gamma 'I do this too, honestly.' itirafini yapmadi."))
    if not re.search(r"team alpha or team beta", L[5], re.I):
        s.append(("KAPANIS_TAKIM", "Kapanista 'Team Alpha or Team Beta?' yok."))
    if not re.search(r"\b(guilty|habit)\b", L[5], re.I):
        s.append(("KAPANIS_ITIRAF", "Kapanis izleyiciden 'guilty habit' istemiyor."))
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


# --------------------------------------------------------------------------- uretim
def uret(topic, llm, parse, skor_yolu=None, gecmis_ilk=(), deneme=2):
    """llm(prompt:str)->str; parse(raw)->(beats,title,hookthumb) (make_topic_short._parse_script).
    Kapidan gecmezse sorunlari geri besleyip bir kez daha yazdirir. -> dict(ok, beats, title, hookthumb, sorunlar, ham, deneme)"""
    prompt = PROMPT.format(topic=topic)
    ham, sorunlar, beats, title, hookthumb = "", [], [], "", ""
    for n in range(1, deneme + 1):
        ham = llm(prompt)
        beats, title, hookthumb = parse(ham)
        beats = kapanisa_skor_ekle(beats, skor_yolu)
        sorunlar = kontrol(beats, title, hookthumb, gecmis_ilk)
        if not sorunlar:
            return {"ok": True, "beats": beats, "title": title, "hookthumb": hookthumb, "sorunlar": [], "ham": ham, "deneme": n,
                    "uyarilar": uyarilar(beats, title, hookthumb)}
        prompt = PROMPT.format(topic=topic) + (
            "\n\nYour previous attempt was REJECTED for these reasons - fix every one and keep all rules:\n"
            + "\n".join(f"- {m}" for _, m in sorunlar))
    return {"ok": False, "beats": beats, "title": title, "hookthumb": hookthumb, "sorunlar": sorunlar, "ham": ham, "deneme": deneme,
            "uyarilar": []}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Konsey formati skor tablosu")
    ap.add_argument("--oy", nargs=2, metavar=("TARAF", "N"), help="gercek yorumlardan sayilan oy ekle: alpha|beta N")
    ap.add_argument("--skor", action="store_true", help="skoru goster")
    a = ap.parse_args(argv)
    if a.oy:
        s = oy_ekle(a.oy[0].lower(), int(a.oy[1]))
        print(f"Skor: Alpha {s['alpha']}, Beta {s['beta']}")
    else:
        s = skor_oku()
        print(f"Skor: Alpha {s['alpha']}, Beta {s['beta']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
