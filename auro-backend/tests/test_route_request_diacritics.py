"""route_request diakritik-fold testleri (Paket 1 / madde C11: "dolar kaç?"
gibi DOGRU Turkce yazim, ASCII-yazilmis _TOOL_HINTS/_DEEP_HINTS ile hic
eslesmiyordu).
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_route_request_diacritics.py -q
"""
import os
import sys
import tempfile

os.environ["DB_DIR"] = tempfile.mkdtemp(prefix="aura_route_test_")
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aura_brain  # noqa: E402


def test_correctly_accented_search_trigger_detected():
    assert aura_brain.route_request("dolar kaç?")["wants_tool"] == "search"
    assert aura_brain.route_request("euro kaç oldu")["wants_tool"] == "search"


def test_ascii_search_trigger_still_detected():
    assert aura_brain.route_request("dolar kac")["wants_tool"] == "search"


def test_correctly_accented_math_trigger_detected():
    assert aura_brain.route_request("bunun yüzde kaçı eder")["wants_tool"] == "math"


def test_correctly_accented_deep_hint_affects_tier():
    r = aura_brain.route_request("bu konuyu adım adım açıkla")
    assert r["tier"] == "deep"


def test_unrelated_message_has_no_tool():
    assert aura_brain.route_request("bugün hava nasıl?")["wants_tool"] is None
