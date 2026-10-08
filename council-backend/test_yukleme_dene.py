import unittest

import yukleme_dene as yd


class _Resp:
    def __init__(self, status):
        self.status = status


class _Http(Exception):
    def __init__(self, status):
        super().__init__(f"HttpError {status}")
        self.resp = _Resp(status)


class DeneTest(unittest.TestCase):
    def _fn(self, hatalar):
        durum = {"i": 0}
        def fn():
            i = durum["i"]
            durum["i"] += 1
            if i < len(hatalar):
                raise hatalar[i]
            return {"id": "VID"}
        return fn, durum

    def test_410_yeni_oturumla_tekrar_dener(self):
        fn, d = self._fn([_Http(410), _Http(503)])
        bekle = []
        self.assertEqual(yd.dene(fn, uyku=bekle.append, log=lambda *_: None), {"id": "VID"})
        self.assertEqual(d["i"], 3)
        self.assertEqual(bekle, [2, 4])

    def test_kalici_hata_tekrar_denenmez(self):
        for kod in (400, 401, 403):
            fn, d = self._fn([_Http(kod)])
            with self.assertRaises(_Http):
                yd.dene(fn, uyku=lambda s: None, log=lambda *_: None)
            self.assertEqual(d["i"], 1)

    def test_deneme_sinirinda_vazgecer(self):
        fn, d = self._fn([_Http(410)] * 10)
        with self.assertRaises(_Http):
            yd.dene(fn, uyku=lambda s: None, log=lambda *_: None)
        self.assertEqual(d["i"], yd.DENEME)

    def test_ag_kopmasi_gecici(self):
        fn, d = self._fn([ConnectionError("reset")])
        self.assertEqual(yd.dene(fn, uyku=lambda s: None, log=lambda *_: None), {"id": "VID"})


if __name__ == "__main__":
    unittest.main()
