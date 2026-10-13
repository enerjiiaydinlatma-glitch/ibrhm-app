"""YouTube video metadatasi: DIL SINYALI. Saf fonksiyonlar (googleapiclient'a bagimli degil; test edilebilir).

13 Ekim 2026 bulgusu: kanal Ingilizce yayinliyor ama (1) yukleme govdesinde defaultLanguage/defaultAudioLanguage HIC yoktu,
(2) 48 videoya Turkce altyazi eklenmisti, (3) izleyicilerin %100'u TR gorundu (7 Ekim, 800/800). Dil metadatasinin dagitima
etkisi DOGRULANMIS degildir; ama bedavadir ve 'bu video Ingilizce' bilgisini acikca verir.
Karar (sahip, 13 Ekim 2026): yalnizca Ingilizce.
"""
DIL = "en"


def video_snippet(title, description, tags=None, category_id="28", dil=DIL):
    """videos.insert 'snippet' govdesi. Dil alanlari HER ZAMAN yazilir."""
    return {"title": title, "description": description, "tags": tags or [], "categoryId": category_id,
            "defaultLanguage": dil, "defaultAudioLanguage": dil}


def dil_plani(videolar, dil=DIL):
    """videolar: [{'id','snippet':{...}}] (videos.list ciktisi). Dil alanlari eksik/farkli olanlari doner:
    [{'id','baslik','eski':(defaultLanguage, defaultAudioLanguage)}]. Zaten dogru olanlar listelenmez."""
    out = []
    for v in videolar:
        sn = v.get("snippet") or {}
        eski = (sn.get("defaultLanguage"), sn.get("defaultAudioLanguage"))
        if eski != (dil, dil):
            out.append({"id": v["id"], "baslik": sn.get("title", ""), "eski": eski})
    return out


def guncelleme_govdesi(video, dil=DIL):
    """videos.update icin govde. API title + categoryId ister; baslik/aciklama/etiketler MEVCUT degerlerle korunur
    (aksi halde bos birakilirsa SILINIR). Yalnizca dil alanlari degisir."""
    sn = video["snippet"]
    yeni = {"title": sn["title"], "categoryId": sn.get("categoryId", "28"),
            "description": sn.get("description", ""), "defaultLanguage": dil, "defaultAudioLanguage": dil}
    if sn.get("tags"):
        yeni["tags"] = sn["tags"]
    return {"id": video["id"], "snippet": yeni}
