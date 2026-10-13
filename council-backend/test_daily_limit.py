import json, os, tempfile, unittest
import daily_limit as dl


class DailyLimit(unittest.TestCase):
    def setUp(self):
        self.p = os.path.join(tempfile.mkdtemp(), ".uploaded_today.json")
        os.environ.pop("AURA_MAX_DAILY", None)

    def test_ilk_video_izinli(self):
        self.assertTrue(dl.can_upload(self.p)[0])

    def test_ikinci_video_izinli(self):
        dl.record_upload(self.p, "a")
        ok, info = dl.can_upload(self.p)
        self.assertTrue(ok); self.assertEqual(info["count"], 1)

    def test_ucuncu_video_reddedilir(self):
        dl.record_upload(self.p, "a"); dl.record_upload(self.p, "b")
        self.assertFalse(dl.can_upload(self.p)[0])

    def test_force_sert_siniri_asamaz(self):
        dl.record_upload(self.p, "a"); dl.record_upload(self.p, "b")
        self.assertFalse(dl.can_upload(self.p, force=True)[0])

    def test_eski_bicim_1_sayilir(self):
        json.dump({"video_id": "x", "ts": "t"}, open(self.p, "w"))
        self.assertEqual(dl.read_info(self.p)["count"], 1)
        self.assertTrue(dl.can_upload(self.p)[0])

    def test_bozuk_dosya_1_sayilir(self):
        open(self.p, "w").write("{bozuk")
        self.assertEqual(dl.read_info(self.p)["count"], 1)

    def test_ayni_video_iki_kez_sayilmaz(self):
        dl.record_upload(self.p, "a"); dl.record_upload(self.p, "a")
        self.assertEqual(dl.read_info(self.p)["count"], 1)

    def test_env_siniri_yukseltemez(self):
        os.environ["AURA_MAX_DAILY"] = "5"
        dl.record_upload(self.p, "a"); dl.record_upload(self.p, "b")
        self.assertFalse(dl.can_upload(self.p)[0])

    def test_env_1e_indirebilir(self):
        os.environ["AURA_MAX_DAILY"] = "1"
        dl.record_upload(self.p, "a")
        self.assertFalse(dl.can_upload(self.p)[0])
        self.assertTrue(dl.can_upload(self.p, force=True)[0])


if __name__ == "__main__":
    unittest.main()
