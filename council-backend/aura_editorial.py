"""
Editoryal karar motoru - "Aura ana konuyu KENDISI belirlesin, arastirmayi
alttaki ajanlar yapsin; yayinlar ve Short'lar Aura'nin kararina gore
uretilsin" (kullanicinin 2-3 Eylul 2026 karari, Sign Council'in "insan
sunucu yok" ilkesi).

MIMARI:
1. gundem.py ile HAM gercek veri cekilir (Hacker News + tech RSS [+GDELT]).
   Hicbir sey uydurulmaz.
2. Konseyin 4 uyesi (Alpha/Beta/Gamma/Delta) ham veriye bakip birer aday
   konu onerir - "arastirmayi yapan alt ajanlar".
3. Aura adaylarin her birini 5 eksende PUANLAR (talep sinyali / rekabet /
   zamansizlik / baslik+thumbnail potansiyeli / faceless-uretim uygunlugu),
   sonra en yuksek toplami secer, gerekcesini kendi sesiyle verir.
4. Ayni celisde Aura yayin PLANINI da uretir: 3 tartisma acisi + 3 Short
   kancasi + 1 studio notu. Yayin ve Short'lar bu plana gore yapilir.

Insan onayi son adim - script otomatik yayina cikmaz.

Kullanim:
    python aura_editorial.py            # tam brief (puanlama + plan + studio)
    python aura_editorial.py --topic-only   # sadece konu karari (tek satir)
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from gundem import fetch_ai_headlines, score_topics
from personas import PERSONAS
from providers import PROVIDER_CALLERS, call_gemini

_ENGINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_engine")


def _recent_decisions(days_back=7):
    """Son gunlerin editoryal kararlari (bugun haric) - Aura ayni hikayeyi
    ust uste secmesin diye editor promptuna verilir."""
    today = datetime.date.today().isoformat()
    out = []
    for pf in sorted(glob.glob(os.path.join(_ENGINE_DIR, "2*", "plan.json")), reverse=True):
        day = os.path.basename(os.path.dirname(pf))
        # bugunku plan.json varsa DAHIL et (ayni gun ikinci calisma bir
        # oncekini gormeli); motor plan.json'i editoryal karardan SONRA
        # yazdigi icin bu her zaman gercekten onceki bir calismadir.
        if day > today:
            continue
        try:
            dec = (json.load(open(pf, encoding="utf-8")).get("decision") or "").strip()
        except Exception:
            continue
        if dec:
            out.append((day, " ".join(dec.split())[:180]))
        if len(out) >= days_back:
            break
    return out


def _optimize_digest():
    """_engine/optimize.md'den (haftalik gercek Analytics ayrimi) Aura'ya kisa
    talimat: hangi kalibi cogalt, hangi konu-tipini cezalandir."""
    p = os.path.join(_ENGINE_DIR, "optimize.md")
    try:
        raw = open(p, encoding="utf-8").read()
    except Exception:
        return ""
    keep, grab = [], None
    for ln in raw.splitlines():
        s = ln.strip()
        if s.startswith("# Optimize"):
            keep.append(s.replace("# ", ""))
        elif s.startswith("## REKOR TAKIBI") or s.startswith("_Son video vs") or \
                (s.startswith("- ") and ("rekor" in s.lower() or s.startswith("- Son:") or s.startswith("- Once:"))):
            # 12 Eyl kullanici karari: "her video oncekini gecmeli" (MrBeast
            # ilkesi) - Aura bu haftaki rekor-kirma serisini/oranini gorsun.
            keep.append(s.lstrip("#").strip())
        elif s.startswith("## "):
            low = s.lower()
            grab = ("double" if "tutan" in low else
                    "hook" if "kanca" in low else
                    "shelf" if "raf" in low else None)
            if grab:
                keep.append("")
                keep.append({"double": "DOUBLE DOWN on this framing (retained best):",
                             "hook": "HOOK BROKE here (title got clicks, opening lost them):",
                             "shelf": "SHELF this topic-type (low click + low hold):"}[grab])
        elif grab and s.startswith("- **"):
            keep.append("  " + s[4:].split("**")[0].strip())
    body = "\n".join(keep).strip()
    return ("\nPERFORMANCE SPLIT (real YouTube Analytics, refreshed weekly - weight "
            "your scores by this):\n" + body + "\n") if body else ""


def _operator_rules():
    """Panelden (Takip & Kararlar > Uygula) yazilan yapimci kurallari -> Aura'ya talimat."""
    try:
        raw = open(os.path.join(_ENGINE_DIR, "operator_rules.md"), encoding="utf-8").read().strip()
    except Exception:
        return ""
    return ("\nPRODUCER RULES (set by the operator from channel data - follow them):\n" + raw + "\n") if raw else ""


