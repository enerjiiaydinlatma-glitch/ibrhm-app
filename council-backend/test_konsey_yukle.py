import datetime
import json
import os
import tempfile
import unittest

import daily_limit
import konsey_yukle as ky

BUGUN = datetime.date(2026, 10, 14)


class YukleTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.video = os.path.join(self.d, "v.mp4")
        open(self.video, "wb").write(b"x")
        self.meta = {"title": "Are Movie Subscriptions Worth It? #Shorts", "description": "Are 3 movie subscriptions too many?\n\n#Shorts",
                     "tags": ["a"], "file": self.video, "seconds": 32, "sabit_yorum": "Team Alpha or Team Beta? Vote below.",
                     "script": "Are 3 movie subscriptions too many? Three bills, one show a month.", "konu": "Are subscriptions worth it?"}
        self.kayit = os.path.join(self.d, "kayit.jsonl")
        self.cagri = []

    def upload(self, f, t, d, tags, publish_at=None):
        self.cagri.append((f, t, d, tags))
        self.publish_at = publish_at
        return "VID1"

    def calistir(self, onay=True, yayin_utc=None):
        return ky.yukle(self.meta, self.upload, lambda m: onay, bugun=BUGUN, engine=self.d, kayit_yolu=self.kayit, yayin_utc=yayin_utc)

    def test_zamanli_yukleme_publish_at_gecer_ve_kayda_yazar(self):
        vid, msg = self.calistir(yayin_utc="2026-10-14T23:30:00Z")
        self.assertEqual(vid, "VID1")
        self.assertEqual(self.publish_at, "2026-10-14T23:30:00Z")
        satir = json.loads(open(self.kayit, encoding="utf-8").read().strip())
        self.assertEqual((satir["gizlilik"], satir["yayin_utc"]), ("scheduled", "2026-10-14T23:30:00Z"))

    def test_zamansiz_yukleme_publish_at_yok(self):
        self.calistir()
        self.assertIsNone(self.publish_at)

    def test_zamanla_utc_donusumu_ve_sinirlar(self):
        simdi = datetime.datetime(2026, 10, 14, 15, 0)            # UTC
        self.assertEqual(ky.zamanla_utc("2026-10-15 02:30", simdi), "2026-10-14T23:30:00Z")   # TR 02:30 = UTC 23:30
        with self.assertRaises(ValueError):
            ky.zamanla_utc("2026-10-14 18:05", simdi)             # TR 18:05 = UTC 15:05, 10 dk'dan yakin
        with self.assertRaises(ValueError):
            ky.zamanla_utc("2026-10-10 12:00", simdi)             # gecmis
        with self.assertRaises(ValueError):
            ky.zamanla_utc("2026-12-30 12:00", simdi)             # 30 gunden uzak
        with self.assertRaises(ValueError):
            ky.zamanla_utc("yarin aksam", simdi)                  # bicim

    def test_basarili_yukleme_sayaci_ve_kaydi_yazar(self):
        vid, msg = self.calistir()
        self.assertEqual((vid, msg), ("VID1", []))
        self.assertEqual(len(self.cagri), 1)
        self.assertEqual(self.cagri[0][3][:2], ["Sign Council", "AI debate"])   # meta'daki eski etiket ("a") kullanilmaz
        self.assertNotIn("a", self.cagri[0][3])
        info = daily_limit.read_info(ky.gunluk_dosya(BUGUN, self.d))
        self.assertEqual(info["count"], 1)
        satir = json.loads(open(self.kayit, encoding="utf-8").read().strip())
        self.assertEqual((satir["format"], satir["gizlilik"], satir["video_id"]), ("konsey", "private", "VID1"))
        self.assertEqual(satir["kanca"], "Are 3 movie subscriptions too many?")
        self.assertEqual(satir["kanca_tipi"], "soru")
        self.assertEqual(satir["konu"], "Are subscriptions worth it?")

    def test_onay_yoksa_yuklenmez(self):
        vid, msg = self.calistir(onay=False)
        self.assertIsNone(vid)
        self.assertEqual(self.cagri, [])
        self.assertEqual(daily_limit.read_info(ky.gunluk_dosya(BUGUN, self.d))["count"], 0)

    def test_gunluk_sinirda_yuklenmez(self):
        gf = ky.gunluk_dosya(BUGUN, self.d)
        os.makedirs(os.path.dirname(gf))
        daily_limit.record_upload(gf, "A")
        daily_limit.record_upload(gf, "B")
        vid, msg = self.calistir()
        self.assertIsNone(vid)
        self.assertTrue(any("sinira" in m for m in msg))
        self.assertEqual(self.cagri, [])

    def test_ikinci_yukleme_olur_ucuncu_olmaz(self):
        self.assertEqual(self.calistir()[0], "VID1")
        gf = ky.gunluk_dosya(BUGUN, self.d)
        daily_limit.record_upload(gf, "VID2")
        self.assertIsNone(self.calistir()[0])

    def test_konsey_olmayan_meta_reddedilir(self):
        del self.meta["sabit_yorum"]
        self.assertIsNone(self.calistir()[0])
        self.assertEqual(self.cagri, [])

    def test_eksik_dosya_baslik_reddedilir(self):
        os.remove(self.video)
        self.assertIsNone(self.calistir()[0])
        self.meta["file"] = self.video
        open(self.video, "wb").write(b"x")
        self.meta["title"] = ""
        self.assertIsNone(self.calistir()[0])

    def test_son_meta_senaryo_kaydini_atlar(self):
        a = os.path.join(self.d, "a.json")
        s = os.path.join(self.d, "konsey_son_senaryo.json")
        open(a, "w").write("{}")
        open(s, "w").write("{}")
        os.utime(a, (1, 1))
        os.utime(s, (999999999, 999999999))     # senaryo kaydi daha yeni olsa da secilmez
        self.assertEqual(ky.son_meta(self.d), a)
        self.assertIsNone(ky.son_meta(tempfile.mkdtemp()))

    def test_public_secenegi_yok(self):
        import inspect
        src = inspect.getsource(ky)
        self.assertIn('privacy_status="private"', src)
        self.assertNotIn('"public"', src.replace("'public/unlisted", ""))


class GunTest(unittest.TestCase):
    def test_yukleme_gunleri(self):
        yol = os.path.join(tempfile.mkdtemp(), "k.jsonl")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(json.dumps({"ts": "2026-10-14T14:17:27"}) + "\nbozuk\n" + json.dumps({"ts": "2026-10-15T09:00:00"}) + "\n"
                    + json.dumps({"ts": "yanlis"}) + "\n" + json.dumps({"ts": "2026-10-14T20:00:00"}) + "\n")
        self.assertEqual(ky.yukleme_gunleri(yol), {"20261014", "20261015"})
        self.assertEqual(ky.yukleme_gunleri(os.path.join(tempfile.mkdtemp(), "yok")), set())


if __name__ == "__main__":
    unittest.main()
