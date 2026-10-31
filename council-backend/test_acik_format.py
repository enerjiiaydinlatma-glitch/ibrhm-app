import unittest

import acik_format as af
import acik_gun as ag

IYI = ["If all the ice melted, how high would oceans rise?", "About 60 meters, according to NASA, if all the ice on land melted.",
       "That would swallow today's coastlines and harbors.", "Greenland's ice alone holds about 7 meters, says Scientific American.",
       "The sea has already risen about 8 inches since 1880, says NASA. What would you save first?"]


def beats(satirlar=None):
    return [("aura", "X", l, "") for l in (satirlar or IYI)]


def kodlar(satirlar=None, baslik=None, anahtar="deniz"):
    return {c for c, _ in af.kontrol_acik(beats(satirlar), baslik or af.ACIK_KONULAR[anahtar]["baslik"], "SEA LEVEL RISE", anahtar)}


def ham(satirlar=None):
    return "\n".join(f"aura | SCREEN {i} | {l} | image" for i, l in enumerate(satirlar or IYI, 1)) + \
        "\nTITLE: whatever\nHOOKTHUMB: SEA LEVEL RISE"


def parse(raw):
    b = [tuple(x.strip() for x in l.split("|")) for l in raw.splitlines() if l.startswith("aura")]
    return b, "t", "SEA LEVEL RISE"


class KapiTest(unittest.TestCase):
    def test_iyi_gecer(self):
        self.assertEqual(kodlar(), set())

    def test_konular_ve_olgular(self):
        for k, v in af.ACIK_KONULAR.items():
            self.assertTrue(af.olgu_metni(k).startswith("- "), k)
            self.assertLessEqual(len(v["baslik"]), af.BASLIK_MAX)
            self.assertTrue(v["baslik"].endswith("?"))
        self.assertIn("(source: NASA)", af.olgu_metni("deniz"))

    def test_kaynaksiz_rakam_ve_kosul(self):
        L = list(IYI)
        L[1] = "About 40 meters, according to NASA, if all the ice on land melted."
        self.assertIn("RAKAM_KAYNAK", kodlar(L))
        L = list(IYI)
        L[0] = "If the ice melted, how high would oceans rise?"
        L[1] = "About 60 meters, according to NASA, when the ice on land melted."
        self.assertIn("ONKOSUL_EKSIK", kodlar(L))

    def test_olgu_ve_kaynak_adi_zorunlu(self):
        L = list(IYI)
        L[1] = "The sea would rise a lot, as scientists say."
        L[3] = "Greenland's ice holds a big share."
        L[4] = "The sea keeps rising. What would you save first?"
        self.assertIn("OLGU_YOK", kodlar(L))
        L = list(IYI)
        L[1] = "About 60 meters if all the ice on land melted."
        L[3] = "Greenland's ice alone holds about 7 meters."
        L[4] = "The sea has already risen about 8 inches since 1880. What would you save first?"
        self.assertIn("KAYNAK_ADI", kodlar(L))

    def test_soru_uzunluk_isim_ve_yapi(self):
        L = list(IYI)
        L[0] = "The sea will rise a lot."
        self.assertIn("KANCA_SORU", kodlar(L))
        L = list(IYI)
        L[4] = "The sea has already risen about 8 inches since 1880, says NASA."
        self.assertIn("KAPANIS_SORU", kodlar(L))
        L = list(IYI)
        L[2] = "OpenAI would drown too."
        self.assertIn("GERCEK_ISIM", kodlar(L))
        self.assertIn("SATIR_SAYISI", {c for c, _ in af.kontrol_acik(beats(IYI[:4]), "t?", "K", "deniz")})
        self.assertIn("UZUNLUK", kodlar([IYI[0], "About 60 meters, according to NASA, if all the ice melted.", "Yes.", "Greenland holds 7 meters.", "NASA? What?"]))

    def test_kaynak_kurumu_isim_yasagina_takilmaz(self):
        self.assertNotIn("GERCEK_ISIM", kodlar())

    def test_aciklama_kaynak_satiri(self):
        r = {"beats": beats(), "title": af.ACIK_KONULAR["deniz"]["baslik"]}
        a = af.aciklama(r, "deniz")
        self.assertTrue(a.startswith(IYI[0]))
        self.assertIn("Sources:", a)
        self.assertIn("sealevel.nasa.gov", a)


