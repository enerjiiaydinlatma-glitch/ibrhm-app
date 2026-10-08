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
        self._o = (bugun.ENGINE, bugun.KAYNAK_ADAY_YOL, bugun.GECMIS_YOL, bugun.kaynak_cek.ENGINE, bugun.AKTIF_YOL)
        bugun.AKTIF_YOL = os.path.join(self.d, "aktif.json")
        bugun.ENGINE = self.d
        bugun.KAYNAK_ADAY_YOL = os.path.join(self.d, "kaynak_adaylar.json")
        bugun.GECMIS_YOL = os.path.join(self.d, "g.jsonl")

    def tearDown(self):
        bugun.ENGINE, bugun.KAYNAK_ADAY_YOL, bugun.GECMIS_YOL, bugun.kaynak_cek.ENGINE, bugun.AKTIF_YOL = self._o

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

    def test_paket_yasam_dongusu_bir_paket_bir_uretim(self):
        self.assertEqual(bugun._son_paket(), "")          # eski/baska paket kullanilmaz
        r = bugun.kaynak_analiz("https://example.com/p", html=HTML)
        p = bugun.kaynak_paketle(r["onerilen"][:3], [])
        self.assertEqual(bugun._son_paket(), p["paket"])
        bugun.paket_kullanildi()
        self.assertEqual(bugun._son_paket(), "")           # ikinci uretim engellenir
        self.assertEqual(bugun._son_paket(kullanilmis=True), p["paket"])  # Paylas adimi yine okuyabilir

    def test_eski_kaynak_son_txt_yoksayilir(self):
        eski = os.path.join(self.d, "kaynak_eski.json")
        open(eski, "w").write("{}")
        open(os.path.join(self.d, "kaynak_son.txt"), "w").write(eski)
        self.assertEqual(bugun._son_paket(), "")

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


FILL = "".join(f"<p>Filler sentence number {i} that makes the page long enough to be parsed as a real article.</p>" for i in range(20))
SAYFA_IDDIALI = f"<html><title>T</title><body>{FILL}<p>Our model is state-of-the-art on every finance benchmark we evaluated internally.</p>" \
                "<p>Independent third party evaluation is planned for a later date this year.</p>" \
                "<p>The internal benchmark evaluation covers manufacturing and financial tasks only.</p>" \
                "<p>Results on finance tasks exceed the previous version according to our evaluation.</p></body></html>"
SAYFA_DUZ = f"<html><title>T</title><body>{FILL}<p>We are happy to announce a new governance feature for customers today.</p></body></html>"


class HazirlikTest(unittest.TestCase):
    def test_iddiali_sayfa_uygun(self):
        h = bugun.sayfa_hazirlik("https://x.com/a", html=SAYFA_IDDIALI)
        self.assertTrue(h["ok"], h)
        self.assertEqual(h["iddia_anahtar"], "state-of-the-art")
        self.assertGreaterEqual(h["kanit"], bugun.MIN_KANIT)

    def test_duz_duyuru_elenir(self):
        h = bugun.sayfa_hazirlik("https://x.com/a", html=SAYFA_DUZ)
        self.assertFalse(h["ok"])
        self.assertTrue(h["hata"])

    def test_kisa_sayfa_ve_hata(self):
        self.assertFalse(bugun.sayfa_hazirlik("https://x.com/a", html="<p>kisa</p>")["ok"])
        o = bugun.kaynak_cek.fetch
        try:
            bugun.kaynak_cek.fetch = lambda u: (_ for _ in ()).throw(OSError("x"))
            self.assertFalse(bugun.sayfa_hazirlik("https://x.com/a")["ok"])
        finally:
            bugun.kaynak_cek.fetch = o


SAYFA_KIYAS = f"<html><title>Productive, Durable: How AI Factories Maximize Return</title><body>{FILL}" \
              "<p>Productive, Durable: How AI Factories Maximize Return</p>" \
              "<p>Our new platform delivers up to 10x faster inference than the previous generation on internal benchmarks.</p>" \
              "<p>Independent third party evaluation is planned for a later date this year.</p>" \
              "<p>The internal benchmark evaluation covers manufacturing and financial tasks only.</p>" \
              "<p>Results on finance tasks exceed the previous version according to our evaluation.</p></body></html>"
SAYFA_SADECE_BASLIK = f"<html><title>Advances Agentic, Open Source Robotics Development</title><body>{FILL}" \
                      "<p>Advances Agentic, Open Source Robotics Development</p>" \
                      "<p>Independent third party evaluation is planned for a later date this year.</p>" \
                      "<p>The internal benchmark evaluation covers manufacturing and financial tasks only.</p>" \
                      "<p>Results on finance tasks exceed the previous version according to our evaluation.</p></body></html>"


class IddiaTespitTest(unittest.TestCase):
    def test_sayi_kiyas_iddiasi(self):
        h = bugun.sayfa_hazirlik("https://x.com/a", html=SAYFA_KIYAS)
        self.assertTrue(h["ok"], h)
        self.assertIn("10x faster", h["iddia"])
        self.assertIn(h["iddia_anahtar"], h["iddia"].lower())

    def test_baslik_iddia_sayilmaz(self):
        h = bugun.sayfa_hazirlik("https://x.com/a", html=SAYFA_SADECE_BASLIK)
        self.assertFalse(h["ok"], h)
        self.assertNotIn("Open Source Robotics", h["iddia"])


class GdeltTest(unittest.TestCase):
    def test_429_yeniden_dener_sonra_yedek_sorgu(self):
        import urllib.error
        cagri = []
        class R:
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return b'{"articles":[{"title":"x","url":"https://a.com"}]}'
        def fake(req, timeout=0):
            cagri.append(req.full_url)
            if len(cagri) == 1:
                raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, None)
            return R()
        o = bugun.urllib.request.urlopen
        try:
            bugun.urllib.request.urlopen = fake
            r = bugun.gdelt_cek()
        finally:
            bugun.urllib.request.urlopen = o
        self.assertEqual(len(r), 1)
        self.assertEqual(len(cagri), 2)   # ilk sorgu 400 -> yedek sorgu
