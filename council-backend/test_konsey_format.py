import json
import os
import tempfile
import unittest

import konsey_format as kf

IYI = """aura | WHO PAYS FOR SHIPPING | Free shipping is never free. | a cardboard box on a doorstep at dusk
alpha | PRICE MOVES | Stores add the shipping cost into item prices. That's one for me. | a cash register receipt on a counter
beta | HOLD ON | Hold on. So I pay for shipping and they call it free? | a shopper frowning at a laptop screen
delta | SWITCHING SIDES | Actually... Beta, you're correct. The price just moves somewhere else. | a seesaw in an empty playground
gamma | CLEAR PRICES | Shoppers deserve a clear price. I do this too, honestly. I chase free shipping. | a stack of delivery boxes in a hallway
aura | PICK A TEAM | Team Alpha or Team Beta? Now tell me your guilty habit. | two doors, one red and one blue
TITLE: Is Free Shipping Really Free?
HOOKTHUMB: WHO PAYS FOR SHIPPING"""


def parse(raw):
    beats, title, ht = [], "", ""
    for ln in raw.splitlines():
        if ln.startswith("TITLE:"):
            title = ln.split(":", 1)[1].strip()
        elif ln.startswith("HOOKTHUMB:"):
            ht = ln.split(":", 1)[1].strip()
        elif "|" in ln:
            p = [x.strip() for x in ln.split("|")]
            beats.append((p[0], p[1], p[2], p[3] if len(p) > 3 else ""))
    return beats, title, ht


def kodlar(raw, **kw):
    b, t, h = parse(raw)
    return {k for k, _ in kf.kontrol(b, t, h, **kw)}


class KapiTest(unittest.TestCase):
    def test_iyi_senaryo_gecer(self):
        b, t, h = parse(IYI)
        self.assertEqual(kf.kontrol(b, t, h), [])

    def test_gercek_isim_yasak(self):
        self.assertIn("GERCEK_ISIM", kodlar(IYI.replace("Stores add", "Amazon adds")))

    def test_rakam_engellenir(self):
        self.assertTrue(any(k.startswith("LINT_RAKAM") for k in kodlar(IYI.replace("the shipping cost", "about 30% of the shipping cost"))))

    def test_niyet_atfi_engellenir(self):
        self.assertTrue(any(k.startswith("LINT_NIYET") for k in kodlar(IYI.replace("Hold on. So", "Hold on. That's a lie. So"))))

    def test_isaret_eksigi(self):
        self.assertIn("ALPHA_ISARET", kodlar(IYI.replace(" That's one for me.", "")))
        self.assertIn("BETA_ISARET", kodlar(IYI.replace("Hold on. So", "Wait. So")))
        self.assertIn("DELTA_ISARET", kodlar(IYI.replace("Actually... Beta, you're correct.", "Both sides matter.")))
        self.assertIn("GAMMA_ISARET", kodlar(IYI.replace(" I do this too, honestly.", "")))
        self.assertIn("KAPANIS_TAKIM", kodlar(IYI.replace("Team Alpha or Team Beta?", "What do you think?")))
        self.assertIn("KAPANIS_ITIRAF", kodlar(IYI.replace("Now tell me your guilty habit.", "Vote now.")))

    def test_baslik_ve_kanca(self):
        self.assertIn("BASLIK_40", kodlar(IYI.replace("Is Free Shipping Really Free?", "Is Free Shipping Really Free Or Just Priced In?")))
        self.assertIn("ILK_UZUN", kodlar(IYI.replace("Free shipping is never free.", "This week we look at why free shipping is never really free")))

    def test_sira_ve_satir_sayisi(self):
        self.assertEqual(kodlar("\n".join(IYI.splitlines()[:4])), {"SATIR_SAYISI"})
        self.assertIn("SIRA", kodlar(IYI.replace("beta | HOLD ON", "gamma | HOLD ON")))

    def test_acilis_tekrari(self):
        self.assertIn("ACILIS_TEKRAR", kodlar(IYI, gecmis_ilk=["Free shipping is odd", "Free shipping is cheap"]))


