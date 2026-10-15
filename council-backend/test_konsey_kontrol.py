import json
import os
import tempfile
import unittest

import konsey_kontrol as kk


class KontrolTest(unittest.TestCase):
    def test_kayitli_idler_tekil_ve_bozuk_satir_atlanir(self):
        yol = os.path.join(tempfile.mkdtemp(), "k.jsonl")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(json.dumps({"video_id": "A"}) + "\nbozuk\n" + json.dumps({"video_id": "A"}) + "\n" + json.dumps({"video_id": "B"}) + "\n")
        self.assertEqual(kk.kayitli_idler(yol), ["A", "B"])
        self.assertEqual(kk.kayitli_idler(os.path.join(tempfile.mkdtemp(), "yok")), [])

    def test_durum_metinleri(self):
        self.assertIn("private", kk.durum({"status": {"privacyStatus": "private"}}))
        self.assertIn("HERKESE ACIK", kk.durum({"status": {"privacyStatus": "public"}}))
        self.assertIn("ZAMANLANDI", kk.durum({"status": {"privacyStatus": "private", "publishAt": "2026-10-15T00:00:00Z"}}))

    def test_satirlar_eksik_video(self):
        it = {"id": "A", "snippet": {"title": "T", "publishedAt": "x"}, "status": {"privacyStatus": "public"}, "statistics": {"viewCount": "5"}}
        s = kk.satirlar([it], ["A", "Z"])
        self.assertIn("Izlenme: 5", s[0])
        self.assertIn("BULUNAMADI", s[1])


class YasTest(unittest.TestCase):
    def it(self, yayin, gizlilik="public", publish_at=None, izl="10"):
        st = {"privacyStatus": gizlilik}
        if publish_at:
            st["publishAt"] = publish_at
        return {"id": "A", "snippet": {"title": "T", "publishedAt": yayin}, "status": st, "statistics": {"viewCount": izl}}

    def test_yas_ve_saatlik(self):
        import datetime
        simdi = datetime.datetime(2026, 10, 15, 6, 0, 0)
        it = self.it("2026-10-14T18:00:00Z")                      # 12 saat once
        self.assertAlmostEqual(kk.yas_saat(it, simdi), 12.0)
        self.assertIn("Saatlik: 0.83", kk.satirlar([it], ["A"], simdi)[0])    # 10 / 12
        self.assertIsNone(kk.yas_saat(self.it("2026-10-14T18:00:00Z", "private"), simdi))
        self.assertIsNone(kk.yas_saat(self.it("2026-10-14T18:00:00Z", "private", "2026-10-16T00:00:00Z"), simdi))
        self.assertIn("cok yeni", kk.satirlar([self.it("2026-10-15T05:30:00Z")], ["A"], simdi)[0])


if __name__ == "__main__":
    unittest.main()
