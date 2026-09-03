"""Aura'nin cagirabildigi araclar (Seviye 1d).

"Aura emri verir, ajanlari kullanir" - route_request bir turun hangi araca
ihtiyaci oldugunu tahmin eder (time / search / math), burasi o araci
calistirir, sonuc Aura'nin sistem talimatina KISA bir "arac notu" olarak
enjekte edilir. Aura son cevabi yine KENDI sesiyle, kendi kararlariyla
uretir - arac sadece ona gercek/guncel bilgi verir.

Tasarim: PRE-FETCH artirimi (LLM'in uretim ortasinda arac cagirmasi degil).
Basit, guvenli, yaygin durumlari kapsar. Tam agentic donguye (self-host
model function-calling'i saglamlasinca) sonra gecilebilir.

Her arac HIZLI ve HATA-GUVENLI: bir arac patlarsa sessizce atlanir
(Aura aracsiz cevaplar), sohbet ASLA kirilmaz.
"""
from __future__ import annotations

import ast
import operator
import re
from datetime import datetime, timedelta, timezone

# Turkiye saati (UTC+3, DST yok - 2016'dan beri sabit).
_TR_TZ = timezone(timedelta(hours=3))

_TR_DAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]
_TR_MONTHS = ["Ocak", "Subat", "Mart", "Nisan", "Mayis", "Haziran", "Temmuz",
              "Agustos", "Eylul", "Ekim", "Kasim", "Aralik"]


def _now_tr() -> datetime:
    return datetime.now(_TR_TZ)


# --- time / tarih ---
_DATE_NUM_RE = re.compile(r"(\d{1,2})[.\-/ ](\d{1,2})(?:[.\-/ ](\d{2,4}))?")
_MONTH_KEYS = {
    "ocak": 1, "subat": 2, "şubat": 2, "mart": 3, "nisan": 4, "mayis": 5, "mayıs": 5,
    "haziran": 6, "temmuz": 7, "agustos": 8, "ağustos": 8, "eylul": 9, "eylül": 9,
    "ekim": 10, "kasim": 11, "kasım": 11, "aralik": 12, "aralık": 12,
}
_DATE_NAME_RE = re.compile(
    r"(\d{1,2})\s+(" + "|".join(_MONTH_KEYS) + r")(?:\s+(\d{4}))?"
)


def _parse_target_date(q: str, now: datetime):
    m = _DATE_NAME_RE.search(q)
    if m:
        d = int(m.group(1)); mo = _MONTH_KEYS[m.group(2)]
        y = int(m.group(3)) if m.group(3) else now.year
        try:
            return datetime(y, mo, d, tzinfo=_TR_TZ)
        except ValueError:
            return None
    m = _DATE_NUM_RE.search(q)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        y = int(m.group(3)) if m.group(3) else now.year
        if y < 100:
            y += 2000
        # yil-basli yazim ("2027 1 1") - ilk grup yila benziyorsa cevir
        if int(m.group(1)) > 31:
            y, mo, d = int(m.group(1)), d, mo if m.group(3) is None else int(m.group(3))
        try:
            return datetime(y, mo, d, tzinfo=_TR_TZ)
        except ValueError:
            return None
    return None


def _tool_time(query: str) -> str:
    now = _now_tr()
    q = (query or "").lower()
    lines = [
        f"Su an (Turkiye saati): {now.day} {_TR_MONTHS[now.month - 1]} {now.year}, "
        f"{_TR_DAYS[now.weekday()]}, saat {now:%H:%M}."
    ]
    if any(k in q for k in ("kac gun", "kalan", "kala", "kadar", "gun var", "gun kaldi", "ne zaman")):
        target = _parse_target_date(q, now)
        if target:
            delta = (target.date() - now.date()).days
            ds = f"{target.day} {_TR_MONTHS[target.month - 1]} {target.year}"
            if delta > 0:
                lines.append(f"{ds} tarihine {delta} gun var ({_TR_DAYS[target.weekday()]}).")
            elif delta < 0:
                lines.append(f"{ds} tarihi {-delta} gun once geride kaldi.")
            else:
                lines.append(f"{ds} bugun.")
    return " ".join(lines)


# --- math ---
_MATH_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos, ast.FloorDiv: operator.floordiv,
}


def _safe_eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _MATH_OPS:
        return _MATH_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _MATH_OPS:
        return _MATH_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError("izin verilmeyen ifade")


def _tool_math(query: str) -> str:
    q = (query or "").lower()
    # "yuzde 18" -> "18/100*", basit Turkce -> sembol
    q = q.replace(",", ".")
    q = re.sub(r"yuzde\s*(\d+(?:\.\d+)?)", r"(\1/100)", q)
    q = (q.replace("carpi", "*").replace("carpim", "*").replace("bolu", "/")
           .replace("arti", "+").replace("eksi", "-").replace("x", "*").replace("%", "/100"))
    # sadece rakam ve operatorleri birak
    expr = re.sub(r"[^0-9.+\-*/()% ]", " ", q).strip()
    expr = expr.replace("%", "/100")
    if not expr or not re.search(r"\d", expr):
        return ""
    # birden fazla sayi-operator kumesi olabilir; en uzun makul parcayi al
    try:
        tree = ast.parse(expr, mode="eval")
        val = _safe_eval(tree.body)
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        elif isinstance(val, float):
            val = round(val, 4)
        return f"Hesap sonucu: {expr} = {val}"
    except Exception:
        return ""


# --- search (grounded) ---
def _tool_search(query: str) -> str:
    try:
        import aura_brain
        return aura_brain.grounded_answer(query)
    except Exception as e:
        print(f"TOOL search hata: {type(e).__name__}: {e}")
        return ""


_TOOLS = {"time": _tool_time, "math": _tool_math, "search": _tool_search}


def run_tool(name: str, query: str) -> str:
    """Araci calistirip kisa bir metin doner. Hata/bos -> '' (cagiran atlar)."""
    fn = _TOOLS.get(name)
    if not fn:
        return ""
    try:
        out = (fn(query) or "").strip()
        return out[:1200]
    except Exception as e:
        print(f"TOOL {name} hata: {type(e).__name__}: {e}")
        return ""
