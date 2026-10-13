import json, os, tempfile, unittest
import kaynak_cek as kc
import source_check as sc

HTML = """<html><head><title>Introducing Mistral Large 4 | Mistral AI</title><style>.x{}</style><script>var a="state-of-the-art hidden";</script></head>
<body><nav>Research</nav><main><h1>Le Chonk</h1>
<div class="card"><p>Open-weight hybrid instruct-and-reasoning MoE with multimodal input; unifies instruction, reasoning, and agentic capabilities in a single model, state-of-the-art among open weights on cybersecurity, finance, and manufacturing, natively fluent in 160+ languages.</p></div>
<p>Trajectories from an internal set of cyber challenges. Tool calls and solve times grounded in actual runs.</p>
<h2>Human Evaluation</h2>
<p>We ran an internal evaluation in which expert annotators across coding, CAD, mathematics and physics compared Mistral Large 4 with GLM-5.3. ML4 was preferred in CAD and STEM, while performing on par or close to GLM-5.3 in finance and coding.</p>
<p>Notably, we evaluated ML4 through third party evaluators on representative tasks for both legal and financial tasks, finding the model exceeds GPT-6-Astra in both cases.</p>
<p>Evaluations judged by humans, conducted by a third party. Unrelated filler sentence number one here for length.</p>
<p>More filler sentence two for the parser minimum count requirement ok.</p><p>More filler sentence three for the parser minimum count requirement ok.</p>
<p>More filler sentence four for the parser minimum count requirement ok.</p><p>More filler sentence five for the parser minimum count requirement ok.</p>
<p>More filler sentence six for the parser minimum count requirement ok.</p><p>More filler sentence seven for the parser minimum count requirement ok.</p>
<p>More filler sentence eight for the parser minimum count requirement ok.</p><p>More filler sentence nine for the parser minimum count requirement ok.</p>
<p>More filler sentence ten for the parser minimum count requirement ok.</p><p>More filler sentence eleven for the parser minimum count requirement ok.</p>
<p>More filler sentence twelve for the parser minimum count requirement ok.</p><p>More filler sentence thirteen for the parser minimum count requirement ok.</p>
</main></body></html>"""


def packet(facts=None):
    title, lines = kc.parse_html(HTML)
    sents = kc.split_sentences(lines)
    keys = kc.DEFAULT_KEYS
    sel = [i for i, s in enumerate(sents) if kc.score(s, keys)[0] > 0]
    return kc.build_packet("https://mistral.ai/news/mistral-large-4/", title, sents, "state-of-the-art", keys, sel,
                           facts or [], "2026-10-08T10:00:00")


class Kaynak(unittest.TestCase):
    def test_parse_script_ve_style_atlanir(self):
        title, lines = kc.parse_html(HTML)
        self.assertIn("Mistral Large 4", title)
        self.assertFalse(any("hidden" in l for l in lines))

    def test_iddia_ve_kanit_bulunur(self):
        p = packet()
        self.assertIn("state-of-the-art among open weights", p["claim"])
        ev = " ".join(p["evidence"])
        self.assertIn("on par or close to GLM-5.3 in finance", ev)
        self.assertIn("third party evaluators", ev)

    def test_konu_ve_aci_uretilir(self):
        p = packet()
        self.assertTrue(p["topic"].startswith("Introducing Mistral Large 4"))
        self.assertNotIn('"', p["topic"])
        self.assertIn("verbatim", p["angle"])

    def test_birebir_alinti_gecer(self):
        p = packet()
        txt = 'The page says "performing on par or close to GLM-5.3 in finance and coding" about finance.'
        self.assertEqual(sc.check([txt], p), [])

    def test_uydurma_alinti_yakalanir(self):
        p = packet()
        iss = sc.check(['It states "Mistral locks every developer into its own cloud registry forever".'], p)
        self.assertTrue(any("alinti" in i for i in iss))

    def test_uydurma_sayi_yakalanir(self):
        p = packet()
        iss = sc.check(["Running it costs $40K monthly and 75% of teams struggle."], p)
        self.assertTrue(any("$40K" in i or "40" in i for i in iss))
        self.assertTrue(any("75" in i for i in iss))

    def test_operator_sayilari_gecer(self):
        p = packet(["Mistral Large 4 solved 18 of 19; GLM 5.2 16; Kimi K3 15"])
        self.assertEqual(sc.check(["It solved 18 of 19 challenges, GLM 5.2 got 16."], p), [])

    def test_yil_ve_tek_hane_serbest(self):
        p = packet()
        self.assertEqual(sc.check(["In 2026 there were 3 claims checked."], p), [])

    def test_sayfadaki_sayi_gecer(self):
        p = packet()
        self.assertEqual(sc.check(["It is fluent in 160+ languages."], p), [])



class TarihMuaf(unittest.TestCase):
    def test_iso_tarih_ve_url_yanlis_alarm_vermez(self):
        p = packet()
        txt = "Page published 2026-10-06, read 2026-10-08. Source: https://mistral.ai/news/mistral-large-4/ and mistral.ai/news/x-4"
        self.assertEqual(sc.check([txt], p), [])

    def test_gercek_sahte_sayi_yine_yakalanir(self):
        p = packet()
        self.assertTrue(sc.check(["Page published 2026-10-06 and it fails by 22%."], p))


if __name__ == "__main__":
    unittest.main()
