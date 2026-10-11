import unittest

import snapshot_dene as sd


class Dene(unittest.TestCase):
    def _kos(self, calisiyor_dizisi, snapshot_sonuclari, **kw):
        log, uyku = [], []
        cal = iter(calisiyor_dizisi)
        snap = iter(snapshot_sonuclari)

        def calisiyor():
            v = next(cal)
            if isinstance(v, Exception):
                raise v
            return v

        def snapshot():
            v = next(snap)
            if isinstance(v, Exception):
                raise v
            return v

        r = sd.dene(calisiyor, snapshot, uyku=uyku.append, log=log.append, **kw)
        return r, log, uyku

    def test_ilk_denemede_basarili(self):
        r, log, uyku = self._kos([True], [{"ok": True, "files": 140}])
        self.assertTrue(r)
        self.assertEqual(uyku, [])
        self.assertIn("alindi: 140", log[0])

    def test_sunucu_yanitlamazsa_tekrar_dener(self):
        r, log, uyku = self._kos([False, False, True], [{"ok": True, "files": 5}], deneme=5, bekle=7)
        self.assertTrue(r)
        self.assertEqual(uyku, [7, 7])            # iki kez bekledi
        self.assertEqual(sum("yanit vermedi" in m for m in log), 2)

    def test_snapshot_ok_false_sebebi_yazilir(self):
        r, log, _ = self._kos([True, True], [{"ok": False, "error": "sozdizimi hatasi var"}, {"ok": True, "files": 1}], deneme=3)
        self.assertTrue(r)
        self.assertTrue(any("ALINMADI" in m and "sozdizimi" in m for m in log))

    def test_istisna_yutulmaz_loglanir_ve_devam_eder(self):
        r, log, _ = self._kos([RuntimeError("x"), True], [{"ok": True, "files": 2}], deneme=3)
        self.assertTrue(r)
        self.assertTrue(any("snapshot hatasi" in m and "RuntimeError" in m for m in log))

    def test_hic_basarilamazsa_false_ve_acik_uyari(self):
        r, log, uyku = self._kos([False] * 3, [], deneme=3, bekle=1)
        self.assertFalse(r)
        self.assertEqual(len(uyku), 2)             # son denemeden sonra bekleme yok
        self.assertIn("ALINAMADI", log[-1])


if __name__ == "__main__":
    unittest.main()
