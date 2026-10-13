"""YouTube yuklemesi icin yeniden deneme mantigi (googleapiclient'a bagimli degil; test edilebilir).

410 'Gone' (resumable oturum gecersiz), 5xx, 408/429 ve ag kopmalari GECICIDIR: yuklemeyi YENI oturumla bastan dener.
Kalici hatalar (401/403 yetki-kota, 400 gecersiz govde) tekrar denenmez, aynen yukari firlatilir.
"""
import time

GECICI_KODLAR = {408, 410, 429, 500, 502, 503, 504}
DENEME = 4
BEKLE = (2, 4, 8, 16)


def gecici_mi(e):
    resp = getattr(e, "resp", None)
    kod = getattr(resp, "status", None)
    if kod is not None:
        try:
            return int(kod) in GECICI_KODLAR
        except (TypeError, ValueError):
            return False
    return isinstance(e, (ConnectionError, TimeoutError, OSError))


def dene(fn, uyku=time.sleep, log=print):
    """fn() her cagrida YENI bir yukleme oturumu acip tamamlamali. Basarida fn'in donusunu verir."""
    son = None
    for i in range(DENEME):
        try:
            return fn()
        except Exception as e:                       # noqa: BLE001
            if not gecici_mi(e) or i == DENEME - 1:
                raise
            son = e
            b = BEKLE[min(i, len(BEKLE) - 1)]
            log(f"  [yukleme] gecici hata ({type(e).__name__}: {str(e)[:80]}) -> {b} sn sonra YENI oturumla tekrar ({i + 2}/{DENEME})")
            uyku(b)
    raise son
