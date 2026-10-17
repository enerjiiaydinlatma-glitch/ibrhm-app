import json
import os
import re
import tempfile
import unittest

import claim_lint
import konsey_format
import konsey_konular as kk


class HavuzTest(unittest.TestCase):
    def test_idler_ve_konular_tekil(self):
        self.assertEqual([k["id"] for k in kk.KONULAR], list(range(1, len(kk.KONULAR) + 1)))
        konular = [k["konu"].lower() for k in kk.KONULAR]
        self.assertEqual(len(konular), len(set(konular)))
        self.assertGreaterEqual(len(kk.KONULAR), 20)

    def test_her_konu_ingilizce_kisa_soru_ve_turkce_anlami_var(self):
        for k in kk.KONULAR:
            self.assertTrue(k["konu"].endswith("?"), k["konu"])
            self.assertLessEqual(len(k["konu"]), 60, k["konu"])
            self.assertTrue(k["tr"].strip() and k["eksen"].strip() and k["kategori"].strip())

    def test_guvenlik_gercek_isim_yok_engelleyici_lint_yok(self):
        for k in kk.KONULAR:
            self.assertEqual(konsey_format._entities().findall(k["konu"]), [], k["konu"])
            engel = [ad for ad, _h, _w in claim_lint.lint(k["konu"]) if ad in konsey_format.ENGELLEYICI]
            self.assertEqual(engel, [], k["konu"])

    def test_havuzda_tibbi_konu_yok(self):
        import konsey_format
        for k in kk.KONULAR:
            self.assertIsNone(konsey_format.MEDIKAL.search(k["konu"]), k["konu"])

    def test_kategori_cesitli(self):
        self.assertGreaterEqual(len({k["kategori"] for k in kk.KONULAR}), 5)

    def test_yeni_evren_kategorileri_ve_risk_etiketi(self):
        kats = {k["kategori"] for k in kk.KONULAR}
        for k in ("afet", "sehir", "robot", "uzay", "insan", "son", "fizik"):
            self.assertIn(k, kats)
        for k in kk.KONULAR[28:]:
            self.assertIn(k["risk"], ("yesil", "sari", "insan"), k["konu"])
        for k in kk.KONULAR:
            self.assertNotRegex(k["konu"], r"(?i)flying|flies|alien|believe|right|origin|trigger")

    def test_onerilen_ilk_yeni_stratejiyi_izler(self):
        ilk3 = [kk.konu_bul(i)["konu"] for i in kk.ONERILEN_ILK[:3]]
        self.assertEqual(ilk3[0], "What if the sea rose 20 centimeters?")
        self.assertIn("fly", ilk3[1].lower())
        self.assertIn("Mars", ilk3[2])

    def test_onerilen_idler_gecerli(self):
        for i in kk.ONERILEN_ILK:
            self.assertIsNotNone(kk.konu_bul(i))
        self.assertIsNone(kk.konu_bul(999))


class KullanimTest(unittest.TestCase):
    def test_kullanilanlar_ve_liste(self):
        yol = os.path.join(tempfile.mkdtemp(), "k.jsonl")
        with open(yol, "w", encoding="utf-8") as f:
            f.write(json.dumps({"video_id": "A", "konu": "Is free shipping really free?"}) + "\n")
            f.write("bozuk satir\n")
            f.write(json.dumps({"video_id": "B"}) + "\n")
        u = kk.kullanilanlar(yol)
        self.assertEqual(u, {"is free shipping really free?"})
        txt = kk.liste(u)
        self.assertRegex(txt, r" 1 \| KULLANILDI")
        self.assertNotRegex(txt, r" 2 \| KULLANILDI")

    def test_dosya_yoksa_bos(self):
        self.assertEqual(kk.kullanilanlar(os.path.join(tempfile.mkdtemp(), "yok.jsonl")), set())


if __name__ == "__main__":
    unittest.main()


class ElemeTest(unittest.TestCase):
    def test_elenenler_gecerli_ve_oneride_yok(self):
        idler = {k["id"] for k in kk.KONULAR}
        self.assertTrue(set(kk.ELENENLER) <= idler)
        self.assertFalse(set(kk.ELENENLER) & set(kk.ONERILEN_ILK))
        self.assertTrue(all(kk.ELENENLER.values()))                      # her elemenin nedeni yazili
        self.assertEqual(len(kk.aktif()), len(kk.KONULAR) - len(kk.ELENENLER))

    def test_liste_elendi_isaretler(self):
        self.assertIn("ELENDİ", kk.liste(set()))
