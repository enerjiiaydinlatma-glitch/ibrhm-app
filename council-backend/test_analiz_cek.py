import datetime
import os
import tempfile
import unittest

import analiz_cek as ac

YANIT = {"columnHeaders": [{"name": "video"}, {"name": "views"}, {"name": "averageViewPercentage"}, {"name": "subscribersGained"}, {"name": "likes"}, {"name": "comments"}],
         "rows": [["A", 38, 41.5, 0, 1, 0], ["B", 5, 20.0, 0, 0, 0], ["C", 223, 36.5, 1, 3, 1]]}


class SaflarTest(unittest.TestCase):
    def test_satirlar_basliklarla_eslesir(self):
        s = ac.satirlar(YANIT)
        self.assertEqual(s[0], {"video": "A", "views": 38, "averageViewPercentage": 41.5, "subscribersGained": 0, "likes": 1, "comments": 0})
        self.assertEqual(ac.satirlar({}), [])
        self.assertEqual(ac.satirlar({"columnHeaders": [{"name": "x"}]}), [])

    def test_medyan_ve_kategori_gruplari(self):
        self.assertEqual(ac.medyan([1, 5, None, 3]), 3)
        self.assertIsNone(ac.medyan([None]))
        kayit = {"A": {"kategori": "robot"}, "B": {"kategori": "afet"}}
        g = ac.kategori_gruplari(ac.satirlar(YANIT), kayit)
        self.assertEqual(g["robot"]["medyan_goruntuleme"], 38)
        self.assertEqual(g["afet"]["n"], 1)
        self.assertEqual(g["diger"]["medyan_goruntuleme"], 223)      # kayitta olmayan eski video

    def test_ozet_metni(self):
        gunluk = [{"day": "2026-10-01", "views": 10, "estimatedMinutesWatched": 6, "subscribersGained": 0},
                  {"day": "2026-10-02", "views": 240, "estimatedMinutesWatched": 30, "subscribersGained": 1}]
        kaynak = [{"insightTrafficSourceType": "SHORTS", "views": 70}, {"insightTrafficSourceType": "YT_SEARCH", "views": 30}]
        m = ac.ozet_metni(gunluk, ac.satirlar(YANIT), kaynak, {"C": "Haber basligi"}, {"A": {"kategori": "robot", "baslik": "Robot video"}})
        self.assertIn("TOPLAM: 250 goruntuleme", m)
        self.assertIn("+1 abone", m)
        self.assertIn("SHORTS %70.0", m)
        self.assertIn("Haber basligi", m)
        self.assertIn("Robot video", m)                              # baslik yoksa kayittan
        self.assertIn("robot: n=1", m)

    def test_csv_yaz_ve_tarih(self):
        yol = os.path.join(tempfile.mkdtemp(), "alt", "x.csv")
        self.assertTrue(ac.csv_yaz(yol, [{"a": 1, "b": 2}, {"a": 3, "c": 4}]))
        self.assertIn("a,b,c", open(yol, encoding="utf-8").read().splitlines()[0])
        self.assertFalse(ac.csv_yaz(yol, []))
        self.assertEqual(ac.tarih_araligi(28, bugun=datetime.date(2026, 10, 25)), ("2026-09-27", "2026-10-24"))
        self.assertEqual(ac.tarih_araligi(60, "2026-08-27", "2026-09-23"), ("2026-08-27", "2026-09-23"))

    def test_yalniz_okuma_kapsami(self):
        for s in ac.SCOPES:
            self.assertTrue(s.endswith(".readonly"), s)


if __name__ == "__main__":
    unittest.main()
