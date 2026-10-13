import datetime
import unittest

import haftalik_rapor as hr

BUGUN = datetime.date(2026, 10, 30)


def v(i, title, views, tarih="2026-10-14", comments=0):
    return {"id": f"v{i}", "title": title, "published": tarih, "views": views, "likes": 0, "comments": comments,
            "shares": 0, "retention": 60.0, "subs": 0, "hashtags": ["#Shorts", "#SignCouncil"]}


class RaporTest(unittest.TestCase):
    def test_kanca_tipi(self):
        self.assertEqual(hr.kanca_tipi("Is Free Shipping a Lie?"), "soru")
        self.assertEqual(hr.kanca_tipi("3 fees you never see"), "rakam")
        self.assertEqual(hr.kanca_tipi("Free shipping is not free"), "çelişki")
        self.assertEqual(hr.kanca_tipi("Subscriptions explained"), "diğer")

    def test_eski_donem_disarida(self):
        eski = v(1, "Old Turkish era video", 999, tarih="2026-09-01")
        yeni = v(2, "New era video", 10)
        self.assertEqual([x["id"] for x in hr.filtrele([eski, yeni])], ["v2"])
        self.assertEqual(len(hr.filtrele([eski, yeni], None)), 2)

    def test_veri_yetersizse_oneri_yok(self):
        m = hr.rapor([v(i, f"Topic {i}?", 10 * i) for i in range(1, 4)], now=BUGUN)
        self.assertIn("veri yetersiz", m)
        self.assertIn("Öneri üretilmedi", m)

    def test_oneri_n5_ile_gelir(self):
        vs = [v(i, f"{i + 2} hidden fees in one week", 300, tarih=f"2026-10-{14 + i % 3}") for i in range(6)]
        vs += [v(10 + i, f"Plain explanation number {i}", 50, tarih=f"2026-10-{14 + i % 3}") for i in range(6)]
        m = hr.rapor(vs, now=BUGUN)
        self.assertNotIn("veri yetersiz", m)
        self.assertIn("Deneme olarak öne al", m)

    def test_yorum_kelimeleri_metni_kopyalamaz(self):
        yorumlar = [{"video_id": "v1", "text": "Team Alpha is right, shipping fees are a scam"},
                    {"video_id": "v1", "text": "alpha wins again"}]
        kel = dict(hr.yorum_kelimeleri(yorumlar))
        self.assertEqual(kel["alpha"], 2)
        self.assertNotIn("the", kel)
        m = hr.rapor([], yorumlar, now=BUGUN)
        self.assertNotIn("is right, shipping", m)

    def test_tekrar_acilis(self):
        vs = [v(1, "Free shipping costs more", 1), v(2, "Free shipping costs you", 1), v(3, "Other topic here", 1)]
        self.assertEqual(hr.tekrar_acilislar(vs), [("free shipping costs", 2)])
        self.assertEqual(hr.acilis("Free shipping costs more"), "free shipping costs")


if __name__ == "__main__":
    unittest.main()
