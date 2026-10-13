import unittest

import hook_gate as hg
import yukleme_meta as ym


def kodlar(s):
    return {k for k, _ in s}


class Kanca(unittest.TestCase):
    def test_receipt_acilisi_reddedilir(self):
        # 11 Ekim'de uretilen gercek acilis: kanca degil
        s = hg.kontrol("NVIDIA's 'One petaflop of FP4' Claim vs Its Own Page",
                       "The claim, from NVIDIA's own page: \"One petaflop of FP4 AI performance and up to 128GB unified memory\"",
                       "Our reading: partly supported. The headline or the details: which do you trust?", "CLAIM VS PAGE")
        k = kodlar(s)
        self.assertTrue({"ILK_UZUN", "YASAK_ACILIS", "ILK_ALINTI", "BASLIK_UZUN", "EKRAN_VARSAYILAN"} <= k, k)

    def test_iyi_acilis_gecer(self):
        s = hg.kontrol("Five AIs, one hairstyle fight", "Five AIs. One hairstyle. Total chaos?",
                       "Team Alpha or Team Beta? Comment.", "WHO WINS THIS")
        self.assertEqual(s, [])

    def test_tetik_olmayan_acilis(self):
        self.assertIn("TETIK_YOK", kodlar(hg.kontrol("Short title", "Alpha explains the new policy", "", "WHO WINS THIS")))

    def test_baslik_kurallari(self):
        k = kodlar(hg.kontrol("AI news: what happened this week in total", "Why did Alpha lie?", "", "ALPHA VS BETA"))
        self.assertIn("BASLIK_IKI_NOKTA", k)
        self.assertNotIn("TETIK_YOK", k)

    def test_ekran_metni(self):
        self.assertIn("EKRAN_UZUNLUK", kodlar(hg.kontrol("t", "Why now?", "", "THIS IS A VERY LONG OPENING CARD TEXT")))
        self.assertIn("EKRAN_YOK", kodlar(hg.kontrol("t", "Why now?", "", "")))
        self.assertNotIn("EKRAN_YOK", kodlar(hg.kontrol("t", "Why now?", "", "WHO IS RIGHT")))

    def test_son_kapanis_yalniz_doluysa_denetlenir(self):
        self.assertNotIn("SON_KAPANIS", kodlar(hg.kontrol("t", "Why now?", "", "WHO IS RIGHT")))
        self.assertIn("SON_KAPANIS", kodlar(hg.kontrol("t", "Why now?", "That was all for today.", "WHO IS RIGHT")))

    def test_tekrar(self):
        onceki = ["Why did Alpha lie", "Why did Beta cry", "Five AIs one fight", "Why did Delta run"]
        self.assertEqual([k for k, _ in hg.tekrar_kontrol(onceki, "Why did Gamma hide")][0], "ACILIS_TEKRAR")
        self.assertEqual(hg.tekrar_kontrol(onceki, "Nobody expected this"), [])


class DilMeta(unittest.TestCase):
    def test_snippet_dil_her_zaman_yazilir(self):
        sn = ym.video_snippet("t", "d", ["a"])
        self.assertEqual((sn["defaultLanguage"], sn["defaultAudioLanguage"]), ("en", "en"))
        self.assertEqual(sn["categoryId"], "28")
        self.assertEqual(ym.video_snippet("t", "d")["tags"], [])

    def test_plan_yalniz_eksik_ve_farklilari_listeler(self):
        v = [{"id": "a", "snippet": {"title": "A"}},
             {"id": "b", "snippet": {"title": "B", "defaultLanguage": "en", "defaultAudioLanguage": "en"}},
             {"id": "c", "snippet": {"title": "C", "defaultLanguage": "tr", "defaultAudioLanguage": "en"}}]
        p = ym.dil_plani(v)
        self.assertEqual([x["id"] for x in p], ["a", "c"])
        self.assertEqual(p[1]["eski"], ("tr", "en"))

    def test_guncelleme_baslik_aciklama_etiket_korunur(self):
        v = {"id": "x", "snippet": {"title": "T", "description": "D", "tags": ["z"], "categoryId": "22", "defaultLanguage": "tr"}}
        g = ym.guncelleme_govdesi(v)
        self.assertEqual(g["id"], "x")
        sn = g["snippet"]
        self.assertEqual((sn["title"], sn["description"], sn["tags"], sn["categoryId"]), ("T", "D", ["z"], "22"))
        self.assertEqual((sn["defaultLanguage"], sn["defaultAudioLanguage"]), ("en", "en"))

    def test_guncelleme_aciklama_yoksa_bos_string_etiket_yoksa_alan_yok(self):
        sn = ym.guncelleme_govdesi({"id": "y", "snippet": {"title": "T"}})["snippet"]
        self.assertEqual(sn["description"], "")
        self.assertNotIn("tags", sn)


if __name__ == "__main__":
    unittest.main()
