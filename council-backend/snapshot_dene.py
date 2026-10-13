"""'Son calisan kopya' snapshot'ini TEKRAR DENEYEREK ve SESSIZ KALMADAN alir.

Eski davranis (11 Ekim 2026 bulgusu): mission_control, acildiktan 30 sn sonra /api/status'u 2 sn zaman asimiyla bir kez soruyor,
yanit gelmezse (ses sunucusu yuklenirken vs.) HIC denemeden vazgeciyordu; snapshot 6 gun alinamadi, kimse fark etmedi.
Simdi: yanit gelmezse ya da snapshot ok:False donerse sebep yazilir ve bekleyip tekrar denenir.
Saf fonksiyon: sunucu/snapshot/uyku/log disaridan verilir (test edilebilir).
"""
import time


def dene(calisiyor, snapshot, uyku=time.sleep, log=print, deneme=10, bekle=60):
    """calisiyor() -> bool, snapshot() -> {'ok': bool, 'files': n, 'error': str}. Basarida True doner."""
    for i in range(1, deneme + 1):
        try:
            if calisiyor():
                r = snapshot()
                if r and r.get("ok"):
                    log(f"[snapshot] alindi: {r.get('files')} dosya (deneme {i}/{deneme})")
                    return True
                log(f"[snapshot ALINMADI] deneme {i}/{deneme}: {(r or {}).get('error', 'bilinmeyen sebep')}")
            else:
                log(f"[snapshot] sunucu {i}/{deneme}. denemede yanit vermedi (/api/status); {bekle} sn sonra tekrar")
        except Exception as e:  # noqa: BLE001
            log(f"[snapshot hatasi] deneme {i}/{deneme}: {type(e).__name__}: {str(e)[:120]}")
        if i < deneme:
            uyku(bekle)
    log(f"[snapshot] {deneme} denemede de ALINAMADI - 'son calisan kopya' eski kalabilir (Derin test bunu kirmizi gosterir)")
    return False
