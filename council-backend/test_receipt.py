import copy, json, os, tempfile, unittest
import receipt as rc

S = [
 "On critical enterprise workloads, including cybersecurity, finance and law, we find it to be state-of-the-art among open models.",
 "On the Artificial Analysis Cyber Index, an independent evaluation of how well AI models find and fix security flaws in real software, it ranks among the top five models globally and leads open-weight models developed outside China",
 "It already achieves performance competitive with the strongest open-source models globally, while significantly outperforming any open-weight model developed in the US or Europe.",
 "ML4 was preferred in CAD and STEM, while performing on par or close to GLM-5.3 in finance and coding.",
 "Notably, we evaluated ML4 through third party evaluators (vals.ai) on representative tasks for both legal and financial tasks, finding the model exceeds GPT-6-Astra in both cases.",
]
PACKET = {"title": "Introducing Mistral Large 4 | Mistral", "url": "https://mistral.ai/news/mistral-large-4/",
          "all_sentences": S, "facts": [], "fetched_at": "2026-10-08T10:00:00"}
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "receipts", "mistral-large-4_2026-10-08.json"), encoding="utf-8"))


class Receipt(unittest.TestCase):
    def test_gercek_receipt_temiz(self):
        self.assertEqual(rc.verify_receipt(R, PACKET), [])

    def test_sayfada_olmayan_alinti_reddedilir(self):
        r = copy.deepcopy(R)
        r["beats"][1]["quotes"] = ["leads every open-weight model in the world"]
        iss = rc.verify_receipt(r, PACKET)
        self.assertTrue(any("BULUNAMADI" in i for i in iss))

    def test_uydurma_sayi_reddedilir(self):
        r = copy.deepcopy(R)
        r["beats"][3]["line"] = "It misses claims by 22 percent and {q1}."
        self.assertTrue(any("22" in i for i in rc.verify_receipt(r, PACKET)))

    def test_niyet_atfi_reddedilir(self):
        r = copy.deepcopy(R)
        r["beats"][0]["line"] = "Mistral deliberately hides the truth about {q1}."
        self.assertTrue(rc.verify_receipt(r, PACKET))

    def test_hukum_damgasi_zorunlu(self):
        r = copy.deepcopy(R)
        r["beats"][4]["stamp"] = "TOTAL FRAUD"
        self.assertTrue(any("damga" in i for i in rc.verify_receipt(r, PACKET)))

    def test_baslik_sirket_adi_icermeli(self):
        r = copy.deepcopy(R)
        r["title"] = "The Claim vs The Page"
        self.assertTrue(any("sirket" in i for i in rc.verify_receipt(r, PACKET)))

    def test_script_yapisi_ve_sesli_metin(self):
        sc = rc.to_script(R, "2026-10-08T10:00:00")
        self.assertEqual(len(sc["beats"]), 5)
        who, screen, line, spec = sc["beats"][0]
        self.assertIn('"state-of-the-art among open models"', line)
        self.assertEqual(spec["quotes"], ["state-of-the-art among open models"])
        self.assertIn("2026-10-06", spec["source"])
        self.assertIn("verbatim", sc["desc"])

    def test_kare_cizilir(self):
        try:
            import receipt_frame as rf
        except ImportError:
            self.skipTest("PIL yok")
        sc = rc.to_script(R)
        d = tempfile.mkdtemp()
        for i, (who, screen, line, spec) in enumerate(sc["beats"]):
            p = rf.render(spec, who, os.path.join(d, f"{i}.png"))
            self.assertTrue(os.path.getsize(p) > 5000)


if __name__ == "__main__":
    unittest.main()