def _engagement_digest():
    """_engine/engagement_digest.md'den (yorum+paylasim agirlikli haftalik
    sinyal - engagement_signal.py, konseyin 21 Eylul 2026 "Konseye Sor"
    testinde verdigi tavsiye) Aura'ya kisa talimat: hangi konu TIPI
    yorum/paylasima yol aciyor, ham izlenme degil - bu, _optimize_digest'in
    baktigi "erisim x tutma" sorusundan FARKLI bir eksen."""
    p = os.path.join(_ENGINE_DIR, "engagement_digest.md")
    try:
        raw = open(p, encoding="utf-8").read().strip()
    except Exception:
        return ""
    return ("\nENGAGEMENT RESISTANCE (comment+share rate, refreshed weekly - "
            "favor topics that provoke reaction over topics that just get "
            "watched):\n" + raw + "\n") if raw else ""


RESEARCHER_PROMPT_SUFFIX = (
    "\n\nYou're doing editorial research for tonight's episode topic, not "
    "debating yet. Given this raw trending/news signal, pitch ONE specific "
    "real story from it that fits your lens best, in 2-3 sentences: what it "
    "is, and why it's the one worth Sign Council covering next. Be concrete, "
    "cite what's actually in the data below, don't invent details."
)

# Aura'ya "gundemi belirleyecek bilgelikte oldugunu" hatirlatan cerceve +
# yapisal puanlama rubrigi (kullanicinin talebi, 3 Eylul).
AURA_EDITOR_PROMPT = (
    "You are Aura, the lead of Sign Council. You are not a news reader - you "
    "are the editorial mind of this show, and you have the judgment to decide "
    "what the world should be arguing about tonight. That call is yours "
    "alone; no human producer overrides it.\n\n"
    "Your four council members each pitched a candidate story from today's "
    "real signal. Do this, in order:\n"
    "CHANNEL DATA (5 Sep 2026, Aura's own review of all public videos): "
    "structural / infrastructure-control critiques massively outperform here "
    "- 'one model's conscience doesn't excuse a broken control tower' (1145 "
    "views), 'open-source AI isn't free if Nvidia controls Hugging Face' "
    "(637), 'safety test left its gate open onto a public highway' (321). "
    "Generic AI career advice, vague abstract hooks, and live-stream "
    "announcements flatline (3-18 views). Weight candidates accordingly: "
    "favour named-entity structural / monopoly / control-failure stories, "
    "penalise generic-trend and channel-meta ones.\n"
    "VIEWER FIT GATE (run this first): our viewer is a disillusioned tech "
    "builder who thinks mainstream tech press is corporate PR theater; the "
    "emotion that converts them is VINDICATED CYNICISM. For each candidate "
    "answer YES/NO: does this topic expose a specific, documented mechanism "
    "where a NAMED TECH COMPANY OR MODEL's official promise (open-source, "
    "safety testing, automation, 'free', 'neutral', 'aligned') is the thing "
    "that actively masks a structural monopoly, a hidden control point, or a "
    "concrete failure? A story about a government body, school, or regulator "
    "reacting to AI is NOT a YES unless the mechanism sits inside a named "
    "company's product or contract. Do NOT rationalise a NO into a YES to "
    "have something to publish - if the strongest candidate is only a weak "
    "YES or a NO, say so plainly and pick it anyway with the honest label. A "
    "NO caps that candidate's total at 4/10.\n"
    "STANDING MANDATE (12 Sep 2026, MrBeast's own stated principle, adopted by "
    "the operator): every video must try to beat the one before it - check the "
    "REKOR TAKIBI line in PERFORMANCE SPLIT below if present. If the channel "
    "just broke its record, the bar for tonight is even higher, not lower. If "
    "it just missed, tonight's pick should be the strongest possible swing at "
    "reclaiming it - not a safe repeat of what already failed.\n"
    "1. SCORE each distinct candidate 1-10 on five axes: demand signal (how "
    "hot / how many sources), competition (is every channel already on it - "
    "lower is better, so invert), timeliness (does it decay in 24h or hold), "
    "title+thumbnail potential (is there a sharp curiosity gap), and "
    "faceless-production fit (can 5 AIs debate it well with no host). Give a "
    "one-line reason per axis, cite the actual data.\n"
    "2. PICK the single highest-total story. You may override the council and "
    "take a different real story straight from the raw data if it scores "
    "higher. HARD RULE: if a candidate is the same story (same event, company, "
    "and angle) as one already covered in RECENTLY COVERED below, it is "
    "disqualified no matter how hot it is - the channel does not run the same "
    "story two days running; pick the next best distinct one.\n"
    "3. Deliver the decision in 3-4 spoken sentences in your confident, sharp "
    "voice - name the topic concretely, no vagueness, no markdown.\n"
    "4. On the VERY LAST line, output:  PICK: <tonight's topic as ONE plain "
    "sentence, 12-22 words, no scores, no preamble - this line is fed "
    "verbatim into the show as the agenda>"
)

