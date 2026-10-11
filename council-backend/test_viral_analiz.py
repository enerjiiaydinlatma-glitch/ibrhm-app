import datetime
import unittest

import viral_analiz as va

NOW = datetime.datetime(2026, 10, 11, 12, 0, 0)


def vid(i, baslik, views, sure="PT45S", saat_once=24, likes=10, yorum=2, kanal="k1"):
    t = (NOW - datetime.timedelta(hours=saat_once)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"id": i, "snippet": {"title": baslik, "publishedAt": t, "channelId": kanal, "channelTitle": "Kanal " + kanal},
            "statistics": {"viewCount": str(views), "likeCount": str(likes), "commentCount": str(yorum)},
            "contentDetails": {"duration": sure}}


class Saf(unittest.TestCase):
    def test_sure(self):
        self.assertEqual(va.sure_saniye("PT45S"), 45)
        self.assertEqual(va.sure_saniye("PT1M5S"), 65)
        self.assertEqual(va.sure_saniye("PT2M"), 120)
        self.assertEqual(va.sure_saniye("PT1H"), 3600)
        self.assertIsNone(va.sure_saniye("bozuk"))
        self.assertIsNone(va.sure_saniye(None))

    def test_baslik_ozellikleri(self):
        o = va.baslik_ozellikleri("Why is Nvidia buying Hugging Face?")
        self.assertTrue(o["soru"])
        self.assertFalse(o["sayi"])
        o = va.baslik_ozellikleri("Anthropic jumps to #1: 3 big wins")
        self.assertTrue(o["sayi"] and o["iki_nokta"] and o["siralama"])
        self.assertTrue(va.baslik_ozellikleri("OPENAI JUST CHANGED EVERYTHING")["cok_buyuk_harf"])
        self.assertTrue(va.baslik_ozellikleri("Short one")["kisa_baslik"])
        self.assertFalse(va.baslik_ozellikleri("x" * 60)["kisa_baslik"])

    def test_satir_shorts_filtresi_ve_oranlar(self):
        s = va.satir_hazirla(vid("a", "Hello 1", 1000, saat_once=10), 500, NOW)
        self.assertEqual(s["izlenme"], 1000)
        self.assertEqual(s["saatlik"], 100.0)
        self.assertEqual(s["abone_orani"], 2.0)
        self.assertEqual(s["begeni_orani"], 1.0)
        self.assertIsNone(va.satir_hazirla(vid("b", "uzun", 5, sure="PT5M"), 10, NOW))  # Shorts degil
        self.assertIsNone(va.satir_hazirla(vid("c", "bozuk", 5, sure="x"), 10, NOW))
        eksik = {"id": "d", "snippet": {"title": "t"}, "statistics": {}, "contentDetails": {"duration": "PT10S"}}
        self.assertIsNone(va.satir_hazirla(eksik, 1, NOW))  # publishedAt yok

    def test_abone_gizli_oran_yok(self):
        s = va.satir_hazirla(vid("a", "t", 100), None, NOW)
        self.assertIsNone(s["abone_orani"])

    def test_kalip_raporu_az_ornek_isaretlenir(self):
        rows = [va.satir_hazirla(vid(str(i), "Why is X? %d" % i if i < 6 else "plain title", 100 * (i + 1)), 100, NOW) for i in range(12)]
        r = {x["ozellik"]: x for x in va.kalip_raporu(rows)}
        self.assertEqual(r["soru"]["n_var"], 6)
        self.assertFalse(r["soru"]["az_ornek"])
        self.assertTrue(r["hashtag"]["az_ornek"])  # hic yok -> az ornek
        self.assertEqual(va.kalip_raporu([]), [])

    def test_ozet(self):
        rows = [va.satir_hazirla(vid(str(i), "t", v), 1, NOW) for i, v in enumerate([10, 20, 300])]
        o = va.ozet(rows)
        self.assertEqual((o["video"], o["medyan_izlenme"], o["en_cok"]), (3, 20, 300))
        self.assertEqual(va.ozet([]), {"video": 0})


if __name__ == "__main__":
    unittest.main()
