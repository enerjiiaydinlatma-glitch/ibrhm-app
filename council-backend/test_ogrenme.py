import datetime
import unittest

import ogrenme
import sutun

BUGUN = datetime.date(2026, 10, 8)


def v(i, title, views, tarih="2026-09-20", retention=20.0, subs=0, comments=0, hashtags=None):
    return {"id": f"v{i}", "title": title, "published": tarih, "views": views, "likes": 0, "comments": comments,
            "shares": 0, "retention": retention, "subs": subs, "hashtags": hashtags or ["#Shorts", "#SignCouncil"]}


class KarneTest(unittest.TestCase):
    def liste(self):
        out = []
        for i in range(6):   # sayili baslik: yuksek izlenme
            out.append(v(i, f"{i + 3} systems breached in one week", 200 + i * 10, subs=1, hashtags=["#Shorts", "#SignCouncil", "#AIsafety"]))
        for i in range(6):   # sayisiz: dusuk
            out.append(v(10 + i, "What is a control point in AI", 40 + i, hashtags=["#Shorts", "#SignCouncil", "#Ekonomi"]))
        out.append(v(99, "Brand new video today", 5, tarih="2026-10-08"))   # taze: sayilmaz
        return out

    def test_medyan_ve_gruplar(self):
        k = ogrenme.karne(self.liste(), BUGUN)
        self.assertEqual(k["genel"]["n"], 12)                       # taze video disarida
        sayi = {r["ad"]: r for r in k["bolumler"]["sayi"]}
        self.assertEqual(sayi["başlıkta sayı var"]["n"], 6)
        self.assertGreater(sayi["başlıkta sayı var"]["med_izlenme"], sayi["başlıkta sayı yok"]["med_izlenme"])
        self.assertEqual(sayi["başlıkta sayı var"]["guven"], "yön")  # n=6 -> 'yon'

    def test_marka_etiketleri_karsilastirmaya_girmez(self):
        k = ogrenme.karne(self.liste(), BUGUN)
        adlar = {r["ad"].lower() for r in k["bolumler"]["hashtag"]}
        self.assertNotIn("#shorts", adlar)
        self.assertNotIn("#signcouncil", adlar)
        self.assertIn("#aisafety", adlar)

    def test_oneriler_yalniz_yeterli_ornek_ve_belirgin_fark(self):
        k = ogrenme.karne(self.liste(), BUGUN)
        self.assertTrue(any("sayı var" in o["ad"] for o in k["oneriler"]))
        kucuk = ogrenme.karne(self.liste()[:3], BUGUN)       # n<5: oneri yok
        self.assertEqual(kucuk["oneriler"], [])

    def test_hashtag_onerisi_marka_sabit_ve_kanitli(self):
        h = ogrenme.hashtag_onerisi(self.liste(), now=BUGUN)
        self.assertEqual(h["hashtagler"][0], "#Shorts")
        self.assertEqual(h["hashtagler"][-1], "#SignCouncil")
        self.assertIn("#AIsafety", h["hashtagler"])
        self.assertTrue(all("n=" in d for d in h["dayanak"]))

    def test_tek_viral_video_medyani_bozmaz(self):
        vs = [v(i, "Normal video title here today", 10) for i in range(9)] + [v(50, "Viral one video here", 5000)]
        g = ogrenme.karne(vs, BUGUN)["genel"]
        self.assertEqual(g["med_izlenme"], 10)


class KanalTrackerTest(unittest.TestCase):
    def test_donusum_ve_sutun_istatistigi(self):
        t = {"videos": [v(1, "Council Case #1: Should I tell my boss", 300, retention=60, subs=2, comments=3),
                        v(2, "Council Case #2: Should I quit", 100, retention=40, subs=0, comments=1)]}
        kanal = ogrenme.kanal_tracker(t)
        self.assertTrue(kanal["ok"])
        tablo = sutun.istatistik(kanal["videolar"], kayit={}, now=datetime.datetime(2026, 10, 8, 12))
        ik = tablo["ikilem"]
        self.assertEqual(ik["deneme"], 2)
        self.assertEqual(ik["ort_abone"], 1.0)
        self.assertEqual(ik["med_tutma"], 50)                 # gercek medyan: (60+40)/2
        self.assertEqual(ik["med_goreli"], 1.0)               # 300 ve 100 / genel medyan 200 -> 1.5 ve 0.5 -> medyan 1.0
        self.assertEqual(ik["skor"], 100 + 20 * 2 + 30 * 1.0)

    def test_bos_tracker(self):
        self.assertFalse(ogrenme.kanal_tracker({})["ok"])


if __name__ == "__main__":
    unittest.main()


class ZamanEtkisiTest(unittest.TestCase):
    """Erken donemde (Agustos) tum videolar cok izlendi; sayili basliklarin hepsi o donemde yayinlanmis.
    Ham medyan 'sayi 100 kat' der; zamana gore duzeltince fark kalmaz."""

    def liste(self):
        out = []
        for i in range(6):      # Agustos: sayili
            out.append(v(i, f"{i + 2} systems breached this week", 1000, tarih=f"2026-08-{10 + i}"))
        for i in range(6):      # Agustos: sayisiz (ayni donem, ayni izlenme)
            out.append(v(20 + i, "Why is the company quietly acquiring a rival", 1000, tarih=f"2026-08-{10 + i}"))
        for i in range(20):     # Ekim: sayisiz, dusuk izlenme
            out.append(v(40 + i, "Why did the vendor change its policy again", 10, tarih=f"2026-10-{1 + (i % 5):02d}"))
        return out

    def test_ham_medyan_yaniltir_goreli_yanilmaz(self):
        k = ogrenme.karne(self.liste(), BUGUN)
        sayi = {r["ad"]: r for r in k["bolumler"]["sayi"]}
        var, yok = sayi["başlıkta sayı var"], sayi["başlıkta sayı yok"]
        self.assertGreater(var["med_izlenme"] / yok["med_izlenme"], 50)       # ham: 100 kat
        self.assertAlmostEqual(var["med_goreli"], 1.0, delta=0.15)            # dönemine göre: tipik
        self.assertFalse(any("sayı var" in o["ad"] for o in k["oneriler"]))   # sahte oneri uretilmez

    def test_goreli_komsu_yoksa_genel_medyan(self):
        g = ogrenme.goreli([v(1, "a long enough title here", 100, tarih="2026-01-01"), v(2, "another long title here", 300, tarih="2026-06-01")])
        self.assertIsNotNone(g[0]["rel"])

    def test_olgun_gun_esigi(self):
        liste = [v(i, f"{i} systems breached title", 100, tarih="2026-10-06") for i in range(8)]   # 2 gunluk
        self.assertEqual(ogrenme.karne(liste, BUGUN)["genel"]["n"], 0)
