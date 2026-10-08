import datetime
import os
import tempfile
import unittest

import analiz
import sutun

NOW = datetime.datetime(2026, 10, 8, 12, 0, 0)


def vid(i, title, views, comments=0, gun=1, privacy="public"):
    return {"id": f"v{i}", "title": title, "published": f"2026-10-0{gun}T10:00:00Z", "views": views,
            "likes": 0, "comments": comments, "privacy": privacy}


class EtiketTest(unittest.TestCase):
    def test_gercek_basliklar(self):
        self.assertEqual(sutun.etiketle("Council Case #3: Should I tell my boss..."), "ikilem")
        self.assertEqual(sutun.etiketle("The Council Decides: Should I take a stake"), "ikilem")
        self.assertEqual(sutun.etiketle("Anthropic jumps to top rank as OpenAI slips"), "siralama")
        self.assertEqual(sutun.etiketle("What is a 'control point' in AI infrastructure"), "aciklayici")
        self.assertEqual(sutun.etiketle("Three AI Safety Claims Fail Inspection While Two Pass"), "receipt")
        self.assertEqual(sutun.etiketle("Did Cognition score 92.8 on a benchmark?"), "haber")
        self.assertEqual(sutun.etiketle(""), "diger")

    def test_gercek_kanal_basliklari_8_ekim(self):
        haber = ["How did a red-team AI agent breach 3 production systems?", "Why is Nvidia quietly acquiring Hugging Face?",
                 "AI Safety Testing Is Already Collapsing", "Testing AI Doesn't Mean You Control It",
                 "Did Cognition score 92.8 on a benchmark it helped design?", "Open weights is not open source - what does a company still control"]
        ikilem = ["Is it wrong to let AI help write a eulogy for someone you loved, or does the help not ma",
                  "A friend wants me to invest my savings in their AI startup - do I say yes to keep the fr",
                  "Is it a red flag if someone you're dating regularly talks to an AI companion app - or is",
                  "You can replace two team members with an AI tool and save your company money - do you re",
                  "If an AI chatbot genuinely helps someone more than their human therapist did, does it ma",
                  "Your data center outbid a hospital for power and nobody let you vote on it."]
        for b in haber:
            self.assertEqual(sutun.etiketle(b), "haber", b)
        for b in ikilem:
            self.assertEqual(sutun.etiketle(b), "ikilem", b)


class IstatistikTest(unittest.TestCase):
    def test_private_ve_taze_sayilmaz(self):
        v = [vid(1, "Council Case #1", 300), vid(2, "Council Case #2", 100, privacy="private"),
             {**vid(3, "Council Case #3", 50), "published": "2026-10-08T09:00:00Z"}]   # 3 saatlik: olgun degil
        t = sutun.istatistik(v, kayit={}, now=NOW)
        self.assertEqual(t["ikilem"]["deneme"], 1)
        self.assertEqual(t["ikilem"]["ort_izlenme"], 300)

    def test_kayitli_sutun_basliga_ustun(self):
        v = [vid(1, "Mistral Large 4: what the page says", 40)]
        t = sutun.istatistik(v, kayit={"v1": "receipt"}, now=NOW)
        self.assertIn("receipt", t)

    def test_skor_yorum_agirlikli(self):
        t = sutun.istatistik([vid(1, "Council Case #1", 100, comments=2)], kayit={}, now=NOW)
        self.assertEqual(t["ikilem"]["skor"], 100 + 2 * sutun.YORUM_AGIRLIK)


class OnerTest(unittest.TestCase):
    CMT = datetime.date(2026, 10, 8)  # persembe (hafta ici)

    def test_veri_az_en_az_denenen(self):
        tablo = {"haber": {"deneme": 30, "skor": 150}, "ikilem": {"deneme": 3, "skor": 200}, "siralama": {"deneme": 1, "skor": 90}}
        o = sutun.oner(tablo, self.CMT)
        self.assertEqual(o["mod"], "veri-topla")
        self.assertEqual(o["sutun"], "receipt")           # 0 deneme, en az denenen

    def test_veri_yeterli_somur_ya_da_kesif_deterministik(self):
        tablo = {s: {"deneme": 3, "skor": sk, "ort_izlenme": sk, "ort_yorum": 0} for s, sk in
                 (("haber", 50), ("ikilem", 300), ("siralama", 100), ("receipt", 10))}
        a = sutun.oner(tablo, self.CMT)
        b = sutun.oner(tablo, self.CMT)
        self.assertEqual(a, b)
        self.assertIn(a["mod"], ("somur", "kesif"))
        modlar = {sutun.oner(tablo, datetime.date(2026, 10, 8) + datetime.timedelta(days=i * 7))["mod"] for i in range(40)}
        self.assertEqual(modlar, {"somur", "kesif"})
        # somur gunlerinde en iyi sutun
        for i in range(40):
            g = datetime.date(2026, 10, 8) + datetime.timedelta(days=i * 7)
            o = sutun.oner(tablo, g)
            if o["mod"] == "somur":
                self.assertEqual(o["sutun"], "ikilem")

    def test_aciklayici_yalniz_hafta_sonu(self):
        self.assertNotIn("aciklayici", sutun.aktif_sutunlar(datetime.date(2026, 10, 8)))
        self.assertIn("aciklayici", sutun.aktif_sutunlar(datetime.date(2026, 10, 10)))


class AkisTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._o = (analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL, sutun.GECMIS_YOL, sutun.ENGINE)
        analiz.ENGINE = self.d
        analiz.SON_YOL = os.path.join(self.d, "s.json")
        analiz.GECMIS_YOL = os.path.join(self.d, "g.jsonl")
        analiz.GIRIS_YOL = os.path.join(self.d, "r.json")
        sutun.ENGINE = self.d
        sutun.GECMIS_YOL = os.path.join(self.d, "sg.jsonl")

    def tearDown(self):
        (analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL, sutun.GECMIS_YOL, sutun.ENGINE) = self._o

    def test_receipt_degilse_haber_taramasi_ve_konsey_calismaz(self):
        cagri = []
        r = analiz.calistir(lambda: cagri.append("gundem") or "x", lambda: {"adaylar": []},
                            lambda b, p: cagri.append("konsey") or [], kanal={"ok": True, "videolar": []}, sutun="ikilem")
        self.assertIn("İkilem", r)
        self.assertEqual(cagri, [])
        s = analiz.son()
        self.assertEqual(s["durum"], "sutun_hazir")
        self.assertEqual(s["sutun"], "ikilem")

    def test_sutun_onay_degisti_isareti(self):
        analiz.calistir(lambda: "x", lambda: {"adaylar": []}, lambda b, p: [], kanal={"ok": True, "videolar": []}, sutun="ikilem")
        oneri = analiz.son()["sutun_oneri"]["sutun"]
        diger = "siralama" if oneri != "siralama" else "ikilem"
        self.assertTrue(analiz.sutun_onayla(diger)["ok"])
        self.assertTrue(analiz.son()["sutun_onay"]["degisti"])
        self.assertFalse(analiz.sutun_onayla("uydurma")["ok"])

    def test_kayit_dongusu(self):
        sutun.kaydet("vX", "ikilem")
        self.assertEqual(sutun.kayitlar()["vX"], "ikilem")


if __name__ == "__main__":
    unittest.main()
