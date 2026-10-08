"""RECEIPT formati: kural tabanli, MODEL YAZMAZ. Metin = operatorun yazdigi kalip + sayfadan BIREBIR alintilar.
Yayin oncesi kod her alintiyi kaynak paketinde (sayfa metni) arar; bulunamazsa uretim yapilmaz.

Receipt JSON:
{ "company","product","source_name","source_date","url","title","hookthumb",
  "beats":[{"who","screen","label","line":"... {q1} ... {q2}","quotes":["birebir alinti",...],"stamp":"(sadece hukum karti)"}] }
"""
import json
import re

from claim_lint import BLOCKING, lint
from kaynak_cek import ascii_norm
from source_check import check as src_check, corpus

STAMPS = {"SUPPORTED", "PARTLY SUPPORTED", "NOT SUPPORTED BY THE PAGE", "NOT SHOWN ON THE PAGE"}
SPEAKERS = {"aura", "alpha", "gamma", "beta", "delta"}


def load_receipt(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def spoken(beat):
    """Beat'in sesli metni: sablondaki {q1},{q2}... yerine tirnakli birebir alinti."""
    fills = {f"q{i + 1}": '"' + q + '"' for i, q in enumerate(beat.get("quotes", []))}
    return beat["line"].format(**fills)


def verify_receipt(r, packet):
    issues = []
    corp = corpus(packet)
    beats = r.get("beats", [])
    if not 4 <= len(beats) <= 6:
        issues.append(f"beat sayisi 4-6 olmali ({len(beats)})")
    if not r.get("title") or r.get("company", "").lower() not in r.get("title", "").lower():
        issues.append("baslik sirket adini icermeli")
    stamps = [b.get("stamp") for b in beats if b.get("stamp")]
    if len(stamps) != 1 or stamps[0] not in STAMPS:
        issues.append(f"tam 1 hukum damgasi ve izinli listeden olmali: {sorted(STAMPS)}")
    texts = [r.get("title", "")]
    for i, b in enumerate(beats, 1):
        if b.get("who") not in SPEAKERS:
            issues.append(f"beat {i}: gecersiz konusmaci")
        try:
            line = spoken(b)
        except (KeyError, IndexError) as e:
            issues.append(f"beat {i}: sablon hatasi {e}")
            continue
        if len(line.split()) > 34:
            issues.append(f"beat {i}: cok uzun ({len(line.split())} kelime)")
        texts.append(line)
        for q in b.get("quotes", []):
            if ascii_norm(q).lower() not in corp:
                issues.append(f"beat {i}: alinti sayfada BULUNAMADI: \"{q[:70]}\"")
    issues += src_check(texts, packet)
    issues += [f"{n}: {', '.join(h)}" for n, h, _ in lint(" | ".join(texts)) if n in BLOCKING]
    return issues


def to_script(r, fetched_at=""):
    beats, lines = [], []
    src = f"{r['source_name']} | published {r['source_date']}"
    for b in r["beats"]:
        line = spoken(b)
        lines.append(line)
        spec = {"label": b.get("label", ""), "quotes": b.get("quotes", []), "stamp": b.get("stamp", ""), "source": src}
        beats.append((b["who"], b.get("screen", b.get("label", "")).upper(), line, spec))
    desc = (f"{lines[0]}\n\nSource: {r.get('url', r['source_name'])}\n"
            f"Page published {r['source_date']}" + (f", read {fetched_at[:10]}" if fetched_at else "") +
            ". Quotes are verbatim from the page; the verdict is Sign Council's own reading.\n\n"
            "#AI #AINews #SignCouncil")
    tags = ["AI", "AI news", "SignCouncil", "shorts", r["company"], r.get("product", r["company"])]
    return {"beats": beats, "title": r["title"], "hookthumb": r.get("hookthumb", "CLAIM VS PAGE").upper(),
            "desc": desc, "tags": tags}
