import unittest

import claim_lint as cl
import kaynak_cek
import receipt as receipt_mod
import receipt_olustur as ro
from source_check import corpus

KLAM = "Based on submitted workloads, at any moment in time we have outstanding requests for 2-3x more GPUs than are available."
SAYFA = [KLAM, "Like many labs, we have demand for GPU time that far exceeds supply.",
         "Occupancy on the cluster held steady at 98% before and after the change, with demand exceeding capacity by 2-3x in both periods.",
         "The vendor secretly hid the data from customers according to this page text."] + \
        [f"Filler sentence number {i} that pads the page text enough to look real." for i in range(20)]


def paket():
    return kaynak_cek.build_packet("https://huggingface.co/blog/allenai/impactful-scheduling", "Impactful scheduling for GPU clusters",
                                   SAYFA, "2-3x more GPUs", [], [1, 2], [], "2026-10-10T11:50:00")


class LintKaynakliTest(unittest.TestCase):
    def test_kaynaktaki_birebir_alinti_karsilastirma_sayilmaz(self):
        c = corpus(paket())
        txt = f'The claim, from Ai2\'s own page: "{KLAM.rstrip(".")}".'
        engel = [n for n, _, _ in cl.lint_kaynakli(txt, c) if n in cl.BLOCKING]
        self.assertEqual(engel, [])
        self.assertTrue([n for n, _, _ in cl.lint(txt) if n in cl.BLOCKING])     # duz lint eskisi gibi isaretler

    def test_bizim_kendi_karsilastirmamiz_hala_engellenir(self):
        c = corpus(paket())
        self.assertIn("KARSILASTIRMA/ETIKET", [n for n, _, _ in cl.lint_kaynakli("Ai2 has more GPUs than its rivals do.", c)])

    def test_kaynakta_olmayan_alinti_muaf_degildir(self):
        c = corpus(paket())
        txt = 'The page says "we have more GPUs than every other lab combined today".'
        self.assertIn("KARSILASTIRMA/ETIKET", [n for n, _, _ in cl.lint_kaynakli(txt, c)])

    def test_niyet_atfi_alintinin_icinde_de_engellenir(self):
        c = corpus(paket())
        txt = 'The page says "The vendor secretly hid the data from customers according to this page text".'
        self.assertIn("NIYET ATFI", [n for n, _, _ in cl.lint_kaynakli(txt, c)])


class ReceiptGpuTest(unittest.TestCase):
    EV = [SAYFA[1], SAYFA[2]]

    def test_ai2_receipt_kurulur_ve_tarih_bossa_okundu_yazar(self):
        pk = paket()
        pk["evidence"] = list(self.EV)
        pk["claim"] = KLAM
        r, sorun = ro.kur(pk, "Ai2", "GPU cluster scheduling", "", "PARTLY SUPPORTED", anahtar="2-3x more GPUs",
                          hukum_notu="Our reading: partly supported. The page repeats its figure and adds a utilization number, "
                                     "but shows no raw queue data. Is a self-reported number enough for you?")
        self.assertEqual(sorun, [])
        self.assertEqual(r["date_label"], "read")
        sc = receipt_mod.to_script(r, "2026-10-10T11:50:00")
        self.assertIn("read 2026-10-10", sc["beats"][0][3]["source"])
        self.assertNotIn("published", sc["beats"][0][3]["source"])
        self.assertIn("Page read 2026-10-10", sc["desc"])
        self.assertNotIn("Page published", sc["desc"])

    def test_tarih_verilirse_published(self):
        pk = paket()
        pk["evidence"] = list(self.EV)
        pk["claim"] = KLAM
        r, _ = ro.kur(pk, "Ai2", "", "2026-09-30", "SUPPORTED", anahtar="2-3x more GPUs")
        self.assertEqual(r["date_label"], "published")
        self.assertIn("published 2026-09-30", receipt_mod.to_script(r)["beats"][0][3]["source"])


if __name__ == "__main__":
    unittest.main()
