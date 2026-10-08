"""Uretilen metindeki ALINTI ve SAYILARI kaynak paketine karsi mekanik dogrular.
Garanti mantigi: metinde tirnak icinde bir alinti veya (yil/tek hane disinda) bir sayi varsa,
kaynak paketinde (sayfa cumleleri + operatorun girdigi grafik sayilari) AYNEN bulunmak zorunda.
Bulunmazsa video private'a dusurulur (aura_engine --source ile).
"""
import json
import re

from kaynak_cek import ascii_norm

_Q = re.compile(r'["“]([^"”]{20,})["”]')
_N = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def load_packet(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def corpus(packet):
    parts = [packet.get("title", ""), packet.get("url", "")] + list(packet.get("all_sentences", [])) + list(packet.get("facts", []))
    return ascii_norm(" ".join(parts)).lower()


def _num_key(tok):
    return tok.replace("$", "").replace(",", "").rstrip("%").rstrip(".")


def numbers(text):
    return {_num_key(m.group(0)) for m in _N.finditer(text)}


def _significant(tok):
    k = _num_key(tok)
    if re.fullmatch(r"(19|20)\d\d", k):
        return False
    return "." in k or tok.endswith("%") or tok.startswith("$") or len(k) >= 2


def check(texts, packet):
    """texts: baslik/senaryo/aciklama listesi. Donus: sorun listesi (bos = temiz)."""
    body = ascii_norm(" ".join(t for t in texts if t))
    corp = corpus(packet)
    issues = []
    for q in _Q.findall(body):
        parts = [p.strip() for p in re.split(r"\.{3}|\[\.\.\.\]", q) if len(p.strip()) >= 15]
        for p in parts or [q]:
            if ascii_norm(p).lower().rstrip(".,;:") not in corp:
                issues.append(f"alinti kaynakta yok: \"{p[:80]}\"")
    src_nums = numbers(corp)
    seen = set()
    for m in _N.finditer(body):
        tok = m.group(0)
        if _significant(tok) and _num_key(tok) not in src_nums and _num_key(tok) not in seen:
            seen.add(_num_key(tok))
            issues.append(f"sayi kaynakta yok: {tok}")
    return issues
