import datetime
import json
import os
import tempfile
import unittest

import analiz

ADAY = [
    {"title": "Mistral beats rivals in its own benchmark", "url": "https://mistral.ai/n", "alan": "mistral.ai", "puan": 9,
     "etiketler": ["birincil kaynak"], "engel": "", "haber_sayisi": 3},
    {"title": "OpenAI secretly hid results", "url": "https://openai.com/a", "alan": "openai.com", "puan": 12,
     "etiketler": [], "engel": "niyet", "haber_sayisi": 1},
    {"title": "Nvidia funds the buyers", "url": "https://blogs.nvidia.com/x", "alan": "blogs.nvidia.com", "puan": 7,
     "etiketler": [], "engel": "", "haber_sayisi": 2},
]
VID = [{"id": str(i), "title": t, "published": f"2026-10-0{d}T13:00:00Z", "views": v, "likes": 1, "comments": 0, "privacy": "public"}
       for i, (t, d, v) in enumerate([("Claim: X. Receipt", 1, 5), ("Claim: Y. Receipt", 2, 9), ("The Receipt: Z", 3, 40),
                                      ("Three Claims Fail", 4, 3), ("Other video", 5, 100), ("Other 2", 6, 8)])]


class AdayTest(unittest.TestCase):
    def test_engelli_adaylar_tartismaya_girmez(self):
        a = analiz.aday_kimlikleri(ADAY)
        self.assertEqual([x["id"] for x in a], ["A1", "A2"])
        self.assertNotIn("OpenAI secretly hid results", [x["title"] for x in a])

    def test_karar_gecerli(self):
        a = analiz.aday_kimlikleri(ADAY)
        k = analiz.karar_ayikla('Tamam: {"secim":"A2","alternatif":["A1","A9"],"gerekce":"x","aci":"y"}', a)
        self.assertEqual(k["secim"], "A2")
        self.assertEqual(k["alternatif"], ["A1"])

    def test_karar_uydurma_kimlik_reddedilir(self):
        a = analiz.aday_kimlikleri(ADAY)
        self.assertIsNone(analiz.karar_ayikla('{"secim":"A7"}', a))
        self.assertIsNone(analiz.karar_ayikla("json yok", a))
        self.assertIsNone(analiz.karar_ayikla('{"secim":"OpenAI hid"}', a))

    def test_karar_ver_kurala_duser(self):
        a = analiz.aday_kimlikleri(ADAY)
        k = analiz.karar_ver([{"speaker": "aura", "text": "bilmiyorum"}], a)
        self.assertEqual((k["secim"], k["kaynak"]), ("A1", "kural"))
        k2 = analiz.karar_ver([{"speaker": "aura", "text": '{"secim":"A2","gerekce":"g"}'}], a)
        self.assertEqual((k2["secim"], k2["kaynak"]), ("A2", "konsey"))


class VeriTest(unittest.TestCase):
    def test_sinyaller(self):
        s = analiz.kalip_sinyalleri(VID)
        self.assertEqual(s["video_sayisi"], 6)
        self.assertEqual(s["medyan_izlenme"], 8.5)
        self.assertEqual(s["baslik_sablonlari"][0]["sablon"], "claim")
        self.assertEqual(s["en_iyi"][0]["izlenme"], 100)

    def test_uydurma_tek_saat_sinyal_vermez(self):
        # tracker yalniz tarih tutar; kanal_tracker hepsine T12:00:00Z yazar -> tek kova -> saat sinyali verilmemeli
        v = [{**x, "published": x["published"][:10] + "T12:00:00Z"} for x in VID]
        s = analiz.kalip_sinyalleri(v)
        self.assertEqual(s["saatler"], [])
        self.assertIn("saat", s["saat_notu"].lower())

    def test_gercek_farkli_saatler_korunur(self):
        v = [{**VID[0], "published": "2026-10-01T09:30:00Z"}, {**VID[1], "published": "2026-10-02T17:10:00Z"}]
        s = analiz.kalip_sinyalleri(v)
        self.assertEqual(sorted(r["saat_utc"] for r in s["saatler"]), [9, 17])
        self.assertEqual(s["saat_notu"], "")

    def test_private_sayilmaz_ve_bos(self):
        v = [{**VID[0], "privacy": "private"}]
        self.assertEqual(analiz.kalip_sinyalleri(v)["video_sayisi"], 0)

    def test_veri_hatasi_dayanikli(self):
        o = analiz.veri_ozeti({"ok": False, "hata": "x", "videolar": []})
        self.assertFalse(o["kanal_ok"])
        self.assertIn("kanal_hata", o)


class AkisGuvenTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._o = (analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL)
        analiz.ENGINE = self.d
        analiz.SON_YOL = os.path.join(self.d, "son.json")
        analiz.GECMIS_YOL = os.path.join(self.d, "g.jsonl")
        analiz.GIRIS_YOL = os.path.join(self.d, "giris.json")

    def tearDown(self):
        analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL = self._o

    def _calistir(self, tr_text):
        return analiz.calistir(lambda: "ok", lambda: {"adaylar": ADAY},
                               lambda b, p: [{"speaker": "aura", "text": tr_text}],
                               kanal={"ok": True, "abone": 26, "videolar": VID}, sutun="receipt")

    def test_akis_ve_onay(self):
        self._calistir('{"secim":"A2","gerekce":"g"}')
        s = analiz.son()
        self.assertEqual(s["durum"], "onay_bekliyor")
        self.assertEqual(s["karar"]["secim"], "A2")
        r = analiz.onayla("A1")
        self.assertTrue(r["ok"])
        self.assertTrue(analiz.son()["onay"]["degisti"])
        self.assertFalse(analiz.onayla("A9")["ok"])

    def test_aday_yok(self):
        r = analiz.calistir(lambda: "x", lambda: {"adaylar": []}, lambda b, p: [], kanal={"ok": True, "videolar": []}, sutun="receipt")
        self.assertIn("bulunamadi", r)

    def _gun(self, geri):
        return (datetime.datetime.now() - datetime.timedelta(days=geri)).replace(microsecond=0).isoformat()

    def test_ayni_gun_cok_analiz_tek_oneri_sayilir(self):
        for _ in range(5):
            analiz.log({"olay": "oneri", "secim": "A1"})
        g = analiz.guven_durumu()
        self.assertEqual(g["oneri"], 1)
        analiz.log({"olay": "onay", "secim": "A1", "degisti": False})
        self.assertEqual(analiz.guven_durumu()["degismeden_onay"], 1)

    def test_gunun_son_onayi_belirler(self):
        analiz.log({"olay": "oneri", "secim": "A1"})
        analiz.log({"olay": "onay", "secim": "A1", "degisti": False, "zaman": self._gun(0)[:11] + "09:00:00"})
        analiz.log({"olay": "onay", "secim": "A2", "degisti": True, "zaman": self._gun(0)[:11] + "10:00:00"})
        self.assertEqual(analiz.guven_durumu()["degismeden_onay"], 0)

    def test_guven(self):
        for k in range(7):
            analiz.log({"olay": "oneri", "secim": "A1", "kaynak": "konsey", "zaman": self._gun(k)})
            analiz.log({"olay": "onay", "secim": "A1", "degisti": False, "zaman": self._gun(k)})
        self.assertFalse(analiz.guven_durumu()["otomatige_hazir"])  # retention girilmedi
        analiz.retention_kaydet("16,2")
        g = analiz.guven_durumu()
        self.assertTrue(g["otomatige_hazir"], g)
        analiz.log({"olay": "ihlal"})
        self.assertFalse(analiz.guven_durumu()["otomatige_hazir"])

    def test_retention_dogrulama(self):
        self.assertFalse(analiz.retention_kaydet("abc")["ok"])
        self.assertFalse(analiz.retention_kaydet("150")["ok"])


