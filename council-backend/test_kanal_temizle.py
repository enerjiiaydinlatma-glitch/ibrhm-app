import json
import os
import tempfile
import unittest

import kanal_temizle as kt


def v(i, baslik, yayin, gizlilik="public", sure="PT1M37S", izl="5", **st):
    status = {"privacyStatus": gizlilik, "embeddable": True, "license": "youtube", "publicStatsViewable": True, "selfDeclaredMadeForKids": False}
    status.update(st)
    return {"id": i, "snippet": {"title": baslik, "publishedAt": yayin + "T10:00:00Z"}, "status": status,
            "statistics": {"viewCount": izl}, "contentDetails": {"duration": sure}}


class AdayTest(unittest.TestCase):
    VIDEOLAR = [v("A", "Did OpenAI Disclose 6 Incidents To Block Competitors?", "2026-09-17", izl="9"),
                v("B", "How did a red-team AI agent breach 3 production systems?", "2026-08-28", izl="1149"),
                v("C", "Could Your Friend Be A Robot?", "2026-10-23", izl="39"),            # kesimden sonra
                v("D", "Old private one", "2026-09-01", gizlilik="private"),                  # zaten ozel
                v("K", "Konsey videosu ama eski tarihli", "2026-09-30")]                      # konsey kaydinda

    def test_aday_secimi_ve_siralama(self):
        a = kt.adaylar(self.VIDEOLAR, {"K"})
        self.assertEqual([x["id"] for x in a], ["B", "A"])                  # izlenmeye gore
        self.assertEqual(a[0]["sure"], 97)

    def test_riskli_sadece(self):
        a = kt.adaylar(self.VIDEOLAR, {"K"}, riskli_sadece=True)
        self.assertEqual([x["id"] for x in a], ["A"])
        self.assertTrue(a[0]["riskler"])

    def test_sure_ve_riskli(self):
        self.assertEqual(kt.sure_sn("PT1M37S"), 97)
        self.assertEqual(kt.sure_sn("PT45S"), 45)
        self.assertEqual(kt.sure_sn("PT1H2M3S"), 3723)
        self.assertEqual(kt.sure_sn("bozuk"), 0)
        self.assertEqual(kt.riskli("What is a robot?"), [])


class UygulaTest(unittest.TestCase):
    def test_govde_ayarlari_korur_publishat_yok(self):
        a = kt.adaylar([v("B", "x", "2026-08-28", license="creativeCommon")], set())[0]
        g = kt.govde(a, "private")
        self.assertEqual(g["status"]["privacyStatus"], "private")
        self.assertEqual(g["status"]["license"], "creativeCommon")
        self.assertNotIn("publishAt", g["status"])

    def test_onay_yoksa_degismez_onayla_kayit_ve_geri_al(self):
        a = kt.adaylar([v("B", "x", "2026-08-28"), v("A", "y", "2026-09-01")], set())
        cagri = []
        yapilan, _ = kt.uygula(a, cagri.append, lambda m: False, "yok.json")
        self.assertEqual((yapilan, cagri), ([], []))
        yol = os.path.join(tempfile.mkdtemp(), "k.json")
        yapilan, _ = kt.uygula(a, cagri.append, lambda m: True, yol)
        self.assertEqual(len(yapilan), 2)
        self.assertTrue(all(c["status"]["privacyStatus"] == "private" for c in cagri))
        kayit = json.load(open(yol, encoding="utf-8"))
        geri = []
        n, _ = kt.geri_al(kayit, geri.append, lambda m: True)
        self.assertEqual(n, 2)
        self.assertTrue(all(g["status"]["privacyStatus"] == "public" and g["status"]["license"] == "youtube" for g in geri))
        n0, _ = kt.geri_al(kayit, geri.append, lambda m: False)
        self.assertEqual(n0, 0)

    def test_aday_yoksa_bir_sey_yapmaz(self):
        cagri = []
        self.assertEqual(kt.uygula([], cagri.append, lambda m: True, "x.json")[0], [])
        self.assertEqual(cagri, [])


if __name__ == "__main__":
    unittest.main()
