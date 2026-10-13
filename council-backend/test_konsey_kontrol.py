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


if __name__ == "__main__":
    unittest.main()
