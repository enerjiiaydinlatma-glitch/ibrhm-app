"""KAYNAK CEKICI - sayfa metnini KODLA ceker, cumleleri cikarir, kanit adaylarini numarali sunar.
Alintilar elle kopyalanmaz; paket (_engine/kaynak_*.json) motora --source ile verilir ve
uretilen metindeki her alinti/sayi bu pakete karsi MEKANIK olarak dogrulanir (source_check.py).

Kullanim:
  python kaynak_cek.py https://mistral.ai/news/mistral-large-4/
  python kaynak_cek.py --file sayfa.html --url https://...        (sayfa JS ile yukleniyorsa: Ctrl+S ile kaydet)
  secenekler: --claim-key "state-of-the-art"  --keys "finance,manufactur"  --select 1,4,7  --facts "18 of 19; 16"
"""
import argparse
import datetime
import json
import os
import re
import sys
import unicodedata
import urllib.request
from html.parser import HTMLParser

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")

SKIP = {"script", "style", "noscript", "svg", "template", "head"}
BLOCK = {"p", "div", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "td", "th", "section",
         "article", "header", "footer", "blockquote", "figcaption", "table", "pre", "button", "main", "nav", "title"}
DEFAULT_KEYS = ["state-of-the-art", "finance", "financial", "manufactur", "third party", "third-party", "independent",
                "internal", "on par", "outperform", "exceed", "benchmark", "evaluat"]
STRONG = {"third party", "third-party", "independent", "internal", "on par", "finance", "financial", "manufactur"}

_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-",
        " ": " ", "…": "...", "•": "-"}


def ascii_norm(s):
    for k, v in _MAP.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip()


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.cur, self.skip, self.title, self._in_title = [], [], 0, "", False

    def _flush(self):
        t = "".join(self.cur).strip()
        if t:
            self.lines.append(t)
        self.cur = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP and tag != "head":
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in BLOCK:
            self._flush()

    def handle_endtag(self, tag):
        if tag in SKIP and tag != "head" and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK:
            self._flush()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.cur.append(data)


def parse_html(html):
    p = _P()
    p.feed(html)
    p._flush()
    return ascii_norm(p.title), [ascii_norm(x) for x in p.lines if ascii_norm(x)]


def split_sentences(lines, min_len=25):
    out, seen = [], set()
    for ln in lines:
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", ln):
            s = s.strip()
            if len(s) >= min_len and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
    return out


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SignCouncil/1.0",
                                               "Accept-Language": "en-US,en;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        cs = r.headers.get_content_charset() or "utf-8"
    return raw.decode(cs, errors="replace")


def score(sentence, keys):
    low = sentence.lower()
    hit = [k for k in keys if k in low]
    return len(set(hit)) + sum(1 for k in hit if k in STRONG), hit


def build_packet(url, title, sentences, claim_key, keys, selected_idx, facts, fetched_at):
    claim = next((s for s in sentences if claim_key.lower() in s.lower()), "")
    evidence = [sentences[i] for i in selected_idx if sentences[i] != claim]
    if claim:
        topic = f"{title}: does the evidence on the page support its own claim? Claim on the page: {claim}"
    else:
        topic = f"{title}: what the page states and what it shows"
    topic = topic.replace('"', "'")[:360]
    quoted = ([claim] if claim else []) + evidence
    angle = ("Use ONLY these verbatim sentences from [" + url + ", read " + fetched_at[:10] + "] and add no other factual "
             "claim, number or motive: " + " / ".join('"' + q.replace('"', "'") + '"' for q in quoted))
    if facts:
        angle += " | Chart numbers read by the operator from the page: " + "; ".join(facts)
    return {"url": url, "title": title, "fetched_at": fetched_at, "claim": claim, "evidence": evidence,
            "facts": facts, "topic": topic, "angle": angle, "all_sentences": sentences}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--file")
    ap.add_argument("--claim-key", default="state-of-the-art")
    ap.add_argument("--keys", default="")
    ap.add_argument("--select", default="")
    ap.add_argument("--facts", default=None)
    ap.add_argument("--auto", action="store_true", help="soru sorma: onerilen kanit adaylarini sec")
    a = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not a.url:
        print("URL gerekli.")
        return 2
    try:
        html = open(a.file, encoding="utf-8", errors="replace").read() if a.file else fetch(a.url)
    except Exception as e:
        print(f"[HATA] Sayfa alinamadi: {type(e).__name__}: {e}")
        return 1
    title, lines = parse_html(html)
    sentences = split_sentences(lines)
    print(f"Baslik: {title}\nMetin: {sum(len(x) for x in lines)} karakter, {len(sentences)} cumle")
    if len(sentences) < 15:
        print("[HATA] Sayfa metni cok kisa - sayfa JavaScript ile yukleniyor olabilir.\n"
              "  Cozum: tarayicida Ctrl+S ile 'Web Sayfasi, Yalnizca HTML' kaydet, sonra:\n"
              f'  python kaynak_cek.py --file kaydedilen.html "{a.url}"')
        return 1
    keys = [k.strip().lower() for k in a.keys.split(",") if k.strip()] or DEFAULT_KEYS
    scored = [(score(s, keys), i, s) for i, s in enumerate(sentences)]
    cands = [(sc, i, s) for sc, i, s in scored if sc[0] > 0]
    cands.sort(key=lambda x: (-x[0][0], x[1]))
    cands = cands[:40]
    claim = next((s for s in sentences if a.claim_key.lower() in s.lower()), "")
    print("\nIDDIA CUMLESI:", claim or f"(sayfada '{a.claim_key}' gecen cumle yok)")
    print("\nKANIT ADAYLARI (anahtar kelimelere gore):")
    for n, (sc, i, s) in enumerate(cands, 1):
        print(f"  {n:>2}. [{', '.join(sc[1])}] {s[:230]}")
    if not cands:
        print("  (aday yok)")
    rec = [n for n, (sc, i, s) in enumerate(cands[:6], 1)]
    if a.select:
        chosen = [int(x) for x in re.findall(r"\d+", a.select)]
    elif a.auto:
        chosen = rec
    else:
        raw = input(f"\nKanit olacak numaralar (ornek 1,3,4 | Enter = onerilen {rec}): ").strip()
        chosen = [int(x) for x in re.findall(r"\d+", raw)] if raw else rec
    chosen = [n for n in chosen if 1 <= n <= len(cands)]
    selected_idx = [cands[n - 1][1] for n in chosen]
    if a.facts is not None:
        facts = [f.strip() for f in a.facts.split(";") if f.strip()]
    else:
        raw = input("Grafikte GORDUGUN sayilar (metinde yok; ornek: 'Model X solved 18 of 19; Y 16'; Enter = yok): ").strip()
        facts = [f.strip() for f in raw.split(";") if f.strip()]
    fetched_at = datetime.datetime.now().isoformat(timespec="seconds")
    packet = build_packet(a.url, title, sentences, a.claim_key, keys, selected_idx, [ascii_norm(f) for f in facts], fetched_at)
    os.makedirs(ENGINE, exist_ok=True)
    path = os.path.join(ENGINE, f"kaynak_{datetime.datetime.now():%Y%m%d_%H%M%S}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(packet, f, ensure_ascii=True, indent=1)
    with open(os.path.join(ENGINE, "kaynak_son.txt"), "w", encoding="utf-8") as f:
        f.write(path)
    print(f"\n[OK] Kaynak paketi: {path}")
    print("KONU :", packet["topic"])
    print("KANIT:", len(packet["evidence"]), "cumle", "| iddia:", "var" if packet["claim"] else "YOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
