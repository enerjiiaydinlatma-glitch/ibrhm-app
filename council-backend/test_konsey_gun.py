import datetime
import unittest

import konsey_gun as kg
import test_konsey_format as T

HOOKS = "1: Free shipping is never free.\n2: Why buy 2 shirts for free shipping?\n3: Never skip the fine print.\n4: Only 1 item, 3 fees.\n5: Cheap is just late.\nPICK: 1"


def gelecek_saat(gun=2):
    tr = datetime.datetime.utcnow() + datetime.timedelta(days=gun, hours=3)
    return tr.strftime("%Y-%m-%d %H:%M")


class Args:
    def __init__(self, konu=1, kategori=None, saat=None):
        self.konu, self.kategori, self.saat = konu, kategori, saat


class Ortam:
    """Sahte bagimliliklar; her cagri kaydedilir."""
    def __init__(self, cevaplar, script=None, limit_ok=True, sunucu_ok=True):
        self.cevaplar = list(cevaplar)
        self.script = script or T.IYI
        self.limit_ok, self.sunucu_ok = limit_ok, sunucu_ok
        self.cikti, self.llm_istemleri, self.render_cagri, self.yukle_cagri, self.izle_cagri, self.kayit = [], [], [], [], [], []
        self.sunucu_baslatildi = 0

    def llm(self, prompt):
        self.llm_istemleri.append(prompt)
        return HOOKS if "5 DIFFERENT opening hooks" in prompt else self.script

    def sozluk(self):
        return {
            "yaz": lambda m="": self.cikti.append(str(m)), "gir": lambda p: self.cevaplar.pop(0),
            "llm": self.llm, "parse": T.parse,
            "render": lambda topic, r: self.render_cagri.append((topic, r)) or {"file": "v.mp4", "seconds": 30, "sabit_yorum": "pin"},
            "yukle": lambda meta, yayin: self.yukle_cagri.append((meta, yayin)) or ("VID9", []),
            "izle": lambda yol: self.izle_cagri.append(yol),
            "kullanilan": lambda: set(),
            "gunluk": lambda: (self.limit_ok, {"count": 0 if self.limit_ok else 2}),
            "sunucu_hazirla": lambda: self.sunucu_baslatildi.__class__ and None,
            "sunucu_bekle": lambda: self.sunucu_ok,
            "duyarlilik": lambda topic, r: {"sensitive": False, "severity": "none"},
            "kaydet": lambda topic, r: self.kayit.append(topic),
        }

    @property
    def metin(self):
        return "\n".join(self.cikti)