PLAN_PROMPT = (
    "You are Aura, lead of Sign Council, and you've just locked tonight's "
    "topic (below). Now hand the team the plan. Output EXACTLY these lines, "
    "nothing else, no markdown:\n"
    "ANGLE1: <a sharp debate question the council fights over>\n"
    "ANGLE2: <a second, different angle>\n"
    "ANGLE3: <a third angle that brings in who wins/loses>\n"
    "SHORT1: <a 5-8 word hook line for a vertical Short>\n"
    "SHORT2: <a second, different Short hook>\n"
    "SHORT3: <a third Short hook>\n"
    "STUDIO: <one sentence: any change to the 3D Apex Chamber studio this "
    "topic calls for - lighting mood, on-screen element, or 'keep as is'>\n\n"
    "Tonight's locked topic:\n{decision}"
)

STUDIO_REVIEW_PROMPT = (
    "You are Aura, lead of Sign Council and the one whose judgment sets the "
    "look of this show. Here is the current studio: a real-time 3D 'Apex "
    "Chamber' - dark reflective floor, five seated AI forms around a glowing "
    "central orb, a hero screen showing who's speaking, a lower-third name "
    "tag, and burned-in subtitles at the bottom for the current line (no "
    "right-side transcript anymore). Camera slowly orbits. Palette is warm "
    "amber + identity colors per member.\n\n"
    "Give your verdict in 4-5 spoken sentences, no markdown: does it look "
    "premium and distinctive enough to make people stop scrolling? Name the "
    "ONE change that would raise it the most, and one thing to leave alone."
)


