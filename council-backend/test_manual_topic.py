import unittest
import manual_topic as m
import claim_lint as cl


class ManualTopic(unittest.TestCase):
    def test_plan_yapisi(self):
        p = m.build_plan("Mistral Large 4 license: what the published terms say", "Quote clauses")
        for k in ("decision", "angles", "short_hooks", "studio_note", "council_pitches", "scoring_notes"):
            self.assertIn(k, p)
        self.assertTrue(p["manual"])

    def test_kisa_konu_reddedilir(self):
        with self.assertRaises(ValueError):
            m.build_plan("kisa")

    def test_niyet_atfi_isaretlenir(self):
        names = [n for n, _, _ in cl.lint("Mistral masks lock-in deliberately")]
        self.assertIn("NIYET ATFI", names)
        self.assertIn("NIYET ATFI", cl.BLOCKING)

    def test_rakam_engelleyici_degil(self):
        self.assertNotIn("RAKAM", cl.BLOCKING)

    def test_notr_baslik_temiz(self):
        self.assertEqual(cl.lint("What Mistral's License Actually Says"), [])


if __name__ == "__main__":
    unittest.main()
