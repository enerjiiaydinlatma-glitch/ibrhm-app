"""Konsey video ffmpeg yardimcilari (retention deneyi, 25 Eki 2026): konusma hizlandirma + bastaki sessizligi kirpma + acilis ses vurusu. Agir bagimliligi yok."""
import os
import subprocess

KONSEY_HIZ = 1.08          # retention deneyi (25 Eki 2026): konusma %8 hizli, bastaki sessizlik kirpilir


def _hizlandir(ap, oran=KONSEY_HIZ):
    """ap (mp3) icindeki bastaki sessizligi kirpar ve konusmayi 'oran' kadar hizlandirir (yerinde). Hata olursa dosya DEGISMEZ; basari -> True."""
    tmp = ap + ".tmp.mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", ap, "-filter:a",
                        f"silenceremove=start_periods=1:start_duration=0:start_threshold=-50dB,atempo={oran}", tmp],
                       check=True, capture_output=True)
        if os.path.getsize(tmp) < 500:
            raise RuntimeError("cok kucuk cikti")
        os.replace(tmp, ap)
        return True
    except Exception as e:
        print(f"    [hiz atlandi ({type(e).__name__})]")
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False


def _son_mix_komutu(joined, final, total, vurus=False, fade_in=0.4):
    """Son video: gorsel solma + zemin tinisi + (istege bagli) acilis SES VURUSU. -> ffmpeg arguman listesi (test edilebilir).
    vurus=True: t=0'da kisa alcak 'thump' + hava 'whoosh' (ilk 0,5 sn); fade_in=0 -> siyahtan acilis YOK (soguk acilis)."""
    v_fade = (f"fade=t=in:st=0:d={fade_in}," if fade_in and fade_in > 0 else "") + f"fade=t=out:st={total-0.5}:d=0.5"
    girdiler = ["-i", joined, "-f", "lavfi", "-i", f"sine=frequency=98:duration={total}",
                "-f", "lavfi", "-i", f"sine=frequency=147:duration={total}"]
    miks = (f"[va][bed]amix=inputs=2:duration=first:weights=1 1,loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    fx = ""
    if vurus:
        girdiler += ["-f", "lavfi", "-i", "sine=frequency=55:duration=0.5",
                     "-f", "lavfi", "-i", "anoisesrc=duration=0.5:color=pink:amplitude=0.6"]
        fx = ("[3:a]afade=t=out:st=0.05:d=0.45,aformat=sample_rates=44100:channel_layouts=stereo[th];"
              "[4:a]lowpass=f=1200,afade=t=in:st=0:d=0.04,afade=t=out:st=0.12:d=0.38,aformat=sample_rates=44100:channel_layouts=stereo[wh];"
              "[th][wh]amix=inputs=2:duration=longest:weights=1 0.7,volume=1.4[fx];")
        miks = "[va][bed][fx]amix=inputs=3:duration=first:weights=1 1 1,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    fc = (f"[0:v]{v_fade}[v];"
          f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo[va];"
          f"[1:a][2:a]amix=inputs=2:weights=1 0.5,"
          f"aformat=sample_rates=44100:channel_layouts=stereo[t];"
          f"[t]volume=0.10,afade=t=in:st=0:d=0.8,afade=t=out:st={total-1}:d=1[bed];"
          + fx + miks)
    return (["ffmpeg", "-y"] + girdiler + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-movflags", "+faststart", final])
