"""
Ajan basina ElevenLabs ses kimligi (voice_id).

auro-backend/main.py'deki VOICE_IDS ile ayni ElevenLabs hesabini
kullaniyoruz (ses bir API kimlik bilgisi, kullanici verisi degil - bu
paylasim izolasyon ilkesini bozmaz). Su an sadece 2 ses biliniyor
(uygulamadaki erkek/kadin sesi); Beta/Gamma/Delta icin ElevenLabs
kutuphanenizden kendi sesinizi secip asagidaki bos degerleri doldurun.
"""

VOICE_IDS = {
    "aura": "iLcCq17FevxNYSk6Hgi7",  # mevcut app Aura sesi - marka tutarliligi
    "alpha": "9OXwpKJw7rW6WI0ORNzm",  # mevcut erkek ses
    "beta": "N2lVS1w4EtoT3dr4eOWO",  # Callum - Husky Trickster (asi/keskin ton)
    "gamma": "pqHfZKP75CvOlQylNhV4",  # Bill - Wise, Mature, Balanced (dusunceli/olgun)
    "delta": "Eoull6RSQg662htO64SQ",  # hesapta hazir duran, gercek Turkce ses
}