if __name__ == "__main__":
    unittest.main()


class SayfaElemeTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._o = (analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL)
        analiz.ENGINE = self.d
        analiz.SON_YOL = os.path.join(self.d, "s.json")
        analiz.GECMIS_YOL = os.path.join(self.d, "g.jsonl")
        analiz.GIRIS_YOL = os.path.join(self.d, "r.json")

    def tearDown(self):
        analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL = self._o

    def _hz(self, url):
        if "mistral" in url or "anthropic" in url:
            return {"ok": True, "iddia": "The model is state-of-the-art.", "iddia_anahtar": "state-of-the-art", "kanit": 5, "hata": ""}
        return {"ok": False, "iddia": "", "iddia_anahtar": "", "kanit": 0, "hata": "iddia yok"}

    def test_elenen_konseye_gitmez_ve_kimlikler_yeniden(self):
        goruldu = {}
        def tartis(b, p):
            goruldu["brif"] = b
            return [{"speaker": "aura", "text": '{"secim":"A1","gerekce":"g"}'}]
        ek = {"title": "Anthropic ships Big Model", "url": "https://anthropic.com/n", "alan": "anthropic.com", "puan": 8,
              "etiketler": [], "engel": "", "haber_sayisi": 1}
        analiz.calistir(lambda: "ok", lambda: {"adaylar": ADAY + [ek]}, tartis, kanal={"ok": True, "videolar": []},
                        hazirlik=self._hz, sutun="receipt")
        s = analiz.son()
        self.assertEqual([a["id"] for a in s["adaylar"]], ["A1", "A2"])
        self.assertEqual({a["alan"] for a in s["adaylar"]}, {"mistral.ai", "anthropic.com"})
        self.assertEqual(len(s["elenen"]), 1)
        self.assertNotIn("Nvidia funds", goruldu["brif"])
        self.assertIn("SAYFADA IDDIA", goruldu["brif"])
        self.assertEqual(analiz.onayla("A1")["iddia_anahtar"], "state-of-the-art")

    def test_hepsi_elenirse_aday_yok_konsey_calismaz(self):
        cagri = []
        r = analiz.calistir(lambda: "ok", lambda: {"adaylar": [ADAY[2]]}, lambda b, p: cagri.append(1) or [],
                            kanal={"ok": True, "videolar": []}, hazirlik=self._hz, sutun="receipt")
        self.assertIn("bulunamadi", r)
        self.assertEqual(cagri, [])
        self.assertEqual(analiz.son()["durum"], "aday_yok")
        self.assertEqual(len(analiz.son()["elenen"]), 1)


class TekAdayTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._o = (analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL)
        analiz.ENGINE = self.d
        analiz.SON_YOL = os.path.join(self.d, "s.json")
        analiz.GECMIS_YOL = os.path.join(self.d, "g.jsonl")
        analiz.GIRIS_YOL = os.path.join(self.d, "r.json")

    def tearDown(self):
        analiz.ENGINE, analiz.SON_YOL, analiz.GECMIS_YOL, analiz.GIRIS_YOL = self._o

    def test_tek_aday_konsey_calismaz_ve_acikca_yazilir(self):
        cagri = []
        hz = lambda url: {"ok": True, "iddia": "up to 5x faster than before today", "iddia_anahtar": "up to 5x faster", "kanit": 4, "hata": ""}
        analiz.calistir(lambda: "ok", lambda: {"adaylar": [ADAY[0]]}, lambda b, p: cagri.append(1) or [],
                        kanal={"ok": True, "videolar": []}, hazirlik=hz, sutun="receipt")
        s = analiz.son()
        self.assertEqual(cagri, [])
        self.assertEqual(s["karar"]["kaynak"], "tek-aday")
        self.assertEqual(s["karar"]["secim"], "A1")
        self.assertEqual(s["durum"], "onay_bekliyor")
