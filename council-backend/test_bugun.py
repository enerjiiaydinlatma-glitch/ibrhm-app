import datetime
import json
import os
import tempfile
import unittest

import bugun

NOW = datetime.datetime(2026, 10, 8, 12, 0, 0)


def art(title, url, seen="20261008T110000Z", **kw):
    d = {"title": title, "url": url, "seendate": seen}
    d.update(kw)
    return d


class PuanTest(unittest.TestCase):
    def test_birincil_ve_iddia_yuksek(self):
        a = bugun.puanla(art("Mistral Large 4 is state-of-the-art, outperforms rivals", "https://mistral.ai/news/x"), NOW)
        b = bugun.puanla(art("Some blog thoughts on AI", "https://randomblog.example.com/p"), NOW)
        self.assertGreater(a["puan"], b["puan"])
        self.assertIn("birincil kaynak", a["etiketler"])

    def test_cikar_catismasi_etiketi(self):
        a = bugun.puanla(art("Nvidia funds startup that buys its chips", "https://example.com/a"), NOW)
        self.assertIn("cikar catismasi (PRIORITY)", a["etiketler"])

    def test_riskli_baslik_engellenir(self):
        a = bugun.puanla(art("OpenAI secretly hid the data in a cover-up", "https://openai.com/a"), NOW)
        self.assertTrue(a["engel"])

    def test_taze_bonus(self):
        taze = bugun.puanla(art("x model", "https://e.com/1", "20261008T110000Z"), NOW)
        eski = bugun.puanla(art("x model", "https://e.com/1", "20261005T110000Z"), NOW)
        self.assertGreater(taze["puan"], eski["puan"])

    def test_sirala_engelliler_sonda_ve_tekrar_url_yok(self):
        m = [art("OpenAI secretly hid a cover-up of results", "https://openai.com/a"),
             art("Mistral beats rivals in own benchmark", "https://mistral.ai/n"),
             art("Mistral beats rivals in own benchmark", "https://mistral.ai/n")]
        r = bugun.sirala(m, NOW)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["url"], "https://mistral.ai/n")
        self.assertTrue(r[-1]["engel"])


class YayinTest(unittest.TestCase):
    def test_dogrula(self):
        n = len(bugun.YAYIN_KONTROL)
        self.assertTrue(bugun.yayin_dogrula("yayinla", n))
        self.assertTrue(bugun.yayin_dogrula("YAYINLA", n - 1))
        self.assertEqual(bugun.yayin_dogrula("YAYINLA", n), "")


HTML = "<html><head><title>Big Model</title></head><body>" + "".join(
    f"<p>Sentence number {i} is filler text for the page to be long enough to parse well.</p>" for i in range(20)
) + "<p>The model is state-of-the-art on finance tasks according to our internal benchmark evaluation.</p>" \
    "<p>Independent third party results are not included on this page at this time at all.</p></body></html>"


class KaynakTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._o = (bugun.ENGINE, bugun.KAYNAK_ADAY_YOL, bugun.GECMIS_YOL, bugun.kaynak_cek.ENGINE)
        bugun.ENGINE = self.d
        bugun.KAYNAK_ADAY_YOL = os.path.join(self.d, "kaynak_adaylar.json")
        bugun.GECMIS_YOL = os.path.join(self.d, "g.jsonl")

    def tearDown(self):
        bugun.ENGINE, bugun.KAYNAK_ADAY_YOL, bugun.GECMIS_YOL, bugun.kaynak_cek.ENGINE = self._o

    def test_analiz_ve_paket(self):
        r = bugun.kaynak_analiz("https://example.com/p", html=HTML)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["claim"])
        self.assertTrue(r["adaylar"])
        p = bugun.kaynak_paketle(r["onerilen"][:3], ["18 of 19"])
        self.assertTrue(p["ok"], p)
        pk = json.load(open(p["paket"], encoding="utf-8"))
        self.assertEqual(pk["url"], "https://example.com/p")
        self.assertTrue(pk["evidence"])
        self.assertTrue(open(os.path.join(self.d, "kaynak_son.txt")).read().endswith(os.path.basename(p["paket"])))

    def test_paket_adaysiz_hata(self):
        r = bugun.kaynak_paketle([1])
        self.assertFalse(r["ok"])

    def test_gecersiz_adres(self):
        self.assertFalse(bugun.kaynak_analiz("ftp://x")["ok"])

    def test_kisa_sayfa(self):
        self.assertFalse(bugun.kaynak_analiz("https://e.com", html="<p>kisa</p>")["ok"])


