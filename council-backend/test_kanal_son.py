import datetime
import unittest

import kanal_son

NOW = datetime.datetime(2026, 10, 11, 12, 0, 0)


def v(i, gun, views, privacy="public", likes=0, comments=0):
    return {"id": i, "title": f"video {i}", "published": f"2026-10-{gun:02d}T12:00:00Z", "views": views,
            "likes": likes, "comments": comments, "privacy": privacy}


class Karne(unittest.TestCase):
    def test_medyan_yalniz_olgun_herkese_acik(self):
        vids = [v("a", 1, 10), v("b", 2, 20), v("c", 3, 100), v("yeni", 10, 999), v("ozel", 2, 5000, "private")]
        k = kanal_son.karne(vids, NOW)
        self.assertEqual(k["olgun_video"], 3)
        self.assertEqual(k["medyan_izlenme"], 20)

    def test_oran_ve_yeni_video_oran_almaz(self):
        vids = [v("a", 1, 10), v("b", 2, 20), v("c", 3, 100), v("yeni", 10, 999)]
        satir = {s["id"]: s for s in kanal_son.karne(vids, NOW)["satirlar"]}
        self.assertEqual(satir["c"]["medyana_oran"], 5.0)
        self.assertIsNone(satir["yeni"]["medyana_oran"])  # henuz 72 saat dolmadi

    def test_ozel_video_oran_almaz_ve_en_yeni_basta(self):
        vids = [v("a", 1, 10), v("ozel", 2, 5, "private"), v("b", 3, 30)]
        k = kanal_son.karne(vids, NOW)
        self.assertEqual([s["id"] for s in k["satirlar"]], ["b", "ozel", "a"])
        self.assertIsNone([s for s in k["satirlar"] if s["id"] == "ozel"][0]["medyana_oran"])

    def test_bos_ve_bozuk_tarih_dayanikli(self):
        self.assertEqual(kanal_son.karne([], NOW)["satirlar"], [])
        bozuk = {"id": "x", "title": "t", "published": "??", "views": 3, "likes": 0, "comments": 0, "privacy": "public"}
        self.assertIsNone(kanal_son.karne([bozuk], NOW)["satirlar"][0]["yas_saat"])


if __name__ == "__main__":
    unittest.main()
