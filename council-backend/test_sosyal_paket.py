import json
import os
import tempfile
import unittest

import sosyal_paket as sp


class PaketTest(unittest.TestCase):
    def test_kategori_konuden_bulunur_ve_etiketler(self):
        p = sp.paket({"video_id": "V1", "baslik": "A quarter of ice means roughly 15 m #Shorts", "kanca": "Quarter of the ice? Roughly 15 meters.",
                      "konu": "What if a quarter of Earth's ice melted?"})
        self.assertEqual(sp.kategori_bul({"konu": "What if a quarter of Earth's ice melted?"}), "afet")
        self.assertIn("#climate", p["aciklama"])
        self.assertTrue(p["aciklama"].startswith("Quarter of the ice? Roughly 15 meters."))   # kanca videodaki ile ayni
        self.assertEqual(p["link"], "https://youtu.be/V1")
        self.assertNotIn("#Shorts", p["baslik"])
        self.assertEqual(p["uyari"], [])

    def test_bilinmeyen_konu_varsayilan_etiket_ve_kanca_yoksa_baslik(self):
        p = sp.paket({"video_id": "V2", "baslik": "Some Title", "konu": "not in the pool"})
        self.assertIn("#whatif", p["aciklama"])
        self.assertTrue(p["aciklama"].startswith("Some Title"))

    def test_kayitlar_bozuk_satiri_atlar_ve_main(self):
        yol = os.path.join(tempfile.mkdtemp(), "k.jsonl")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(json.dumps({"video_id": "A", "baslik": "T1", "kanca": "H1?", "konu": "x"}) + "\nbozuk\n" + json.dumps({"baslik": "idsiz"}) + "\n")
        self.assertEqual([k["video_id"] for k in sp.kayitlar(yol)], ["A"])
        self.assertEqual(sp.kayitlar(os.path.join(tempfile.mkdtemp(), "yok")), [])


if __name__ == "__main__":
    unittest.main()
