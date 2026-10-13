import os, tempfile, unittest
import rotate_voice_key as rk


class Rotate(unittest.TestCase):
    def _yaz(self, ad, veri):
        # BAYT olarak yaz: Windows'ta metin kipi "\n"->"\r\n" cevirir, "\r\n" yazinca "\r\r\n" olup satir sayisini bozuyordu
        with open(os.path.join(self.b, ad), "wb") as f:
            f.write(veri.encode("utf-8"))

    def _oku(self, ad):
        with open(os.path.join(self.b, ad), "rb") as f:
            return f.read().decode("utf-8")

    def setUp(self):
        self.b = tempfile.mkdtemp()
        self.old = "sc-local-OLDKEYVALUE123456"
        self._yaz(".voice_key", self.old + "\n")
        self._yaz("a.py", 'K = "%s"\nprint(1)\n' % self.old)
        self._yaz("b.bat", "set X=1\r\nset AURA_VOICE_KEY=%s\r\n" % self.old)
        self._yaz("c.py", "temiz = 1\n")

    def test_yeni_anahtar_uretilir_ve_yazilir(self):
        r = rk.rotate(self.b)
        yeni = self._oku(".voice_key").strip()
        self.assertTrue(yeni.startswith("sc-local-"))
        self.assertNotEqual(yeni, self.old)
        self.assertGreaterEqual(len(yeni), 30)

    def test_kodda_kalan_eski_anahtar_bulunur_ama_degeri_yazilmaz(self):
        r = rk.rotate(self.b)
        self.assertEqual(sorted(r["leftovers"]), [("a.py", 1), ("b.bat", 2)])
        self.assertTrue(all(isinstance(f, str) and isinstance(n, int) for f, n in r["leftovers"]))

    def test_degistir_eski_anahtari_yenisiyle_degistirir(self):
        r = rk.rotate(self.b, replace=True)
        yeni = self._oku(".voice_key").strip()
        self.assertNotIn(self.old, self._oku("a.py"))
        self.assertIn(yeni, self._oku("a.py"))
        self.assertIn(yeni, self._oku("b.bat"))
        self.assertEqual(r["leftovers"], [])

    def test_iki_yenileme_farkli_anahtar(self):
        rk.rotate(self.b); k1 = self._oku(".voice_key")
        rk.rotate(self.b); k2 = self._oku(".voice_key")
        self.assertNotEqual(k1, k2)

    def test_eski_anahtar_yoksa_calisir(self):
        os.remove(os.path.join(self.b, ".voice_key"))
        r = rk.rotate(self.b)
        self.assertFalse(r["had_old"])
        self.assertTrue(os.path.exists(os.path.join(self.b, ".voice_key")))


if __name__ == "__main__":
    unittest.main()
