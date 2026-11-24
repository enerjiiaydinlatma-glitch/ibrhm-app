"""aura_tools._tool_math guvenlik + dogruluk testleri (Paket 1 / madde C10:
"9**9**9**9" gibi bir ifade eskiden operator.pow'u sinirsiz cagirip CPU/
bellek kilitleyebiliyordu).
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_aura_tools_math.py -q
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aura_tools  # noqa: E402

# Gercekci bir "kilitlenme" en az birkac saniye surer - 2sn sinirini
# rahatlikla gecemeyen bir cevap, DoS korumasinin calistigini gosterir.
_MAX_SECONDS = 2.0


def _timed(query: str):
    t0 = time.monotonic()
    result = aura_tools._tool_math(query)
    elapsed = time.monotonic() - t0
    assert elapsed < _MAX_SECONDS, f"{query!r} {elapsed:.2f}s surdu (DoS riski)"
    return result


def test_extreme_power_tower_is_rejected_quickly_not_computed():
    # Python'da ** sagdan sola birlesir: 9**9**9**9 == 9**(9**(9**9)) -
    # astronomik bir sayi, gercekten hesaplanmaya calisilirsa kilitlenir.
    assert _timed("9**9**9**9") == ""


def test_large_but_reasonable_power_still_works():
    assert _timed("2**50") == "Hesap sonucu: 2**50 = 1125899906842624"


def test_fractional_power_still_works():
    assert _timed("1.5**20") == "Hesap sonucu: 1.5**20 = 3325.2567"


def test_ordinary_arithmetic_unaffected():
    assert _timed("2 carpi 21") == "Hesap sonucu: 2 * 21 = 42"
    assert _timed("10 bolu 4") == "Hesap sonucu: 10 / 4 = 2.5"


def test_very_long_query_is_truncated_not_slow():
    assert _timed("9**" * 2000 + "9") == ""
