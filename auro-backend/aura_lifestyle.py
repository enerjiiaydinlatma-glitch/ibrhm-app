"""
Aura Lifestyle
==============
Aura'nin "yasama yonlendiren" tarafi. Bu modul LLM'e ne soyleyecegini
degil, neyi fark etmesi gerektigini soyler - hava durumu, uzun suredir
bahsedilmeyen bir rutin, ya da takip edilmemis bir gundem gibi sinyaller
uretir. Bu sinyaller aura_brain.build_system_instruction() tarafindan
sistem promptuna birer "YASAM IPUCU" cumlesi olarak eklenir.

Kategori sozlesmesi (aura_memory'deki serbest metin category kolonunda):
- "routine"        -> aliskanliklar (kahve, yuruyus, uyku ...)
- "upcoming_event" -> takip edilecek gundem (toplanti, sinav, randevu ...)
"""

from datetime import datetime, timezone

import httpx

import aura_memory

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather_code gruplari (Open-Meteo)
_CLEAR_CODES = {0, 1}
_RAIN_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
_SNOW_CODES = {71, 73, 75, 77, 85, 86}

ROUTINE_CATEGORY = "routine"
UPCOMING_EVENT_CATEGORY = "upcoming_event"
PATTERN_INSIGHT_CATEGORY = "pattern_insight"
_ROUTINE_GAP_HOURS = 20
_INSIGHT_COOLDOWN_DAYS = 14


def _parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T")).replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def get_weather_nudge(user: dict) -> str:
    if not user.get("weather_enabled"):
        return ""

    lat = user.get("location_lat")
    lon = user.get("location_lon")

    if lat is None or lon is None:
        return ""

    try:
        response = httpx.get(
            OPEN_METEO_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code",
            },
            timeout=5,
        )
        response.raise_for_status()
        current = response.json().get("current", {})
        temp = current.get("temperature_2m")
        code = current.get("weather_code")
    except Exception:
        return ""

    if temp is None:
        return ""

    if code in _SNOW_CODES:
        return (
            f"YASAM IPUCU: Disarida kar var ({temp:.0f} derece) - "
            "kalin giyinmesini hatirlatabilirsin."
        )
    if code in _RAIN_CODES:
        return (
            f"YASAM IPUCU: Disarida yagmur var ({temp:.0f} derece) - "
            "yanina semsiye almasini onerebilirsin."
        )
    if code in _CLEAR_CODES and temp >= 18:
        return (
            f"YASAM IPUCU: Hava acik ve {temp:.0f} derece - "
            "disari cikmasini, biraz yurumesini onerebilirsin."
        )
    if temp <= 5:
        return (
            f"YASAM IPUCU: Hava cok soguk ({temp:.0f} derece) - "
            "kalin giyinmesini hatirlatabilirsin."
        )
    return ""


def get_routine_nudge(user_id: int) -> str:
    memories = aura_memory.get_memories(user_id)
    routines = [m for m in memories if m.get("category") == ROUTINE_CATEGORY]

    if not routines:
        return ""

    now = datetime.now(timezone.utc)
    stalest = None
    stalest_hours = -1.0

    for memory in routines:
        seen = _parse_timestamp(memory.get("updated_at"))
        if not seen:
            continue
        hours = (now - seen).total_seconds() / 3600
        if hours > stalest_hours:
            stalest_hours = hours
            stalest = memory

    if stalest and stalest_hours >= _ROUTINE_GAP_HOURS:
        return (
            "YASAM IPUCU: Kullanicinin '" + stalest["memory_value"] + "' "
            "rutininden bir suredir bahsedilmedi - dogal bir sekilde "
            "sorabilir, hatirlatabilirsin."
        )
    return ""


def get_followup_nudge(user_id: int) -> str:
    memories = aura_memory.get_memories(user_id)
    events = [
        m
        for m in memories
        if m.get("category") == UPCOMING_EVENT_CATEGORY and not m.get("last_used_at")
    ]

    if not events:
        return ""

    event = events[0]

    try:
        aura_memory.mark_memory_used(user_id, event["id"])
    except Exception:
        pass

    return (
        "YASAM IPUCU: Kullanicinin '" + event["memory_value"] + "' ile ilgili "
        "bir gundemi vardi - nasil gectigini sorabilirsin."
    )


def get_insight_nudge(user_id: int) -> str:
    """
    Kor nokta/celiski farkindaligi icin soguma sureli nudge. Son
    _INSIGHT_COOLDOWN_DAYS icinde herhangi bir pattern_insight zaten
    kullanildiysa, yenisi olsa bile GOSTERILMEZ - "her firsatta analiz
    ediyor" hissini onleyen asil mekanizma burasi.
    """
    memories = aura_memory.get_memories(user_id)
    insights = [m for m in memories if m.get("category") == PATTERN_INSIGHT_CATEGORY]

    if not insights:
        return ""

    now = datetime.now(timezone.utc)

    used_timestamps = [
        ts
        for ts in (_parse_timestamp(m.get("last_used_at")) for m in insights)
        if ts is not None
    ]
    if used_timestamps:
        hours_since_last_use = (now - max(used_timestamps)).total_seconds() / 3600
        if hours_since_last_use < _INSIGHT_COOLDOWN_DAYS * 24:
            return ""

    unused = [m for m in insights if not m.get("last_used_at")]
    if not unused:
        return ""

    insight = unused[0]

    try:
        aura_memory.mark_memory_used(user_id, insight["id"])
    except Exception:
        pass

    return "ORUNTU FARKINDALIGI: " + insight["memory_value"]


def get_lifestyle_nudges(user: dict) -> str:
    parts = [
        get_weather_nudge(user),
        get_routine_nudge(user["id"]),
        get_followup_nudge(user["id"]),
        get_insight_nudge(user["id"]),
    ]
    return " ".join(p for p in parts if p)