if __name__ == "__main__":
    unittest.main()


class PaylasimTest(unittest.TestCase):
    def test_taslak_kaynakli_ve_temiz(self):
        pk = {"title": "Mistral Large 4", "claim": "The model is state-of-the-art on finance tasks.", "url": "https://mistral.ai/news/x"}
        t = bugun.paylasim_taslak("reddit", pk, "VID123")
        self.assertTrue(t["ok"])
        self.assertIn("https://mistral.ai/news/x", t["govde"])
        self.assertIn("https://youtu.be/VID123", t["ilk_yorum"])
        self.assertEqual(t["uyari"], [])

    def test_riskli_iddia_uyari(self):
        pk = {"title": "Co", "claim": "They deliberately hid the results.", "url": "https://x.com/a"}
        t = bugun.paylasim_taslak("x", pk, "V")
        self.assertTrue(t["uyari"])

    def test_bilinmeyen_platform(self):
        self.assertFalse(bugun.paylasim_taslak("tiktok", {}, "V")["ok"])


RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Introducing Big Model, state-of-the-art on benchmarks</title><link>https://openai.com/index/big</link><pubDate>Thu, 08 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Data centre operators on board with energy rules</title><link>https://x.com/e</link><pubDate>Thu, 08 Oct 2026 09:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Gemini gets faster</title>
<link rel="alternate" href="https://deepmind.google/blog/g"/><updated>2026-10-08T08:30:00Z</updated></entry></feed>"""


class FeedTest(unittest.TestCase):
    def test_rss_ve_atom(self):
        r = bugun.feed_parse(RSS)
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["seendate"], "20261008T100000Z")
        a = bugun.feed_parse(ATOM)
        self.assertEqual(a[0]["url"], "https://deepmind.google/blog/g")
        self.assertEqual(a[0]["seendate"], "20261008T083000Z")

    def test_konu_suzgeci(self):
        self.assertTrue(bugun.konu_uyar("Introducing Big Model, state-of-the-art on benchmarks"))
        self.assertTrue(bugun.konu_uyar("Gemini gets faster"))
        self.assertFalse(bugun.konu_uyar("Data centre operators on board with energy rules"))
        self.assertFalse(bugun.konu_uyar("Rencore Launches New Multi - AI Governance Functionality"))

    def test_yenile_bir_akis_bozuksa_digerleri_calisir(self):
        d = tempfile.mkdtemp()
        o = (bugun.ENGINE, bugun.ADAY_YOL, bugun.gdelt_cek, bugun.feed_cek, bugun.FEEDS)
        try:
            bugun.ENGINE, bugun.ADAY_YOL = d, os.path.join(d, "a.json")
            bugun.FEEDS = ["https://openai.com/f", "https://bozuk.example/f"]
            bugun.gdelt_cek = lambda: (_ for _ in ()).throw(OSError("ag yok"))
            bugun.feed_cek = lambda u, **k: bugun.feed_parse(RSS) if "openai" in u else (_ for _ in ()).throw(OSError("x"))
            msg = bugun.gundem_yenile()
            g = bugun.gundem_oku()
            self.assertEqual(len(g["adaylar"]), 1)
            self.assertIn("OKUNAMADI", msg)
            self.assertIn("1/2", msg)
            self.assertIn("openai.com", g["adaylar"][0]["alan"])
        finally:
            bugun.ENGINE, bugun.ADAY_YOL, bugun.gdelt_cek, bugun.feed_cek, bugun.FEEDS = o