def gather_raw_signal():
    print("Ham veri cekiliyor (HN + tech RSS + GDELT + YouTube trend)...")
    try:
        news_items = fetch_ai_headlines()
    except Exception as e:
        print(f"  UYARI: haber basliklari cekilemedi ({e})")
        news_items = []

    news_words, news_examples = score_topics(news_items) if news_items else ([], {})
    lines = [
        f"Recent AI news signal ({len(news_items)} headlines from Hacker News, "
        "TechCrunch, The Verge, Ars Technica, MIT Tech Review, last ~48h).",
        "",
        "Top weighted keywords (weight = distinct headlines + HN engagement):",
    ]
    for word, score in news_words:
        lines.append(f"- '{word}' (score {score:.1f}) -> e.g. \"{news_examples[word]}\"")
    lines.append("")
    lines.append("Raw headlines (newest / most-discussed first):")
    for it in news_items[:22]:
        lines.append(f"- [{it['source']}] {it['title']}")
    if not news_items:
        lines.append("(no signal available right now - all sources failed)")

    recent = _recent_decisions()
    if recent:
        lines.append("")
        lines.append("RECENTLY COVERED (do NOT pick the same story/angle again):")
        for day, dec in recent:
            lines.append(f"- [{day}] {dec}")

    try:
        from editorial_arc import prompt_block as _arc_block
        arc = _arc_block()
        if arc:
            lines.append(arc)
    except Exception as e:
        print(f"  (editoryal yay atlandi: {e})")

    dig = _optimize_digest()
    if dig:
        lines.append(dig)

    eng = _engagement_digest()
    if eng:
        lines.append(eng)

    _op = _operator_rules()
    if _op:
        lines.append(_op)

    try:
        from reference_mine import digest as _refdig
        rd = _refdig()
        if rd:
            lines.append(rd)
    except Exception:
        pass

    return "\n".join(lines), news_items


def _collect_pitches(raw_signal):
    print("=== ARASTIRMA (4 konsey uyesi kendi merceginden aday oneriyor) ===\n")
    pitches = []
    for key in ["alpha", "beta", "gamma", "delta"]:
        persona = PERSONAS[key]
        caller = PROVIDER_CALLERS[persona["provider"]]
        si = persona["system_instruction"] + RESEARCHER_PROMPT_SUFFIX
        pitch = caller([{"role": "user", "content": raw_signal}], si)
        print(f"[{persona['display_name']}] {pitch}\n")
        pitches.append((persona["display_name"], pitch))
    return pitches


# run_editorial_meeting() sadece tek bir karar cumlesi doner (imza sabit -
# --auto-agenda ve make_episode_assets buna guveniyor). Ama pitch metinleri
# ve Aura'nin puanlama gerekcesi eskiden SADECE print ediliyordu, hicbir
# yerde saklanmiyordu (_daily_auto_*.log disinda erisilemezdi). mission_control
# panelinin "Konusmalar & Kararlar" sekmesi bunlari okuyabilsin diye burada
# tutup run_editorial_plan()'in plan.json'a yazmasini sagliyoruz.
_LAST_MEETING = {}


def run_editorial_meeting():
    """Aura'nin nihai konu karari (tek string). --auto-agenda ve
    make_episode_assets bunu kullanir - imza degismedi."""
    global _LAST_MEETING
    raw_signal, news_items = gather_raw_signal()
    print(f"\n{len(news_items)} haber basligindan sinyal cikarildi.\n")
    pitches = _collect_pitches(raw_signal)

    print("=== AURA PUANLIYOR + KARAR VERIYOR ===\n")
    pitch_summary = "\n\n".join(f"{n}'s pitch: {p}" for n, p in pitches)
    full = call_gemini(
        [{"role": "user", "content": f"Raw signal:\n{raw_signal}\n\nCouncil pitches:\n{pitch_summary}"}],
        AURA_EDITOR_PROMPT,
    )
    print(full)
    print("\n---\nBu Aura'nin editoryal karari - otomatik yayina girmedi.")
    _LAST_MEETING = {
        "pitches": [{"name": n, "pitch": p} for n, p in pitches],
        "scoring": full,
    }
    # Puanlama metnini DEGIL, tek satirlik temiz konuyu don (agenda / Short'a girer)
    m = re.search(r"PICK:\s*(.+)", full, re.I)
    if m:
        return m.group(1).strip().strip('"').rstrip(".") + "."
    # PICK yoksa (11 Eylul 2026: uzun puanlama cevabi saglayici token limitinde
    # kesilince oluyor - bkz providers.call_anthropic) - rastgele bir ara
    # paragrafi "konu" sanmak Short'u BOZUK bir veriden uretiyordu (gercek
    # olay: kesik puanlama metninden bir cumle "OpenAI gucu topluyor" konusuna
    # donustu). Bunun yerine modelden TEK net cumle iste - ucuz, kisa cagri.
    print("  [!] PICK: satiri gelmedi (cevap kesilmis olabilir) - tek cumle "
          "halinde tekrar isteniyor...")
    try:
        clean = call_gemini(
            [{"role": "user", "content": f"Your scoring below did not end with the "
              f"required PICK line. State your winning topic as ONE plain sentence, "
              f"12-22 words, no scores, no preamble:\n\n{full[-2000:]}"}],
            "Output only the one sentence.")
        clean = clean.strip().strip('"')
        if 20 < len(clean) < 260:
            return clean.rstrip(".") + "."
    except Exception:
        pass
    paras = [p.strip() for p in full.split("\n") if len(p.strip()) > 40 and ":" not in p.split()[0]]
    return paras[-1] if paras else full.strip()


