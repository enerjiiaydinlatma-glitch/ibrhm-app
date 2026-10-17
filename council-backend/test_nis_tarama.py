import datetime
import unittest

import nis_tarama as nt


def s(i, baslik, izl, abone=1000, yorum=0, saatlik=1.0, sure=30):
    return {"id": f"v{i}", "baslik": baslik, "kanal": f"K{i}", "kanal_id": f"c{i}", "yas_saat": 100, "sure": sure, "izlenme": izl,
            "begeni": 0, "yorum": yorum, "saatlik": saatlik, "abone": abone, "abone_orani": round(izl / abone, 2) if abone else None,
            "begeni_orani": 0, "yorum_orani": 0, "ozellik": {}}


class OzellikTest(unittest.TestCase):
    def test_baslik_ozellikleri(self):
        f = nt.nis_ozellikleri("What if the sea rose 20 cm?")
        self.assertTrue(f["what_if"] and f["soru"] and f["sayi+birim"] and f["kisa(<=50)"])
        self.assertFalse(f["would_you"] or f["korku_kelimesi"])
        self.assertTrue(nt.nis_ozellikleri("Would you survive a flood?")["would_you"])
        self.assertTrue(nt.nis_ozellikleri("Would you survive a flood?")["korku_kelimesi"])
        self.assertFalse(nt.nis_ozellikleri("A calm walk")["what_if"])

    def test_konu_gruplari(self):
        sat = [s(1, "What if all the ice melted?", 500), s(2, "Moon base in 2030", 300), s(3, "Flying cars soon", 100),
               s(4, "Volcano erupts in your city", 50), s(5, "Random cooking tips", 10)]
        g = {r["konu"]: r for r in nt.konu_gruplari(sat)}
        self.assertEqual(g["deniz/buz/iklim"]["n"], 1)
        self.assertEqual(g["uzay/ay/mars"]["n"], 1)
        self.assertEqual(g["ucan araba/gelecek sehir"]["n"], 1)
        self.assertEqual(g["dogal afet"]["n"], 1)
        self.assertEqual(g["diger"]["n"], 1)

    def test_kalip_raporu_az_ornek_isaretler(self):
        sat = [s(i, "What if x?", 100 + i) for i in range(3)] + [s(10 + i, "Plain title", 10) for i in range(3)]
        r = {x["ozellik"]: x for x in nt.kalip_raporu(sat)}
        self.assertTrue(r["what_if"]["az_ornek"])
        self.assertEqual(r["what_if"]["n_var"], 3)

    def test_yorum_ozeti_metin_kopyalamaz(self):
        o = nt.yorum_ozeti(["I would move inland", "Is this real?", "nice", ""])
        self.assertEqual(o["n"], 3)
        self.assertAlmostEqual(o["soru_orani"], 0.33, places=2)
        self.assertAlmostEqual(o["kisisel_orani"], 0.33, places=2)
        self.assertEqual(nt.yorum_ozeti([]), {"n": 0})


class RaporTest(unittest.TestCase):
    def test_rapor_bolumleri_ve_bos_veri(self):
        sat = [s(i, "What if the sea rose 20 cm?" if i % 2 else "Moon base tour", 100 * (i + 1), abone=500, yorum=i) for i in range(10)]
        d = {"zaman": "2026-10-17T00:00:00", "gun": 90, "sorgular": ["q1"], "satirlar": sat}
        md = nt.rapor_md(d, {"v9": ["I would stay", "Why?"]}, simdi=datetime.date(2026, 10, 17))
        for baslik in ("## Özet", "## En çok izlenen 15", "## Küçük kanalda patlayanlar", "## Konu grupları", "## Başlık kalıpları",
                       "## Etkileşim", "## Sen doldur"):
            self.assertIn(baslik, md)
        self.assertIn("yön göstergesidir", md.lower().replace("YÖN", "yön"))
        self.assertIn("Yorum %", md)
        self.assertNotIn("Yorum‰", md)
        self.assertIn("Veri yok", nt.rapor_md({"zaman": "x", "gun": 90, "sorgular": [], "satirlar": []}))

    def test_ayri_onbellek_ai_haber_onbellegini_bozmaz(self):
        self.assertNotEqual(nt.CACHE, nt.va.CACHE)


class NisSetleriTest(unittest.TestCase):
    def test_nisler_ve_yollar(self):
        self.assertEqual(set(nt.NISLER), {"afet", "robot", "insan", "uzay_yeralti", "fizik"})
        for ad, q in nt.NISLER.items():
            self.assertEqual(len(q), 8, ad)
            self.assertIn(ad, nt.NIS_ADLARI)
        yollar = {nt.cache_yolu(a) for a in nt.NISLER} | {nt.va.CACHE}
        self.assertEqual(len(yollar), len(nt.NISLER) + 1)            # her nis ayri onbellek, AI-haber onbellegi ayri
        self.assertEqual(nt.cache_yolu("afet"), nt.CACHE)

    def test_yeni_konu_kovalari(self):
        sat = [s(1, "What if robots ran the world?", 100), s(2, "Would you put a chip in your brain?", 90),
               s(3, "A city under the ocean", 80), s(4, "What if gravity doubled?", 70)]
        g = {r["konu"]: r["n"] for r in nt.konu_gruplari(sat)}
        self.assertEqual(g["robot/makine"], 1)
        self.assertEqual(g["beyin/cip/cyborg"], 1)
        self.assertEqual(g["yer alti/su alti sehir"], 1)
        self.assertEqual(g["fizik/absurt"], 1)

    def test_karsilastirma(self):
        kucuk = [s(i, "x", 20000, abone=500) for i in range(3)]
        buyuk = [s(10 + i, "y", 900000, abone=5_000_000) for i in range(3)]
        md = nt.karsilastirma_md({"robot": {"satirlar": kucuk}, "fizik": {"satirlar": buyuk}, "insan": {"satirlar": []}})
        self.assertLess(md.index("robotlar"), md.index("fizik"))     # kucuk kanalda >=10k fazla olan once
        self.assertIn("hayatta kalma", md)
        self.assertIn("| **3** |", md)


class YorumCekTest(unittest.TestCase):
    class _Yt:
        def __init__(self, tablo):
            self.tablo = tablo

        def commentThreads(self):
            tablo = self.tablo

            class L:
                def list(self_, **kw):
                    class E:
                        def execute(self__):
                            if kw["videoId"] not in tablo:
                                raise RuntimeError("commentsDisabled")
                            return {"items": [{"snippet": {"topLevelComment": {"snippet": {"textDisplay": t}}}} for t in tablo[kw["videoId"]]]}
                    return E()
            return L()

    def test_kapali_yorum_atlanir(self):
        sat = [s(1, "a", 900), s(2, "b", 500)]
        out = nt.yorumlari_cek(self._Yt({"v2": ["hello"]}), sat)
        self.assertEqual(out, {"v2": ["hello"]})


if __name__ == "__main__":
    unittest.main()
