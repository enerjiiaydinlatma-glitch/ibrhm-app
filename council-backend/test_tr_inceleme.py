import json
import os
import tempfile
import unittest

import tr_inceleme as t


def sahte(cevaplar):
    """cevaplar: {saglayici: metin | Exception}"""
    def al(ad):
        def c(mesajlar, sistem):
            v = cevaplar[ad]
            if isinstance(v, Exception):
                raise v
            return v
        return c
    return al


class CeviriTest(unittest.TestCase):
    def test_numarali_ceviri_ayni_sirada(self):
        r = t.ceviri(["The claim is up to 5.5x faster.", "NVIDIA says so."],
                     ["gemini"], sahte({"gemini": "1. İddia 5,5x'e kadar daha hızlı.\n2. NVIDIA öyle diyor."}))
        self.assertEqual(r["tr"], ["İddia 5,5x'e kadar daha hızlı.", "NVIDIA öyle diyor."])
        self.assertEqual(r["saglayici"], "gemini")

    def test_anahtari_olmayan_saglayici_atlanir(self):
        r = t.ceviri(["Hello world line."], ["gemini", "groq"],
                     sahte({"gemini": RuntimeError("anahtar yok"), "groq": "1. Merhaba dünya satırı."}))
        self.assertEqual(r["saglayici"], "groq")

    def test_hepsi_basarisiz(self):
        r = t.ceviri(["a line of text"], ["gemini"], sahte({"gemini": RuntimeError("x")}))
        self.assertEqual(r["tr"], [])
        self.assertIn("yapilamadi", r["hata"])

    def test_eksik_satir_isaretlenir(self):
        r = t.ceviri(["first line here", "second line here", "third line here"], ["gemini"],
                     sahte({"gemini": "1. birinci\n2. ikinci"}))
        self.assertEqual(r["tr"][2], "(çevrilemedi)")
        self.assertEqual(r["eksik"], [2])

    def test_yarisindan_fazlasi_eksikse_reddedilir(self):
        r = t.ceviri(["one line", "two line", "three line"], ["gemini", "groq"],
                     sahte({"gemini": "1. bir", "groq": "1. bir\n2. iki\n3. üç"}))
        self.assertEqual(r["saglayici"], "groq")

    def test_bos_girdi(self):
        self.assertEqual(t.ceviri(["", " "])["tr"], ["", ""])


class UretimMetniTest(unittest.TestCase):
    def test_run_json_okur(self):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, "2026-10-08"))
        json.dump({"steps": {"short": {"title": "Can X do Y?", "script": "AURA: line one\nALPHA: line two\n",
                                       "description": "Desc one.\n\nSource: https://x.com\n\n#AI", "video_id": ""}}},
                  open(os.path.join(d, "2026-10-08", "run.json"), "w", encoding="utf-8"))
        m = t.uretim_metni("2026-10-08", d)
        self.assertEqual(m["baslik"], "Can X do Y?")
        self.assertEqual(m["satirlar"], ["AURA: line one", "ALPHA: line two"])
        self.assertIsNone(t.uretim_metni("2026-10-09", d))


if __name__ == "__main__":
    unittest.main()
