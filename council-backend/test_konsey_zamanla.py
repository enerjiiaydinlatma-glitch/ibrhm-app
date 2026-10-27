import datetime
import unittest

import konsey_zamanla as kz

SIMDI = datetime.datetime(2026, 10, 14, 15, 0)


def item(gizlilik="private", publish_at=None):
    st = {"privacyStatus": gizlilik}
    if publish_at:
        st["publishAt"] = publish_at
    return {"id": "V1", "snippet": {"title": "T"}, "status": st}


class ZamanlaTest(unittest.TestCase):
    def test_ozel_video_zamanlanir_ve_govde_dogru(self):
        cagri = []
        ok, msg = kz.zamanla(item(), "2026-10-15 02:30", cagri.append, lambda o: True, SIMDI)
        self.assertTrue(ok)
        self.assertEqual(cagri, [{"id": "V1", "status": {"privacyStatus": "private", "publishAt": "2026-10-14T23:30:00Z", "selfDeclaredMadeForKids": False}}])

    def test_herkese_acik_video_reddedilir(self):
        cagri = []
        for g in ("public", "unlisted"):
            ok, msg = kz.zamanla(item(g), "2026-10-15 02:30", cagri.append, lambda o: True, SIMDI)
            self.assertFalse(ok)
        self.assertEqual(cagri, [])

    def test_bulunamayan_video(self):
        self.assertFalse(kz.zamanla(None, "2026-10-15 02:30", lambda b: None, lambda o: True, SIMDI)[0])

    def test_onay_yoksa_degismez(self):
        cagri = []
        ok, msg = kz.zamanla(item(), "2026-10-15 02:30", cagri.append, lambda o: False, SIMDI)
        self.assertFalse(ok)
        self.assertEqual(cagri, [])

    def test_gecersiz_saat_degismez(self):
        cagri = []
        for saat in ("yarin", "2026-10-14 18:05", "2026-10-01 10:00"):
            self.assertFalse(kz.zamanla(item(), saat, cagri.append, lambda o: True, SIMDI)[0])
        self.assertEqual(cagri, [])

    def test_mevcut_zamanlama_ozette_gorunur(self):
        ozetler = []
        kz.zamanla(item(publish_at="2026-10-20T00:00:00Z"), "2026-10-15 02:30", lambda b: None, lambda o: ozetler.append(o) or True, SIMDI)
        self.assertIn("2026-10-20T00:00:00Z", ozetler[0])


if __name__ == "__main__":
    unittest.main()


class IptalTest(unittest.TestCase):
    def item(self, gizlilik="private", publish="2026-10-29T23:30:00Z"):
        st = {"privacyStatus": gizlilik}
        if publish:
            st["publishAt"] = publish
        return {"id": "V1", "snippet": {"title": "T"}, "status": st}

    def test_iptal_govde_publishat_icermez(self):
        govdeler = []
        ok, _ = kz.iptal(self.item(), govdeler.append, lambda m: True)
        self.assertTrue(ok)
        self.assertEqual(govdeler[0]["status"]["privacyStatus"], "private")
        self.assertNotIn("publishAt", govdeler[0]["status"])

    def test_iptal_reddedilen_durumlar(self):
        for it in (None, self.item("public"), self.item("unlisted"), self.item(publish=None)):
            cagri = []
            ok, msg = kz.iptal(it, cagri.append, lambda m: True)
            self.assertFalse(ok)
            self.assertEqual(cagri, [])

    def test_onay_yoksa_degismez(self):
        cagri = []
        ok, _ = kz.iptal(self.item(), cagri.append, lambda m: False)
        self.assertFalse(ok)
        self.assertEqual(cagri, [])
