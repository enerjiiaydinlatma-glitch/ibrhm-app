"""
Aura Reminders
===============
Kullanici istegi (2026-08-26, kendi ornegi): "Hatirlatma alarmi olabilir
mesela haftaya persembe gunu maca gidecegim ama bilet bulmam icin bir iki
gun onceden almam lazim gibi mesela?"

Mevcut aura_lifestyle.py'deki UPCOMING_EVENT_CATEGORY bunun TERSINI
yapiyordu - olay GECTIKTEN SONRA "nasil gecti" diye soruyor, olaydan
ONCE harekete gecirecek bir uyari vermiyordu. Bu modul, mesajlarda
GELECEKTEKI, tarihi belirtilebilen bir etkinlik + ona bagli bir hazirlik
ihtiyaci varsa bunu yakalayip `reminders` tablosuna yaziyor.

Maliyet bilinci: her mesajda LLM cagirmak yerine ONCE ucuz bir anahtar
kelime on-elemesi (_looks_schedulable) yapiliyor - hem bir tarih ifadesi
HEM bir etkinlik kelimesi gecmeyen mesajlar LLM'e hic gonderilmiyor. Bu,
extract_memory_candidate/extract_style_signals ile ayni "sadece kanit
varsa pahali isi yap" ilkesi.
"""

import re
from datetime import date, datetime, timedelta

import aura_brain
import database

_DATE_WORDS = (
    "pazartesi", "sali", "salı", "carsamba", "çarşamba", "persembe", "perşembe",
    "cuma", "cumartesi", "pazar",
    "yarin", "yarın", "haftaya", "gelecek hafta", "önümüzdeki", "onumuzdeki",
    "ayın", "ayin",
)
_EVENT_WORDS = (
    "mac", "maç", "konser", "sinav", "sınav", "toplanti", "toplantı",
    "randevu", "ucak", "uçak", "bilet", "doğum günü", "dogum gunu",
    "davet", "görüşme", "gorusme", "etkinlik", "parti", "sunum", "seyahat",
    "tatil", "uçuş", "ucus", "operasyon", "ameliyat", "mülakat", "mulakat",
)


def _looks_schedulable(message: str) -> bool:
    text = message.lower()
    return any(w in text for w in _DATE_WORDS) and any(w in text for w in _EVENT_WORDS)


_REMINDER_EXTRACTION_PROMPT = """
Bugunun tarihi: {today} ({weekday}).

Asagidaki kullanici mesajinda GELECEKTE gerceklesecek, tarihi (kesin ya
da "haftaya persembe" gibi goreli de olsa) belirtilebilen bir etkinlik
VE bu etkinlikle ilgili onceden yapilmasi gereken somut bir hazirlik/
hatirlatma ihtiyaci var mi? (ornek: "persembe maca gidecegim, bilet
almam lazim" -> etkinlik persembe gunku mac, hatirlatma bilet almak).

Eger boyle bir sey YOKSA (mesaj gecmisten bahsediyorsa, tarih tahmin
edilemiyorsa, ya da acik bir hazirlik/hatirlatma ihtiyaci yoksa) SADECE
"YOK" yaz, baska hicbir sey yazma.

Eger VARSA, TAM OLARAK bu formatta 3 satir yaz (baska hicbir aciklama/
yorum ekleme):
KONU: <kisa, ne icin oldugu - ornek: persembe gunku mac icin bilet almak>
ETKINLIK_TARIHI: <YYYY-MM-DD>
HATIRLATMA_TARIHI: <YYYY-MM-DD>

HATIRLATMA_TARIHI, kullanicinin belirttigi hazirlik suresine gore
ETKINLIK_TARIHI'nden ONCEKI (ya da ayni) bir tarih olmali - kullanici
"1-2 gun once" gibi bir sure belirtmisse ona gore hesapla, hicbir sure
belirtilmemisse ETKINLIK_TARIHI ile ayni tarihi yaz.

Kullanici mesaji: "{message}"
""".strip()

_TURKISH_WEEKDAYS = ["Pazartesi", "Sali", "Carsamba", "Persembe", "Cuma", "Cumartesi", "Pazar"]


def extract_reminder_candidate(user_id: int, message: str) -> None:
    """Sinyal yoksa (on-eleme gecmezse) HICBIR API cagrisi yapmadan cikar."""
    if not _looks_schedulable(message):
        return

    today = date.today()
    prompt = _REMINDER_EXTRACTION_PROMPT.format(
        today=today.isoformat(),
        weekday=_TURKISH_WEEKDAYS[today.weekday()],
        message=message,
    )

    try:
        text = aura_brain.BACKGROUND_PROVIDERS[aura_brain.BACKGROUND_PROVIDER](prompt)
    except Exception as e:
        print(f"REMINDER EXTRACTION ERROR: {type(e).__name__}: {e}")
        return

    if not text or text.strip().upper() == "YOK":
        return

    data = {}
    for line in text.strip().splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().upper()] = value.strip()

    topic = data.get("KONU", "").strip()
    event_str = data.get("ETKINLIK_TARIHI", "").strip()
    remind_str = data.get("HATIRLATMA_TARIHI", "").strip()

    if not topic or not event_str or not remind_str:
        return

    try:
        event_at = datetime.strptime(event_str, "%Y-%m-%d").date()
        remind_at = datetime.strptime(remind_str, "%Y-%m-%d").date()
    except ValueError:
        # LLM bekleneni yazmadi (bosluklu/hatali format) - sessizce vazgec,
        # gecersiz bir hatirlatma olusturmaktan iyidir.
        return

    # SAGLAMLIK KONTROLLERI (LLM ciktisina korkoruce guvenmiyoruz):
    # - Gecmis bir tarih icin hatirlatma olusturma (bugun ya da sonrasi olmali).
    # - Hatirlatma, etkinlikten SONRAYA denk gelmemeli (mantik hatasi olur).
    if event_at < today:
        return
    if remind_at > event_at:
        remind_at = event_at
    if remind_at < today:
        remind_at = today

    # BULUNDU (kod incelemesi): kullanici ayni etkinlikten birden fazla
    # mesajda bahsederse ("persembe mac var, bilet almaliyim" ... sonra
    # ... "unutma persembe mac var") her ikisi de ayri ayri cikarilip
    # coklanan yerel bildirime yol aciyordu.
    if database.has_active_reminder_on_date(user_id, event_at.isoformat()):
        return

    database.add_reminder(user_id, topic, event_at.isoformat(), remind_at.isoformat())