class AkisTest(unittest.TestCase):
    def test_mutlu_yol_zamanli(self):
        o = Ortam(["evet"])
        rc = kg.calistir(Args(saat=gelecek_saat()), o.sozluk())
        self.assertEqual(rc, 0)
        self.assertEqual(len(o.render_cagri), 1)
        self.assertEqual(o.render_cagri[0][0], "Is free shipping really free?")
        self.assertEqual(o.izle_cagri, ["v.mp4"])
        meta, yayin = o.yukle_cagri[0]
        self.assertTrue(yayin.endswith("Z"))
        self.assertIn("ZAMANLANDI", o.metin)
        self.assertEqual(o.kayit, ["Is free shipping really free?"])

    def test_saat_sorulur_ve_enter_zamansiz_ozel(self):
        o = Ortam(["evet", ""])
        self.assertEqual(kg.calistir(Args(), o.sozluk()), 0)
        self.assertIsNone(o.yukle_cagri[0][1])
        self.assertIn("OZEL, zamanlanmadi", o.metin)

    def test_hatali_saat_tekrar_sorulur(self):
        o = Ortam(["evet", "yarin aksam", gelecek_saat()])
        self.assertEqual(kg.calistir(Args(), o.sozluk()), 0)
        self.assertEqual(len(o.yukle_cagri), 1)
        self.assertIn("Saat bicimi", o.metin)

    def test_uc_hatali_saat_yuklemez(self):
        o = Ortam(["evet", "x", "y", "z"])
        self.assertEqual(kg.calistir(Args(), o.sozluk()), 0)
        self.assertEqual(o.yukle_cagri, [])
        self.assertIn("yukleme yapilmadi", o.metin.lower())

    def test_hayir_saatte_yuklemez(self):
        o = Ortam(["evet", "hayir"])
        kg.calistir(Args(), o.sozluk())
        self.assertEqual(o.yukle_cagri, [])
        self.assertEqual(len(o.render_cagri), 1)           # video yine de uretilmis

    def test_senaryoyu_reddedince_hicbir_sey_uretilmez(self):
        o = Ortam(["hayir"])
        self.assertEqual(kg.calistir(Args(saat=gelecek_saat()), o.sozluk()), 0)
        self.assertEqual((o.render_cagri, o.yukle_cagri, o.kayit), ([], [], []))

    def test_baska_kanca_secilince_yeniden_yazar(self):
        o = Ortam(["1", "evet"])
        kg.calistir(Args(saat=gelecek_saat()), o.sozluk())
        senaryo_istemleri = [p for p in o.llm_istemleri if "5 DIFFERENT" not in p]
        self.assertEqual(len(senaryo_istemleri), 2)
        self.assertIn("PACKAGED HOOK", senaryo_istemleri[1])
        self.assertEqual(len(o.render_cagri), 1)

    def test_kapidan_gecmeyen_senaryo_uretilmez(self):
        o = Ortam([], script=T.IYI.replace("Stores add", "Amazon adds"))
        self.assertEqual(kg.calistir(Args(saat=gelecek_saat()), o.sozluk()), 2)
        self.assertEqual((o.render_cagri, o.yukle_cagri), ([], []))
        self.assertIn("KAPIDAN GECMEDI", o.metin)

    def test_gunluk_sinirda_hic_baslamaz(self):
        o = Ortam([], limit_ok=False)
        self.assertEqual(kg.calistir(Args(), o.sozluk()), 0)
        self.assertEqual(o.llm_istemleri, [])
        self.assertIn("Gunluk sinira", o.metin)

    def test_ses_sunucusu_hazir_degilse_video_uretilmez(self):
        o = Ortam(["evet"], sunucu_ok=False)
        self.assertEqual(kg.calistir(Args(saat=gelecek_saat()), o.sozluk()), 2)
        self.assertEqual(o.render_cagri, [])
        self.assertIn("URETILMEDI", o.metin)

    def test_gecersiz_konu_numarasi(self):
        o = Ortam([])
        self.assertEqual(kg.calistir(Args(konu=999), o.sozluk()), 2)
        self.assertEqual(o.llm_istemleri, [])


class YardimciTest(unittest.TestCase):
    KONULAR = [{"id": 1, "konu": "A?", "kategori": "para"}, {"id": 2, "konu": "B?", "kategori": "gelecek"}, {"id": 3, "konu": "C?", "kategori": "gelecek"}]

    def test_sonraki_konu_onceligi_ve_kullanilan(self):
        self.assertEqual(kg.sonraki_konu(set(), None, self.KONULAR, [3, 1])["id"], 3)
        self.assertEqual(kg.sonraki_konu({"c?"}, None, self.KONULAR, [3, 1])["id"], 1)
        self.assertEqual(kg.sonraki_konu({"c?", "a?"}, None, self.KONULAR, [3, 1])["id"], 2)
        self.assertIsNone(kg.sonraki_konu({"a?", "b?", "c?"}, None, self.KONULAR, []))

    def test_sonraki_konu_kategori(self):
        self.assertEqual(kg.sonraki_konu(set(), "gelecek", self.KONULAR, [1])["id"], 2)
        self.assertIsNone(kg.sonraki_konu(set(), "yok", self.KONULAR, []))

    def test_gercek_havuzda_ilk_oneri(self):
        self.assertEqual(kg.sonraki_konu(set())["id"], 1)

    def test_sunucu_hazirla_yalniz_kapaliysa_baslatir(self):
        sayac = []
        self.assertFalse(kg.sunucu_hazirla(lambda: True, lambda: sayac.append(1), lambda m: None))
        self.assertEqual(sayac, [])
        self.assertTrue(kg.sunucu_hazirla(lambda: False, lambda: sayac.append(1), lambda m: None))
        self.assertEqual(sayac, [1])

    def test_sunucu_bekle(self):
        t = [0.0]
        def saat():
            return t[0]
        def uyu(n):
            t[0] += n
        durumlar = iter([False, False, True])
        self.assertTrue(kg.sunucu_bekle(lambda: next(durumlar), 30, 2, saat, uyu))
        self.assertFalse(kg.sunucu_bekle(lambda: False, 10, 2, saat, uyu))


if __name__ == "__main__":
    unittest.main()
