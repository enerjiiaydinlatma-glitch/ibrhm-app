import os
import tempfile
import unittest

import rules_guncelle as rg

ORNEK = "\n".join([
    "- [FORMAT] format satiri",
    "- [LEGAL] NEVER assert crime and cover-up",
    "- [PRIORITY] eski oncelik metni",
    "- [CLOSING] kapanis",
])


class KuralTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.y = os.path.join(self.d, "operator_rules.md")
        open(self.y, "w", encoding="utf-8").write(ORNEK)

    def test_yalniz_priority_degisir_ve_yedek_alinir(self):
        ok, msg = rg.uygula(self.y)
        self.assertTrue(ok, msg)
        s = open(self.y, encoding="utf-8").read().split("\n")
        self.assertEqual(s[0], "- [FORMAT] format satiri")
        self.assertEqual(s[1], "- [LEGAL] NEVER assert crime and cover-up")
        self.assertEqual(s[3], "- [CLOSING] kapanis")
        self.assertIn("BONUS", s[2])
        self.assertNotIn("eski oncelik", s[2])
        self.assertTrue(any(f.startswith("operator_rules.md.bak_") for f in os.listdir(self.d)))

    def test_kontrol_dosyayi_degistirmez(self):
        rg.uygula(self.y, kontrol=True)
        self.assertEqual(open(self.y, encoding="utf-8").read(), ORNEK)

    def test_tekrar_calistirma_zararsiz_ve_geri_al(self):
        rg.uygula(self.y)
        self.assertEqual(rg.uygula(self.y)[1], "Zaten guncel.")
        self.assertTrue(rg.geri_al(self.y)[0])
        self.assertEqual(open(self.y, encoding="utf-8").read(), ORNEK)

    def test_legal_yoksa_dokunmaz(self):
        open(self.y, "w", encoding="utf-8").write("- [PRIORITY] x")
        ok, _ = rg.uygula(self.y)
        self.assertFalse(ok)
        self.assertEqual(open(self.y, encoding="utf-8").read(), "- [PRIORITY] x")

    def test_gercek_dosya_bicimi_cift_priority_dokunmaz(self):
        open(self.y, "w", encoding="utf-8").write(ORNEK + "\n- [PRIORITY] ikinci")
        self.assertFalse(rg.uygula(self.y)[0])

    def test_crlf_korunur(self):
        open(self.y, "wb").write(ORNEK.replace("\n", "\r\n").encode("utf-8"))
        self.assertTrue(rg.uygula(self.y)[0])
        ham = open(self.y, "rb").read()
        self.assertEqual(ham.count(b"\r\n"), 3)
        self.assertEqual(ham.count(b"\n"), 3)

    def test_yeni_metin_legal_ve_niyet_yasagi_icerir(self):
        self.assertIn("LEGAL", rg.YENI_PRIORITY)
        self.assertIn("YASAK", rg.YENI_PRIORITY)


if __name__ == "__main__":
    unittest.main()
