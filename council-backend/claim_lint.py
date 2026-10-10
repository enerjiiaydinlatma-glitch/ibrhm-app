"""Yayin oncesi iddia taramasi - baslik/kanca/senaryo icin KABA uyari listesi.
sensitivity_gate'in YERINE GECMEZ, ustune ek bir hizli kontroldur; hicbir seyi engellemez, sadece isaretler.

Kullanim:
  python claim_lint.py "Mistral Le Chonk Costs Force $40K Monthly Cloud Registry Lock"
  python claim_lint.py --file senaryo.txt
  python claim_lint.py --packages assets/thumbnails/episode_xxx_packages.json
Cikis kodu: 0 temiz, 1 isaret var.
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

INTENT = r"mask(?:s|ed|ing)?|hidden|hides?|disguis\w*|trap(?:s|ped)?|illusion|decepti\w+|deliberate\w*|intentional\w*|secret(?:ly)?|quiet(?:ly)?|cover[- ]?up|covered up|lie[sd]?|lying|scam|fraud\w*|rig(?:s|ged)?|manipulat\w+|conspir\w+|weaponi[sz]\w*|force[sd]?"
CRIME = r"crime|criminal|illegal|unlawful|fraud|bribe\w*|embezzl\w+|antitrust violation|broke the law"
NUMBER = r"\$\s?\d[\d.,]*\s?(?:[kKmMbB]|million|billion|thousand)?|\b\d[\d.,]*\s?%|\b\d[\d.,]*\s?(?:[kK]|million|billion)\b"
COMPARE = r"\b(?:\w+er|more|less|worse|better) [\w\- ]{0,25}\bthan\b|\bis not (?:open|free|real|safe)\b|\bnot (?:really )?open\b"
ABSOLUTE = r"\b(?:always|never|permanently|every(?:one|body)?|all developers|no one|nobody|impossible)\b"

BLOCKING = {"NIYET ATFI", "SUC DILI", "KARSILASTIRMA/ETIKET"}  # yayinda private'a dusurur (RAKAM/MUTLAK sadece uyarir)

RULES = [
    ("NIYET ATFI", re.compile(INTENT, re.I), "Niyet/gizlilik ima eder. Yapiyi anlat, niyeti yorumlama."),
    ("SUC DILI", re.compile(CRIME, re.I), "Suc iddiasi: sensitivity_gate 'critical' kapsaminda olabilir."),
    ("RAKAM", re.compile(NUMBER, re.I), "Rakam: birincil belgede gecmiyorsa yazma (kaynak karti gerekir)."),
    ("KARSILASTIRMA/ETIKET", re.compile(COMPARE, re.I), "Karsilastirma veya etiket iddiasi: iki tarafin belgesi de gerekli."),
    ("MUTLAK IFADE", re.compile(ABSOLUTE, re.I), "Mutlak ifade: belge bunu destekliyor mu?"),
]


def lint(text):
    out = []
    for name, rx, why in RULES:
        hits = sorted({m.group(0).strip() for m in rx.finditer(text or "")}, key=str.lower)
        if hits:
            out.append((name, hits, why))
    return out


_TIRNAK = re.compile(r'["“]([^"”]{20,})["”]')
ALINTIDA_DA_ENGEL = ("NIYET ATFI", "SUC DILI")


def lint_kaynakli(text, corpus):
    """lint(), ama KAYNAKTA BIREBIR bulunan tirnakli alintilar icin karsilastirma/etiket/rakam/mutlak kurallari uygulanmaz:
    o cumle bizim degil, sayfanin kendi sozudur (Receipt'in amaci tam olarak sirketin kendi iddiasini alintilamak; ornek:
    'outstanding requests for 2-3x more GPUs than are available'). NIYET ATFI ve SUC DILI ise alintinin ICINDE de engellenir.
    Bizim kendi kelimelerimiz (alinti disi metin) TUM kurallardan gecer. corpus: source_check.corpus(paket)."""
    from kaynak_cek import ascii_norm
    alintilar = []

    def _al(m):
        q = m.group(1)
        if ascii_norm(q).lower().rstrip(".,;:") in (corpus or ""):
            alintilar.append(q)
            return '"Q"'
        return m.group(0)

    kalan = _TIRNAK.sub(_al, text or "")
    sonuc = {n: (list(h), w) for n, h, w in lint(kalan)}
    for q in alintilar:
        for n, h, w in lint(q):
            if n in ALINTIDA_DA_ENGEL:
                eski = sonuc.get(n, ([], w))
                sonuc[n] = (sorted(set(eski[0]) | set(h), key=str.lower), w)
    return [(n, h, w) for n, (h, w) in sonuc.items()]


def report(label, text):
    res = lint(text)
    print(f"[{'ISARET' if res else 'temiz '}] {label}")
    for name, hits, why in res:
        print(f"    - {name}: {', '.join(hits)}  -> {why}")
    return bool(res)


def main(argv):
    flagged = False
    if argv and argv[0] == "--file":
        flagged = report(argv[1], open(argv[1], encoding="utf-8").read())
    elif argv and argv[0] == "--packages":
        data = json.load(open(argv[1], encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("packages", data.get("items", [data]))
        for i, p in enumerate(items):
            blob = " | ".join(str(v) for v in (p.values() if isinstance(p, dict) else [p]))
            flagged |= report(f"paket {i + 1}: {blob[:90]}", blob)
    elif argv:
        flagged = report(" ".join(argv)[:90], " ".join(argv))
    else:
        print(__doc__)
        return 2
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
