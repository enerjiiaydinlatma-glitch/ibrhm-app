import os
import subprocess
import tempfile
import unittest

import konsey_video_arac as kva


def _ffmpeg_var():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        return True
    except Exception:
        return False


def _sure(yol):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", yol], capture_output=True, text=True)
    return float(r.stdout.strip())


class KomutTest(unittest.TestCase):
    def test_vurus_ve_fade_in_secenekleri(self):
        k = kva._son_mix_komutu("j.mp4", "f.mp4", 30.0, vurus=True, fade_in=0)
        fc = k[k.index("-filter_complex") + 1]
        self.assertNotIn("fade=t=in:st=0:d=0.4", fc)                 # soguk acilis: siyahtan acilis YOK
        self.assertIn("[fx]", fc)
        self.assertIn("anoisesrc", " ".join(k))
        k2 = kva._son_mix_komutu("j.mp4", "f.mp4", 30.0)
        fc2 = k2[k2.index("-filter_complex") + 1]
        self.assertIn("fade=t=in:st=0:d=0.4", fc2)
        self.assertNotIn("[fx]", fc2)
        self.assertNotIn("anoisesrc", " ".join(k2))


@unittest.skipUnless(_ffmpeg_var(), "ffmpeg yok")
class GercekFfmpegTest(unittest.TestCase):
    def test_son_mix_calisir_ve_sure_korunur(self):
        d = tempfile.mkdtemp()
        j, f = os.path.join(d, "j.mp4"), os.path.join(d, "f.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=size=270x480:rate=30:duration=4", "-f", "lavfi", "-i", "sine=frequency=300:duration=4",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", j], check=True, capture_output=True)
        for vurus, fi in ((True, 0), (False, 0.4)):
            subprocess.run(kva._son_mix_komutu(j, f, 4.0, vurus=vurus, fade_in=fi), check=True, capture_output=True)
            self.assertAlmostEqual(_sure(f), 4.0, delta=0.4)

    def test_hizlandir_sureyi_kisaltir_ve_hatada_dokunmaz(self):
        d = tempfile.mkdtemp()
        ap = os.path.join(d, "a.mp3")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=300:duration=5", ap], check=True, capture_output=True)
        once = _sure(ap)
        self.assertTrue(kva._hizlandir(ap, 1.25))
        self.assertLess(_sure(ap), once * 0.9)
        bozuk = os.path.join(d, "bozuk.mp3")
        open(bozuk, "wb").write(b"degil mp3")
        self.assertFalse(kva._hizlandir(bozuk))
        self.assertEqual(open(bozuk, "rb").read(), b"degil mp3")


if __name__ == "__main__":
    unittest.main()


class YardimciTest(unittest.TestCase):
    def test_tekrar_dene_basarili_ve_basarisiz(self):
        sayac, bekler = {"n": 0}, []

        def fn():
            sayac["n"] += 1
            if sayac["n"] < 3:
                raise RuntimeError("503")
            return "tamam"
        self.assertEqual(kva.tekrar_dene(fn, deneme=3, bekle=(1, 2), uyku=bekler.append, yaz=lambda m: None), "tamam")
        self.assertEqual(bekler, [1, 2])

        def hep():
            raise ValueError("kalici")
        bekler.clear()
        with self.assertRaises(ValueError):
            kva.tekrar_dene(hep, deneme=2, bekle=(1,), uyku=bekler.append, yaz=lambda m: None)
        self.assertEqual(bekler, [1])

    def test_satirlara_bol(self):
        olc = lambda t: len(t) * 10  # noqa: E731
        self.assertEqual(kva.satirlara_bol("aaa bbb ccc ddd", olc, 80), ["aaa bbb", "ccc ddd"])
        self.assertEqual(kva.satirlara_bol("", olc, 80), [])
        self.assertEqual(kva.satirlara_bol("uzunkelimeuzunkelime x", olc, 50), ["uzunkelimeuzunkelime", "x"])   # sigmayan kelime tek satirda kalir
        cok = kva.satirlara_bol("a b c d e f g h", olc, 10, max_satir=3)
        self.assertEqual(len(cok), 3)
        self.assertEqual(cok[-1].split()[-1], "h")                                                       # metin kaybolmaz
