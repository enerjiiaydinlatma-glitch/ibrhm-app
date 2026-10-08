import os, tempfile, unittest
import rotate_voice_key as rk


class Rotate(unittest.TestCase):
    def setUp(self):
        self.b = tempfile.mkdtemp()
        self.old = "sc-local-OLDKEYVALUE123456"
        open(os.path.join(self.b, ".voice_key"), "w").write(self.old + "\n")
        open(os.path.join(self.b, "a.py"), "w").write('K = "%s"\nprint(1)\n' % self.old)
        open(os.path.join(self.b, "b.bat"), "w").write("set X=1\r\nset AURA_VOICE_KEY=%s\r\n" % self.old)
        open(os.path.join(self.b, "c.py"), "w").write("temiz = 1\n")

    def test_yeni_anahtar_uretilir_ve_yazilir(self):
        r = rk.rotate(self.b)
        yeni = open(os.path.join(self.b, ".voice_key")).read().strip()
        self.assertTrue(yeni.startswith("sc-local-"))
        self.assertNotEqual(yeni, self.old)
        self.assertGreaterEqual(len(yeni), 30)

    def test_kodda_kalan_eski_anahtar_bulunur_ama_degeri_yazilmaz(self):
        r = rk.rotate(self.b)
        self.assertEqual(sorted(r["leftovers"]), [("a.py", 1), ("b.bat", 2)])
        self.assertTrue(all(isinstance(f, str) and isinstance(n, int) for f, n in r["leftovers"]))

    def test_degistir_eski_anahtari_yenisiyle_degistirir(self):
        r = rk.rotate(self.b, replace=True)
        yeni = open(os.path.join(self.b, ".voice_key")).read().strip()
        self.assertNotIn(self.old, open(os.path.join(self.b, "a.py")).read())
        self.assertIn(yeni, open(os.path.join(self.b, "a.py")).read())
        self.assertIn(yeni, open(os.path.join(self.b, "b.bat")).read())
        self.assertEqual(r["leftovers"], [])

    def test_iki_yenileme_farkli_anahtar(self):
        rk.rotate(self.b); k1 = open(os.path.join(self.b, ".voice_key")).read()
        rk.rotate(self.b); k2 = open(os.path.join(self.b, ".voice_key")).read()
        self.assertNotEqual(k1, k2)

    def test_eski_anahtar_yoksa_calisir(self):
        os.remove(os.path.join(self.b, ".voice_key"))
        r = rk.rotate(self.b)
        self.assertFalse(r["had_old"])
        self.assertTrue(os.path.exists(os.path.join(self.b, ".voice_key")))


if __name__ == "__main__":
    unittest.main()
