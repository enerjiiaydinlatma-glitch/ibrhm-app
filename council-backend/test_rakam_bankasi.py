import unittest

import konsey_format as kf
import konsey_konular
import rakam_bankasi as rb

T79 = "What if a quarter of Earth's ice melted?"
T29 = "What if the sea rose 20 centimeters?"
T1 = "Is free shipping really free?"


class BankaTest(unittest.TestCase):
    def test_her_olgunun_konusu_ve_kaynagi_var(self):
        idler = {k["id"] for k in konsey_konular.KONULAR}
        for o in rb.OLGULAR:
            self.assertTrue(o["url"].startswith("https://"), o["id"])
            self.assertTrue(o["sayilar"] and o["kaynak"], o["id"])
            self.assertIn(o["tur"], ("kaynak", "turetilmis"))
            self.assertTrue(set(o["konular"]) <= idler, o["id"])
            for n in o["sayilar"]:                      # olgu cumlesi kendi rakamini icermeli
                self.assertIn(n, o["olgu"], o["id"])

    def test_olgu_secimi(self):
        self.assertEqual({o["id"] for o in rb.olgular(T79)}, {"buz_toplam", "gronland", "buz_ceyrek", "deniz_1880"})
        self.assertEqual(rb.olgular(T1), [])
        self.assertEqual(rb.olgular("not in the pool"), [])

    def test_yasakli_rakamlar(self):
        self.assertEqual(rb.yasakli_rakamlar("The sea would rise 15 meters. Greenland alone is 7 meters.", T79), [])
        self.assertEqual(rb.yasakli_rakamlar("The sea would rise 40 meters.", T79), ["40"])
        self.assertEqual(rb.yasakli_rakamlar("It rises 7 meters, then 12 feet.", T29), ["12", "7"])      # 29'da gronland olgusu yok
        self.assertEqual(rb.yasakli_rakamlar("Sixty meters of water.", T79), ["sixty"])               # yazi ile kacirma
        self.assertEqual(rb.yasakli_rakamlar("Three fees and 4 bills.", T1), [])                      # kucuk sayim serbest
        self.assertEqual(rb.yasakli_rakamlar("That's 20 centimeters, not more.", T29), [])            # konunun kendi varsayimi
        self.assertEqual(rb.yasakli_rakamlar("Since 1880, 21 cm.", T29), ["21"])

    def test_prompt_bolumu(self):
        self.assertIn("60 meters", rb.prompt_bolumu(T79))
        self.assertIn("roughly", rb.prompt_bolumu(T79))
        self.assertIn("NO numbers of 10 or more", rb.prompt_bolumu(T1))

    def test_kaynak_satiri(self):
        self.assertEqual(rb.kaynak_satiri(T79, "Welcome to the show."), "")
        s = rb.kaynak_satiri(T79, "A quarter melts, the sea rises 15 meters.")
        self.assertIn("rough arithmetic", s)
        self.assertIn("https://sealevel.nasa.gov", s)
        self.assertNotIn("scientificamerican", s)
        self.assertEqual(rb.kaynak_satiri(T79, "price is 150 dollars"), "")                          # '15' parcasi 150'yi eslemez


class KapiTest(unittest.TestCase):
    def beats(self, kanca, kapanis="Team Alpha or Team Beta? What's your guilty habit?"):
        return [("aura", "X", kanca, ""), ("alpha", "X", "The sea climbs. That's one for me.", ""), ("beta", "X", "Hold on. Who moves first?", ""),
                ("delta", "X", "Actually... Beta, you're correct. Docks go first.", ""), ("gamma", "X", "Pack a bag early. I do this too, honestly. I never pack.", ""),
                ("aura", "X", kapanis, "")]

    def kodlar(self, beats, konu):
        return {k for k, _ in kf.kontrol(beats, "Ice melts?", "SEA RISES FAST", konu=konu)}

    def test_kaynaksiz_rakam_reddedilir_kaynakli_gecer(self):
        self.assertIn("RAKAM_KAYNAK", self.kodlar(self.beats("The sea could rise 40 meters, not less."), T79))
        self.assertNotIn("RAKAM_KAYNAK", self.kodlar(self.beats("The sea could rise 15 meters, not less."), T79))

    def test_konusuz_kontrol_buyuk_rakami_reddeder(self):
        self.assertIn("RAKAM_KAYNAK", self.kodlar(self.beats("Only 25 days, not more."), None))
        self.assertNotIn("RAKAM_KAYNAK", self.kodlar(self.beats("Only 3 fees, not more."), None))

    def test_uret_promptuna_olgular_girer(self):
        gorulen = []

        def llm(p):
            gorulen.append(p)
            return ""

        kf.uret(T79, llm, lambda raw: ([], "", ""), deneme=1)
        self.assertIn("VERIFIED FACTS", gorulen[0])
        self.assertIn("15 meters", gorulen[0])


if __name__ == "__main__":
    unittest.main()


class OnkosulTest(unittest.TestCase):
    def test_premise_olmadan_rakam_reddedilir(self):
        self.assertEqual(rb.onkosul_eksik("Melting ice raises water roughly 15 meters?", T79), ["buz_ceyrek"])
        self.assertEqual(rb.onkosul_eksik("A quarter of the ice melts. The sea rises roughly 15 meters.", T79), [])
        self.assertEqual(rb.onkosul_eksik("Welcome.", T79), [])
        self.assertEqual(rb.onkosul_eksik("In 2012 a person was teleported 143 kilometers.", "Would you step into a teleporter?"), ["isinlanma_143"])
        self.assertEqual(rb.onkosul_eksik("In 2012 a light particle crossed 143 kilometers.", "Would you step into a teleporter?"), [])

    def test_yer_sayimi_kaynaksiz(self):
        self.assertEqual(rb.yasakli_rakamlar("3 major cities will flood first.", T79), ["3 major cities"])
        self.assertEqual(rb.yasakli_rakamlar("Three fees and 4 bills.", T1), [])

    def test_kapi_ve_kanca_onkosulu(self):
        k = KapiTest().beats("Melting ice raises water roughly 15 meters?")
        self.assertIn("ONKOSUL_EKSIK", {c for c, _ in kf.kontrol(k, "Ice melts?", "SEA RISES FAST", konu=T79)})
        self.assertIn("ADAY_ONKOSUL", {c for c, _ in kf.kanca_gecerli("Melting ice raises water roughly 15 meters?", T79)})
        self.assertNotIn("ADAY_ONKOSUL", {c for c, _ in kf.kanca_gecerli("A quarter of ice means 15 meters, not 1.", T79)})
        self.assertIn("ADAY_RAKAM", {c for c, _ in kf.kanca_gecerli("3 major cities will flood first.", T79)})
