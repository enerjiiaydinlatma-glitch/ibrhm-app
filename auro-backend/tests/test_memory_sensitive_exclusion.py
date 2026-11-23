"""Hafiza cikarim promptunda hassas-bilgi kisitlamasi var mi (Paket 1 /
madde B8). LLM'in bu kurala GERCEKTE ne kadar uydugu bu testle
DOGRULANAMAZ (prompt-seviyesi bir kural, deterministik degil) - bu test
sadece kuralin promptta BULUNDUGUNU ve beklenen kategorileri kapsadigini
dogrular, mevcut test_council_opinion.py'deki instruction-icerik testleriyle
AYNI felsefeyle.
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_memory_sensitive_exclusion.py -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aura_brain  # noqa: E402


def test_sensitive_exclusion_rule_present_in_memory_extraction_prompt():
    prompt = aura_brain._MEMORY_EXTRACTION_PROMPT
    assert "HASSAS BILGI KISITLAMASI" in prompt
    for keyword in (
        "saglik durumu", "intihar", "cinsel", "din", "suc",
    ):
        assert keyword in prompt.lower()


def test_sensitive_exclusion_explicitly_overrides_user_request():
    """Kullanici acikca 'hatirla' dese bile kaydedilmemeli - bu satir
    promptta ACIKCA yazili olmali, yoksa model varsayilan olarak
    kullanicinin istegini kurala tercih edebilir."""
    prompt = aura_brain._MEMORY_EXTRACTION_PROMPT
    assert "ACIKCA istese BILE" in prompt