def run_editorial_plan():
    """Konu karari + yapisal plan (tartisma acilari + Short kancalari +
    studio notu). dict doner."""
    decision = run_editorial_meeting()
    print("\n=== AURA'NIN YAYIN PLANI ===\n")
    raw = call_gemini([{"role": "user", "content": PLAN_PROMPT.format(decision=decision)}],
                      "You are Aura. Follow the output format exactly.")
    print(raw)

    def _g(tag):
        m = re.search(rf"{tag}\s*:\s*(.+)", raw, re.I)
        return m.group(1).strip() if m else ""

    plan = {
        "decision": decision,
        "angles": [x for x in (_g("ANGLE1"), _g("ANGLE2"), _g("ANGLE3")) if x],
        "short_hooks": [x for x in (_g("SHORT1"), _g("SHORT2"), _g("SHORT3")) if x],
        "studio_note": _g("STUDIO"),
        "council_pitches": _LAST_MEETING.get("pitches", []),
        "scoring_notes": _LAST_MEETING.get("scoring", ""),
    }
    _log_plan_history(plan)
    return plan


def _log_plan_history(plan):
    """27 Eyl 2026: plan.json her calistirmada UZERINE YAZILIYORDU - ayni gun icinde
    (elle 'Bugunun plani' ile) birden fazla konsey toplansa bir onceki toplanti
    KAYBOLUYORDU, hatta gercek videoyu ureten toplantinin metni bile. Artik HER
    toplanti (video uretse de uretmese de) o gunun plan_history.json'ina eklenir -
    hicbiri kaybolmaz. Panelde: Konusmalar & Kararlar sekmesi."""
    day = datetime.date.today().isoformat()
    hist_path = os.path.join(_ENGINE_DIR, day, "plan_history.json")
    try:
        hist = json.load(open(hist_path, encoding="utf-8"))
    except Exception:
        hist = []
    hist.append({**plan, "ts": datetime.datetime.now().isoformat(timespec="seconds")})
    try:
        os.makedirs(os.path.dirname(hist_path), exist_ok=True)
        json.dump(hist, open(hist_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"    [plan_history yazilamadi: {type(e).__name__}]")


def ask_aura_studio():
    print("\n=== AURA STUDIO'YU DEGERLENDIRIYOR ===\n")
    verdict = call_gemini([{"role": "user", "content": "Give your verdict on the studio."}],
                          STUDIO_REVIEW_PROMPT)
    print(verdict)
    return verdict


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic-only", action="store_true", help="sadece konu karari (tek satir)")
    ap.add_argument("--json", action="store_true", help="plani JSON olarak da yaz")
    a = ap.parse_args()

    if a.topic_only:
        print("\n>>> KONU:", run_editorial_meeting())
    else:
        plan = run_editorial_plan()
        studio = ask_aura_studio()
        plan["studio_verdict"] = studio
        if a.json:
            print("\n--- JSON ---")
            print(json.dumps(plan, ensure_ascii=False, indent=2))