class UretDuzenleTest(unittest.TestCase):
    def test_uret_kotuyu_yeniden_yazdirir(self):
        kotu = ["The sea will rise a lot."] + IYI[1:]
        cevaplar = [ham(kotu), ham(IYI)]
        istemler = []

        def llm(p):
            istemler.append(p)
            return cevaplar.pop(0)
        r = af.uret("deniz", llm, parse)
        self.assertTrue(r["ok"])
        self.assertEqual(r["deneme"], 2)
        self.assertIn("REJECTED", istemler[1])
        self.assertEqual(r["title"], af.ACIK_KONULAR["deniz"]["baslik"])        # baslik bizim (arama ifadesi)
        self.assertFalse(af.uret("deniz", lambda p: ham(["x"] + IYI[1:]), parse, deneme=2)["ok"])

    def test_duzenle(self):
        r = af.uret("deniz", lambda p: ham(), parse)
        yeni, s = af.duzenle(r, ("s", 3, "That would swallow coastlines, ports and whole river deltas."))
        self.assertEqual(s, [])
        self.assertIn("ports", yeni["beats"][2][2])
        y2, s2 = af.duzenle(r, ("s", 2, "About 99 meters, according to NASA, if all the ice melted."))
        self.assertIsNone(y2)
        self.assertTrue(s2)
        self.assertIsNone(af.duzenle(r, ("s", 6, "x"))[0])
        self.assertEqual(af.duzenle(r, ("k", "new card"))[0]["hookthumb"], "NEW CARD")


class EkranTest(unittest.TestCase):
    def test_ekran_yazisi_denetlenir_ve_duzenlenir(self):
        r = af.uret("deniz", lambda p: ham(), parse)
        yeni, s = af.duzenle(r, ("e", 3, "low cities at risk"))
        self.assertEqual(s, [])
        self.assertEqual(yeni["beats"][2][1], "LOW CITIES AT RISK")
        y2, s2 = af.duzenle(r, ("e", 3, "99 METERS UNDER"))               # ekranda kaynaksiz rakam
        self.assertIsNone(y2)
        self.assertIn("RAKAM_KAYNAK", {c for c, _ in s2})
        self.assertIsNone(af.duzenle(r, ("e", 9, "x"))[0])


class GunTest(unittest.TestCase):
    def ortam(self, cevaplar, script=None, sunucu=True):
        o = type("O", (), {})()
        o.cevaplar, o.cikti, o.render, o.izle = list(cevaplar), [], [], []
        d = {"yaz": lambda m="": o.cikti.append(str(m)), "gir": lambda p: o.cevaplar.pop(0), "llm": lambda p: script or ham(), "parse": parse,
             "sunucu_hazirla": lambda: None, "sunucu_bekle": lambda: sunucu,
             "render": lambda r, k: o.render.append((r, k)) or {"file": "v.mp4", "seconds": 45}, "izle": o.izle.append}
        return o, d

    class A:
        def __init__(self, konu):
            self.konu = konu

    def test_mutlu_yol_yukleme_yok(self):
        o, d = self.ortam(["evet"])
        self.assertEqual(ag.calistir(self.A("deniz"), d), 0)
        self.assertEqual(len(o.render), 1)
        self.assertEqual(o.render[0][1], "deniz")
        self.assertIn("YUKLENMEDI", "\n".join(o.cikti))
        self.assertNotIn("yukle", d)

    def test_hayir_iptal_ve_gecersiz_konu_ve_sunucu(self):
        o, d = self.ortam(["hayir"])
        self.assertEqual(ag.calistir(self.A("deniz"), d), 0)
        self.assertEqual(o.render, [])
        self.assertEqual(ag.calistir(self.A("yok"), d), 2)
        o2, d2 = self.ortam(["evet"], sunucu=False)
        self.assertEqual(ag.calistir(self.A("deniz"), d2), 2)
        self.assertEqual(o2.render, [])

    def test_ekran_komutu_gun_icinde(self):
        o, d = self.ortam(["e 3 LOW CITIES AT RISK", "evet"])
        self.assertEqual(ag.calistir(self.A("deniz"), d), 0)
        self.assertEqual(o.render[0][0]["beats"][2][1], "LOW CITIES AT RISK")

    def test_tamir_modu_gecersizde_evet_reddedilir(self):
        kotu = ham(["The sea will rise a lot."] + IYI[1:])
        o, d = self.ortam(["evet", "s 1 If all the ice melted, how high would oceans rise?", "evet"], script=kotu)
        self.assertEqual(ag.calistir(self.A("deniz"), d), 0)
        self.assertIn("KAPIDAN GECMEDI", "\n".join(o.cikti))
        self.assertIn("henuz kapidan gecmedi", "\n".join(o.cikti))
        self.assertEqual(len(o.render), 1)


if __name__ == "__main__":
    unittest.main()


class YasakKelimeTest(unittest.TestCase):
    def test_deniz_glacier_ve_suddenly_yasak(self):
        L = list(IYI)
        L[0] = "What happens if every glacier on Earth suddenly melts?"
        k = kodlar(L)
        self.assertIn("YASAK_KELIME", k)
        L[0] = "What happens if all the ice on Earth melts?"
        self.assertNotIn("YASAK_KELIME", kodlar(L))

    def test_prompt_notu(self):
        self.assertIn("NEVER say 'glaciers'", af.prompt_uret("deniz"))
        self.assertNotIn("glaciers", af.prompt_uret("robot"))
        self.assertIn("55-105 words", af.prompt_uret("robot"))