class OrnekTest(unittest.TestCase):
    def test_komut_icindeki_ornek_kapidan_gecer(self):
        b, t, h = parse(kf.ORNEK)
        self.assertEqual(kf.kontrol(b, t, h), [])
        self.assertIn(kf.ORNEK, kf.PROMPT.format(topic="x"))

    def test_baslik_duzelt(self):
        self.assertEqual(kf.baslik_duzelt("is free shipping really free"), "Is free shipping really free?")
        self.assertEqual(kf.baslik_duzelt("Free shipping is a story"), "Free shipping is a story")
        self.assertEqual(kf.baslik_duzelt("Why subscriptions pile up?"), "Why subscriptions pile up?")
        self.assertEqual(kf.baslik_duzelt(""), "")

    def test_uzun_satir_engellenir(self):
        uzun = IYI.replace("Stores add the shipping cost into item prices.", "Stores add the shipping cost into the item prices that you see on every single product page today.")
        self.assertIn("SATIR_UZUN", kodlar(uzun))


class SkorTest(unittest.TestCase):
    def setUp(self):
        self.yol = os.path.join(tempfile.mkdtemp(), "skor.json")

    def test_oy_yoksa_skor_yazilmaz(self):
        self.assertEqual(kf.skor_cumlesi(self.yol), "")
        b, _, _ = parse(IYI)
        self.assertEqual(kf.kapanisa_skor_ekle(b, self.yol)[-1][2], b[-1][2])

    def test_oy_eklenir_ve_kod_yazar(self):
        kf.oy_ekle("alpha", 7, self.yol)
        kf.oy_ekle("beta", 6, self.yol)
        self.assertEqual(kf.skor_cumlesi(self.yol), "Score: Alpha 7, Beta 6.")
        b, t, h = parse(IYI)
        b2 = kf.kapanisa_skor_ekle(b, self.yol)
        self.assertTrue(b2[-1][2].startswith("Score: Alpha 7, Beta 6. Team Alpha"))
        self.assertEqual(kf.kapanisa_skor_ekle(b2, self.yol)[-1][2], b2[-1][2])   # iki kez eklenmez
        self.assertEqual(kf.kontrol(b2, t, h), [])                                # skor kapiyi bozmaz

    def test_gecersiz_oy(self):
        with self.assertRaises(ValueError):
            kf.oy_ekle("gamma", 1, self.yol)
        with self.assertRaises(ValueError):
            kf.oy_ekle("alpha", -1, self.yol)

    def test_bozuk_dosya_sifir(self):
        with open(self.yol, "w") as f:
            f.write("{bozuk")
        self.assertEqual(kf.skor_oku(self.yol), {"alpha": 0, "beta": 0})


class UretTest(unittest.TestCase):
    def setUp(self):
        self.yol = os.path.join(tempfile.mkdtemp(), "skor.json")

    def test_ilk_kotu_ikinci_iyi(self):
        cevaplar = [IYI.replace("Stores add", "Amazon adds"), IYI]
        istemler = []

        def llm(p):
            istemler.append(p)
            return cevaplar[len(istemler) - 1]
        r = kf.uret("free shipping", llm, parse, self.yol)
        self.assertTrue(r["ok"])
        self.assertEqual(r["deneme"], 2)
        self.assertIn("REJECTED", istemler[1])
        self.assertIn("GERCEK_ISIM", istemler[1] + "GERCEK_ISIM")   # geri besleme sorun mesajini icerir
        self.assertIn("Amazon".lower(), istemler[1].lower())

    def test_komut_kanca_tetik_listesini_veriyor(self):
        import hook_gate
        for w in ("never", "just", "only", "not", "digit", "question mark"):
            self.assertIn(w, kf.PROMPT)
        # listedeki her kelime gercekten hook_gate'te tetik sayilir
        for w in "but not never why how wrong missing only just nobody everyone still versus worst best first last stop before after instead".split():
            self.assertTrue(hook_gate.TETIK.search(w), w)

    def test_iki_kez_kotu_uretilmez(self):
        r = kf.uret("free shipping", lambda p: IYI.replace("Stores add", "Amazon adds"), parse, self.yol)
        self.assertFalse(r["ok"])
        self.assertTrue(r["sorunlar"])

    def test_prompt_yasaklari_iceriyor(self):
        for s in ("Do NOT name any real company", "NO statistics", "NEVER attribute intent", "That's one for me.", "Hold on.",
                  "I do this too, honestly.", "Team Alpha or Team Beta?"):
            self.assertIn(s, kf.PROMPT)


if __name__ == "__main__":
    unittest.main()
