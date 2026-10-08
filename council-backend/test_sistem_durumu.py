import datetime, json, os, tempfile, time, unittest
import sistem_durumu as sd


def mk(base, rel, content="x", age_days=0):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").write(content)
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(p, (t, t))
    return p


class Temizlik(unittest.TestCase):
    def setUp(self):
        self.b = tempfile.mkdtemp()
        b = self.b
        # silinebilir adaylar
        mk(b, "__pycache__/x.pyc")
        mk(b, "assets/thumbnails/episode_old_A.png", age_days=20)
        mk(b, "assets/thumbnails/episode_new_A.png", age_days=1)
        mk(b, "_daily_auto_20260801.log", age_days=40)
        mk(b, "_daily_auto_20261008.log", age_days=0)
        mk(b, "_engine/kaynak_old.json", age_days=30)
        self.eski = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
        self.yeni = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        mk(b, f"_engine/{self.eski}/plan.json", age_days=60)
        mk(b, f"_engine/{self.yeni}/plan.json", age_days=1)
        mk(b, "output/shorts/topic/00_frame_base.png")
        mk(b, "output/shorts/topic/00.mp3")
        mk(b, "output/shorts/topic/final-video.mp4")
        # korunacaklar
        for rel in ("_engine/predictions.json", "_engine/mission_token.txt", "_engine/operator_rules.md", "youtube_token.json",
                    ".voice_key", "REVIEW_MODE", "aura_engine.py", "daily_auto.bat", "receipts/r.json", "analysis/a.md",
                    "_engine/kaynak_son.txt", "x.bak.py"):
            mk(b, rel, age_days=90)
        mk(b, "eski.bak", age_days=90)

    def names(self, res):
        return {os.path.relpath(p, self.b).replace("\\", "/") for items in res.values() for p in items}

    def test_adaylar_dogru(self):
        n = self.names(sd.candidates(self.b))
        for beklenen in ("__pycache__/x.pyc", "assets/thumbnails/episode_old_A.png", "_daily_auto_20260801.log",
                         "_engine/kaynak_old.json", f"_engine/{self.eski}", "output/shorts/topic/00_frame_base.png",
                         "output/shorts/topic/00.mp3", "eski.bak"):
            self.assertIn(beklenen, n)

    def test_korunanlar_aday_degil(self):
        n = self.names(sd.candidates(self.b))
        for korunan in ("assets/thumbnails/episode_new_A.png", "_daily_auto_20261008.log", f"_engine/{self.yeni}",
                        "output/shorts/topic/final-video.mp4", "_engine/predictions.json", "_engine/mission_token.txt",
                        "_engine/operator_rules.md", "youtube_token.json", ".voice_key", "REVIEW_MODE", "aura_engine.py",
                        "daily_auto.bat", "receipts/r.json", "analysis/a.md", "_engine/kaynak_son.txt", "x.bak.py"):
            self.assertNotIn(korunan, n)

    def test_tasi_ve_geri_al(self):
        items = [p for v in sd.candidates(self.b).values() for p in v]
        stamp, cnt = sd.move_to_archive(items, self.b, stamp="T1")
        self.assertEqual(cnt, len(items))
        self.assertFalse(os.path.exists(os.path.join(self.b, "eski.bak")))
        self.assertTrue(os.path.exists(os.path.join(self.b, "_arsiv", "T1", "eski.bak")))
        self.assertTrue(os.path.exists(os.path.join(self.b, "aura_engine.py")))
        n = sd.restore("T1", self.b)
        self.assertEqual(n, cnt)
        self.assertTrue(os.path.exists(os.path.join(self.b, "eski.bak")))
        self.assertTrue(os.path.exists(os.path.join(self.b, "_engine", self.eski, "plan.json")))

    def test_kategori_filtresi(self):
        res = sd.candidates(self.b, only=["pycache"])
        self.assertEqual(list(res), ["pycache"])


if __name__ == "__main__":
    unittest.main()
