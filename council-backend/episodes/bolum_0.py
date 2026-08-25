"""
Bolum 0 - pilot. Konu: "Ego ve bencillik". Katilimcilar: Aura + Alpha +
Gamma (Faz 1, Sign Council Rundown Segment 11). Onaylanan taslak script
sabit metin olarak degil, buradaki soz sirasina gore CANLI API
cagrilariyla uretilir - asagidaki TURN_PLAN sadece kimin ne zaman
konusacagini ve ne yapmasi gerektigini tanimlar.
"""

TOPIC = (
    "Dunyada herkese yetecek kadar kaynak varken, insanlik neden hala "
    "sahiplenme, rekabet ve ego uzerinden hareket ediyor?"
)

TURN_PLAN = [
    {
        "speaker": "aura",
        "directive": "Bolumu ac. Konuyu iki cumlede ortaya koy ve sozu Alpha'ya ver.",
    },
    {
        "speaker": "alpha",
        "directive": "Konuyu kendi uzmanlik alanindan bagimsiz analiz et.",
    },
    {
        "speaker": "gamma",
        "directive": (
            "Konuyu kendi uzmanlik alanindan bagimsiz analiz et. Alpha'nin "
            "ne dedigini bilmiyorsun."
        ),
    },
    {
        "speaker": "aura",
        "directive": (
            "Alpha'nin soylediklerine karsi Gamma'nin gorusunu sor - "
            "aralarindaki gerilimi acikca ortaya koy."
        ),
    },
    {
        "speaker": "alpha",
        "directive": "Gamma'nin itirazina kisa bir cevap ver.",
    },
    {
        "speaker": "gamma",
        "directive": "Alpha'nin cevabina kisa bir karsilik ver.",
    },
    {
        "speaker": "aura",
        "directive": (
            "Ikisinin de nerede hakli, nerede eksik oldugunu belirt ve "
            "bolumu somut bir sentezle kapat."
        ),
    },
]
