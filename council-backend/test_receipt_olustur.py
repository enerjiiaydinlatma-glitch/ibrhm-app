import json
import os
import tempfile
import unittest

import kaynak_cek
import receipt as receipt_mod
import receipt_olustur as ro

CLAIM = ("FoundationPose, a foundation model for object pose estimation and tracking, now provides an agent-ready inference library "
         "that enables robots to perceive and track the position and orientation of objects up to 5.5x faster.")
EV1 = ("Magna is using NVIDIA Isaac ROS as a modular, GPU-accelerated foundation for robotic perception, synchronized data collection "
       "and NVIDIA Isaac GR00T model deployment, pairing it with Isaac Sim hardware-in-the-loop testing.")
EV2 = ("Powered by NVIDIA Jetson at the edge, the solution enables robots to adapt to parts that are not precisely positioned, "
       "reducing reliance on costly fixtures.")
EV3 = "The release is available now on GitHub for developers building perception pipelines today."


def paket(ev=(EV1, EV2), claim=CLAIM):
    sents = [claim, *ev] + [("Filler sentence number %d that pads the page text enough to be realistic." % i) for i in range(20)]
    return kaynak_cek.build_packet("https://blogs.nvidia.com/blog/isaac-ros-5-0/", "NVIDIA Isaac ROS 5.0", sents,
                                   "up to 5.5x faster", [], list(range(1, 1 + len(ev))), [], "2026-10-08T17:50:36")


class ParcaTest(unittest.TestCase):
    def test_birebir_alt_dize_ve_yarim_baglac_yok(self):
        for c in (CLAIM, EV1, EV2):
            q = ro.parca(c, "up to 5.5x faster" if c == CLAIM else "")
            self.assertIn(q, c)
            self.assertNotIn('"', q)
            self.assertNotIn(q.split()[-1].lower(), ro._BAGLAC)
            self.assertNotIn(q.split()[0].lower(), ro._BAGLAC)
        self.assertIn("5.5x faster", ro.parca(CLAIM, "up to 5.5x faster"))

    def test_kisa_cumle_aynen(self):
        self.assertEqual(ro.parca("A short sentence here."), "short sentence here")   # bastaki "A" yarim baglac olarak atilir


class KurTest(unittest.TestCase):
    def test_gecerli_receipt_dogrulamadan_gecer(self):
        r, sorun = ro.kur(paket(), "NVIDIA", "Isaac ROS 5.0", "2026-10-08", "NOT SHOWN ON THE PAGE", anahtar="up to 5.5x faster")
        self.assertEqual(sorun, [])
        self.assertEqual(len(r["beats"]), 4)
        self.assertEqual([b.get("stamp") for b in r["beats"]].count("NOT SHOWN ON THE PAGE"), 1)
        self.assertIn("NVIDIA", r["title"])
        self.assertEqual(receipt_mod.verify_receipt(r, paket()), [])

    def test_uc_kanit_bes_beat(self):
        r, sorun = ro.kur(paket((EV1, EV2, EV3)), "NVIDIA", "", "2026-10-08", "PARTLY SUPPORTED", anahtar="up to 5.5x faster")
        self.assertEqual(sorun, [])
        self.assertEqual(len(r["beats"]), 5)

    def test_kanit_secimi(self):
        r, _ = ro.kur(paket((EV1, EV2, EV3)), "NVIDIA", "", "2026-10-08", "SUPPORTED", kanit_idx=[2, 0], anahtar="up to 5.5x faster")
        self.assertIn("release is available", r["beats"][1]["quotes"][0])

    def test_hatalar(self):
        p = paket()
        self.assertIn("Hukum", ro.kur(p, "NVIDIA", "", "2026-10-08", "KESIN YALAN")[1][0])
        self.assertIn("Sirket", ro.kur(p, "", "", "2026-10-08", "SUPPORTED")[1][0])
        self.assertIn("En az 2", ro.kur(p, "NVIDIA", "", "2026-10-08", "SUPPORTED", kanit_idx=[0])[1][0])
        self.assertIn("iddia", ro.kur(paket(claim=""), "NVIDIA", "", "2026-10-08", "SUPPORTED")[1][0])

    def test_niyet_atfi_iceren_alinti_yazilmaz(self):
        kotu = "The vendor secretly hid the benchmark results from every customer who asked for them."
        r, sorun = ro.kur(paket((kotu, EV2)), "NVIDIA", "", "2026-10-08", "SUPPORTED", anahtar="up to 5.5x faster")
        self.assertIsNone(r)
        self.assertTrue(any("NIYET" in x or "niyet" in x.lower() for x in sorun), sorun)

    def test_yaz(self):
        r, _ = ro.kur(paket(), "NVIDIA", "Isaac ROS 5.0", "2026-10-08", "SUPPORTED", anahtar="up to 5.5x faster")
        d = tempfile.mkdtemp()
        ad = ro.yaz(r, d)
        self.assertEqual(ad, "nvidia-isaac-ros-5-0_2026-10-08.json")
        self.assertEqual(json.load(open(os.path.join(d, ad), encoding="utf-8"))["company"], "NVIDIA")


if __name__ == "__main__":
    unittest.main()
