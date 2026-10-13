"""Elle konu verme (--topic): Aura'nin editoryal toplantisini ATLAR, plani operator verir.
Neden: 7 Ekim 2026 - Aura'nin sectigi konu ve urettigi A/B basliklari kaynaksiz iddia
(uydurma "$40K", "AWS", niyet atfi) icerdi; operator konuyu ve belgeyi kendisi belirlemeli.
"""
from claim_lint import lint


def build_plan(topic, angle=""):
    topic = (topic or "").strip()
    if len(topic) < 15:
        raise ValueError("--topic en az 15 karakter olmali (tek net cumle: ne, kim, hangi belge).")
    angle = (angle or "").strip()
    return {
        "decision": topic,
        "angles": [angle] if angle else [],
        "short_hooks": [],
        "studio_note": "",
        "council_pitches": [],
        "scoring_notes": "MANUEL KONU (operator --topic ile verdi; Aura editoryal toplantisi atlandi)",
        "manual": True,
    }


def lint_plan(plan):
    """[(kural, [bulunanlar], aciklama)] - konu + acilar uzerinde."""
    return lint(" | ".join([plan.get("decision", "")] + list(plan.get("angles") or [])))
