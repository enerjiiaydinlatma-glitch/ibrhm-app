"""
AURA MOTORU - Sign Council'in gunluk otonom uretim hatti. Aura gundemi
KENDISI belirler, alt analiz ajanlarini sirayla calistirir, cikan her
seyi tek klasore koyar ve operatore net bir "sunu yayinla" listesi verir.
Yayin ve (varsayilan) Short YAYINLAMA insan onayinda kalir.

Alt ajanlar (her biri bagimsiz calisan bir modul):
  gundem.fetch_ai_headlines      - ham sinyal
  aura_editorial.run_editorial_plan - Aura: 5-eksen puanla -> konu + plan + studio
  make_episode_assets.build_ab   - 3 A/B baslik+thumbnail paketi
  make_topic_short.build         - ~100s kazanan-kalip Short
  make_leaderboard_short.build_leaderboard - siralama/guc-listesi Short (--leaderboard)
  analyze_channel.analyze        - (haftalik) kanal oruntusu -> icerik modeli
  analyze_video.analyze          - (2 gun sonra) retention tanisi

Guvenlik: --public ile yuklerken duyarlilik kapisi (sensitivity_gate) devrede -
gercek bir sirket/kisi hakkinda CIDDI iddia iceren Short otomatik yayinlanmaz,
private'a duser + "insan onayi gerekiyor" bayragi basilir.

Kullanim:
    python aura_engine.py                 # plan + kapaklar + Short (yuklemez)
    python aura_engine.py --short-upload   # + Short'u private yukle
    python aura_engine.py --short-upload --public   # + Short herkese acik
    python aura_engine.py --short-upload --public --leaderboard  # siralama formati
    python aura_engine.py --learn          # + analyze_channel (haftalik ogrenme)
    python aura_engine.py --plan-only      # sadece Aura'nin karari + plani
"""
import argparse
import datetime
import json
import os
import sys
import traceback

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_ROOT = os.path.join(HERE, "_engine")
VOICE_URL = os.getenv("AURA_VOICE_URL", "http://127.0.0.1:8124")


def _voice_up():
    try:
        import httpx
        r = httpx.get(f"{VOICE_URL}/health", timeout=4)
        return r.status_code == 200 and r.json().get("model_loaded")
    except Exception:
        return False


def _fresh_episode(max_age_days=4):
    """En yeni output/bolum_*.json max_age_days'ten yeni mi? Hot-take'in
    bayat bir tartismayi kirpmamasi icin (bolum uretimi ayri, zamanlanmamis)."""
    import glob
    files = glob.glob(os.path.join(HERE, "output", "bolum_*.json"))
    if not files:
        return False
    newest = max(os.path.getmtime(f) for f in files)
    return (datetime.datetime.now().timestamp() - newest) < max_age_days * 86400


def _add_pending_approval(video_id, title, reason, severity, entity):
    """Onay bekleyen (private yuklenmis, insan onayi gereken) Short'lari
    mission_control.py'nin okuyabilecegi bir kuyruga yazar - eskiden bu
    sadece konsola print ediliyordu, panelin veri kaynagi yoktu."""
    path = os.path.join(RUN_ROOT, "pending_approval.json")
    try:
        rows = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    except Exception:
        rows = []
    rows = [r for r in rows if r.get("video_id") != video_id]
    rows.append({
        "video_id": video_id, "title": title, "reason": reason,
        "severity": severity, "entity": entity,
        "date": datetime.date.today().isoformat(),
    })
    os.makedirs(RUN_ROOT, exist_ok=True)
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _step(name, fn):
    print(f"\n{'='*64}\n  ADIM: {name}\n{'='*64}")
    try:
        return fn()
    except SystemExit as e:
        print(f"  [!] {name} durdu: {e}")
    except Exception as e:
        print(f"  [!] {name} HATA: {e}")
        traceback.print_exc()
    return None


def _drop_time(hhmm=""):
    """'Koordineli dusum' icin gelecekteki bir yayin ani (ISO-8601 UTC). hhmm
    'HH:MM' yerel saat; verilmezse simdiden +3 saat. Gecmisse ertesi gune atar."""
    now = datetime.datetime.now()
    if hhmm and ":" in hhmm:
        h, m = (int(x) for x in hhmm.split(":")[:2])
        t = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if t <= now + datetime.timedelta(minutes=10):
            t += datetime.timedelta(days=1)
    else:
        t = now + datetime.timedelta(hours=3)
    return t.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(short_upload=False, public=False, learn=False, plan_only=False, leaderboard=False,
        hottake=False, evergreen=False, verdict=False, council_decides=False, drop=None,
        force=False):
    day = datetime.date.today().isoformat()
    run_dir = os.path.join(RUN_ROOT, day)
    os.makedirs(run_dir, exist_ok=True)
    result = {"date": day, "steps": {}}

    # GUNDE-BIR-VIDEO KILIDI (27 Eyl 2026: 26 Eylul'de elle yapilan bir telafi
    # calistirmasi + ayni gunun 18:00 zamanlanmis gorevi CAKISTI, ayni gun 2
    # video yuklendi - strateji karariyla celisti VE plan.json ikinci calisma
    # tarafindan ustune yazildi. Bugun zaten bir video yuklendiyse ikinci
    # calistirma SESSIZCE atlanir; kasitli ikinci video icin --force kullan.)
    # GUNDE-2-VIDEO KILIDI (Ekim 2026): sinir daily_limit.MAX_DAILY (=2). Sinira
    # ulasinca --force dahil yeni yukleme YAPILMAZ.
    from daily_limit import can_upload, MAX_DAILY
    _uploaded_flag = os.path.join(run_dir, ".uploaded_today.json")
    if short_upload:
        _ok, info = can_upload(_uploaded_flag, force=force)
        if not _ok:
            last = info.get("video_id", "?")
            print(f"[guard] Bugun ({day}) {info['count']}/{MAX_DAILY} video yuklendi "
                  f"(son: https://youtu.be/{last}  {info.get('ts', '?')})\n"
                  "[guard] Gunluk sinira ulasildi - YENI VIDEO URETILMIYOR (--force sert siniri asamaz).")
            return result

    # 0) OMURGA: aylik editoryal yay (birbiri uzerine insa olan 4 haftalik tema)
    #    + haftalik performans-ayrimi (gercek Analytics). Ikisi de editoryal
    #    karardan ONCE calisir ki Aura ayni gun taze veriyle secim yapsin.
    #    GUNDE-BIR-KEZ kilidi: 11 Eyl'den itibaren gunde 2 Short (2. slot ayni
    #    aura_engine.py'yi tekrar cagiriyor) - bu blok ayni gun ikinci kez
    #    calismasin (optimize/reference_mine'a bosuna 2. API/LLM turu).
    _housekeep_flag = os.path.join(RUN_ROOT, day, ".housekeeping_done")
    if not os.path.exists(_housekeep_flag):
        if datetime.date.today().day <= 3:
            def _arc():
                from editorial_arc import plan_month
                o = plan_month()
                return f"{o['month']}: " + " > ".join(w["theme"] for w in o["weeks"])
            _step("Aylik editoryal yay (4 haftalik tema)", _arc)
        if datetime.date.today().weekday() == 0:  # Pazartesi
            def _opt():
                from optimize_loop import report
                report(as_md=True)
                return "optimize.md yenilendi"
            _step("Optimize loop (haftalik performans ayrimi)", _opt)

            def _ref():
                from reference_mine import mine
                mine()
                return "reference_patterns.md yenilendi"
            _step("Referans kanal oruntu madenciligi", _ref)

            def _eng():
                from engagement_signal import analyze, write_md
                model, high = analyze()
                write_md(model, high)
                return "engagement_digest.md yenilendi"
            _step("Etkilesim sinyali (yorum+paylasim agirlikli)", _eng)
        open(_housekeep_flag, "w").close()

    # 1) Aura karar + plan
    from aura_editorial import run_editorial_plan, ask_aura_studio
    plan = _step("Aura gundemi seciyor + planliyor (5-eksen puanlama)", run_editorial_plan)
    if not plan:
        print("\nAura karar veremedi - motor durdu.")
        return
    plan["studio_verdict"] = _step("Aura studio'yu degerlendiriyor", ask_aura_studio)
    result["steps"]["plan"] = plan
    with open(os.path.join(run_dir, "plan.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    if plan_only:
        _print_checklist(result, run_dir, short=None, ab=None)
        return

    topic = plan["decision"]
    angle = plan["angles"][0] if plan.get("angles") else ""

    # 1b) LEDGER - tarihli yanlislanabilir tahmin + acik olanlari kapat
    #     (Aura'nin 6 Eylul evren analizi: yorumlayan degil, onceden soyleyen ol)
    def _ledger():
        from ledger import record_from_topic, resolve_pending, scorecard
        resolve_pending("")
        record_from_topic(topic, angle)
        try:
            from render_ledger_page import build as _render_ledger
            _render_ledger()  # docs/sign-council/track-record.html guncelle
        except Exception as e:
            print(f"    [ledger sayfasi render edilemedi: {type(e).__name__}]")
        return scorecard()
    result["steps"]["ledger"] = _step("Tahmin defteri (ledger)", _ledger)

    # 2) A/B kapaklar
    from make_episode_assets import build_ab
    ab = _step("3 A/B baslik+thumbnail paketi", lambda: build_ab(topic))
    result["steps"]["ab_packages"] = ab

    # 3) ~100s Short
    if not _voice_up():
        print(f"\n  [!] Ses sunucusu ({VOICE_URL}) KAPALI - once sign_council_voice.bat "
              "calistir. Short atlaniyor.")
        short = None
    elif leaderboard:
        # Siralama/guc-listesi formati (accessland.live kaniti: siralama gorseli
        # + "tahmin et, kaydet" CTA = kaydetme/paylasim). Haftada ~1 onerilir.
        # NOT: gunun tekil-konusu DEGIL, haftalik siralama temasi verilir -
        # build_leaderboard kendi canli sinyalinden 5'li sirayi kurar.
        from make_leaderboard_short import build_leaderboard
        lb_theme = "the AI companies, models and deals that moved this week"
        short = _step("Leaderboard Short (haftalik guc siralamasi)",
                      lambda: build_leaderboard(theme=lb_theme))
    elif evergreen:
        # Habere bagli OLMAYAN, zamana dayanikli mekanizma-anlatimi (wetubemevlana
        # slayt 4: viral degil evergreen arsiv). Bank: _engine/evergreen_bank.json.
        # BUG (27 Eyl 2026 kesfedildi): burada da _short_desc(plan) veriliyordu -
        # plan o GUNUN haber konusu (or. "OpenAI rogue agents..."), evergreen'in
        # KENDI konusuyla (or. "open weights") HICBIR ilgisi yok. Aciklamaya
        # yanlis/alakasiz bir iddia yapistiriyordu (2 canli video etkilendi,
        # elle duzeltildi). build_evergreen'in KENDI compose_description'i zaten
        # dogru - override VERME.
        from make_evergreen_short import build_evergreen
        short = _step("Evergreen Short (zamansiz mekanizma anlatimi)",
                      lambda: build_evergreen())
    elif verdict:
        # 'N flagged, M clean' liste formati (11 Eyl 2026 - Consumer Exposed
        # kalibi: dengeli liste tek-tarafli saldiridan daha guvenilir VE daha
        # az itibar/hukuk riski tasir). Haftalik tema, gunun tekil-konusu DEGIL.
        from make_leaderboard_short import build_verdict_list
        vc_theme = "AI safety and infrastructure claims making the rounds this week"
        short = _step("Verdict Check Short (N flagged, M clean)",
                      lambda: build_verdict_list(theme=vc_theme))
    elif council_decides:
        # 13 Eyl 2026: 3 BAGIMSIZ saglayiciya (Anthropic/OpenAI/Groq, ayri ayri)
        # ayni soru soruldu - ucu de "haber nisini birak, izleyicinin gercek
        # ikilemini 5 kalici kisilige karar verdirt" onerdi. Haber formatini
        # SILMEZ, paralel/ek format. Havuz: _engine/dilemma_bank.json.
        # Ayni gun kullanicinin kendi Aura'sinin onerdigi oylama mekanizmasi:
        # bir onceki Case'in yorumlarini sayip baskan/susturulani belirle,
        # SONRA bugunku Case'i o sonuca gore kur.
        from make_council_decides_short import build_council_decides, next_dilemma
        import council_standings as cs
        _step("Konsey oylamasi sayiliyor (bir onceki Case'in yorumlari)", cs.tally_and_update)
        dilemma = next_dilemma()
        short = _step("Council Decides Short (izleyici ikilemi)",
                      lambda: build_council_decides(dilemma))
    elif hottake and _fresh_episode(max_age_days=4):
        # En son bolumun en keskin catismasini 45sn Short'a cevirir (Aura
        # 5 Eylul kanal analizi #4: uzun tartisma 83 izlenme, keskin Short 300+).
        # 27 Eyl 2026: evergreen'deki ayni hatadan (bkz. yukarida) - hot-take
        # bolumun kendi konusunu isler, plan'in GUNUN haberiyle alakasi yok.
        from make_hottake_short import build_hottake
        short = _step("Hot-take Short (bolumden en keskin 45sn)",
                      lambda: build_hottake())
    else:
        if hottake:
            print("  [i] Taze bolum yok (>4 gun) - hot-take yerine tekil-konu kalibi.")
        from make_topic_short import build as build_short
        short = _step("~100s Short (kazanan kalip)",
                      lambda: build_short(topic, angle,
                                          desc_override=_short_desc(plan)))

    # 3a) YUKLEME + DUYARLILIK KAPISI + DAGITIM - HANGI FORMAT olursa olsun
    # (topic/leaderboard/evergreen/verdict/hottake) ayni sekilde uygulanir.
    # BUG (12 Eyl 2026 kesfedildi): bu blok daha once SADECE 'else' (tekil-
    # konu) dalinin icine gomuluydu - leaderboard/evergreen/verdict/hottake
    # gunlerinde Short SESSIZCE render edilip HIC YUKLENMIYORDU. If/elif
    # zincirinin DISINA alindi ki her format ayni yukleme+dagitim hattindan
    # gecsin.
    if short and short_upload:
        # DUYARLILIK KAPISI: gercek bir sirket/kisi hakkinda CIDDI iddia iceren
        # Short kullaniciya sormadan HERKESE ACIK yayinlanmaz (5 Eylul 2026
        # kullanici geri bildirimi). Boyle bir durumda private'a duser,
        # yorum atilmaz, checklist'te "INSAN ONAYI GEREKIYOR" basilir.
        gate = {"sensitive": False}
        if public:
            from sensitivity_gate import assess
            gate = _step("Duyarlilik kapisi (ciddi iddia kontrolu)",
                         lambda: assess(topic, short.get("script", ""), short.get("title", "")))
            gate = gate or {"sensitive": True, "reason": "kapi calismadi - guvenli taraf",
                            "entity": "", "severity": "high", "checked_by": "error"}
        short["sensitivity"] = gate
        effective_public = public and not gate.get("sensitive")
        # Koordineli dusum: video 'private' yuklenir, drop aninda otomatik
        # herkese acik olur -> tum aboneler ayni anda bildirim alir (ilk
        # saatteki yorum hizi = algoritma sinyali, bos-canli-yayin riski YOK)
        pub_at = _drop_time(drop) if (drop is not None and effective_public) else None

        def _up():
            from upload_youtube import upload_video
            from make_shorts import _sanitize_text
            try:
                return upload_video(short["file"], _sanitize_text(short["title"]),
                                    _sanitize_text(short["description"]), tags=short["tags"],
                                    privacy_status="public" if effective_public else "private",
                                    publish_at=pub_at)
            except Exception as e:
                msg = str(e).lower()
                if "invalid_grant" in msg or "expired or revoked" in msg or "refresherror" in msg:
                    # Token oldu - 4 gun boyunca sessizce trace basip is
                    # kaybettirdi (5-10 Eyl). Artik NET soyle, Short'u sakla.
                    short["auth_dead"] = True
                    print("\n" + "#" * 60)
                    print("  [!!] YOUTUBE TOKEN OLU - yukleme yapilamadi.")
                    print("       Short YERELDE hazir:", short["file"])
                    print("       COZUM: Google Cloud Console -> OAuth consent")
                    print("              screen -> PUBLISH APP (Testing modu 7 gunde")
                    print("              token'i olduruyor), sonra:")
                    print("              python youtube_auth.py")
                    print("       Sonra elle: python upload_youtube.py <dosya> --privacy public")
                    print("#" * 60)
                    return None
                raise
        short["video_id"] = _step("Short yukleniyor", _up)
        short["publish_at"] = pub_at
        # 12 Eyl 2026 kesfedilen bug: video_id sadece bellekte kaliyordu, yerel
        # .json'a hic yazilmiyordu - publish_pending.py zaten yayinlanmis
        # Short'lari "bekliyor" sanip DUPLICATE yukleme riski yaratiyordu.
        if short.get("video_id") and short.get("file"):
            try:
                jpath = short["file"].rsplit(".", 1)[0] + ".json"
                jd = json.load(open(jpath, encoding="utf-8"))
                jd["uploaded_id"] = short["video_id"]
                json.dump(jd, open(jpath, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"    [uploaded_id yerel json'a yazilamadi: {type(e).__name__}]")

        # 13 Eyl 2026 oylama mekanizmasi: bu Case'in video_id'sini kaydet ki
        # YARINKI Case bu videonun yorumlarini sayabilsin (bkz. council_standings.py).
        if short.get("format") == "council_decides" and short.get("video_id"):
            try:
                import council_standings as cs
                cs.set_last_video(short["video_id"])
            except Exception as e:
                print(f"    [oylama durumu kaydedilemedi: {type(e).__name__}]")

        if public and gate.get("sensitive") and gate.get("severity") == "critical":
            # 28 Eyl 2026 sahip karari: "yasal olarak hic bir sorun yasamamaliyiz
            # kimseyle" - suc ISLEDIGI + bunu KASITLI ORTBAS ETTIGI/yasadan
            # kactigi iddiasi (yalnizca guvenlik olayi degil) INSANA BILE
            # SORULMADAN reddedilir: video private KALIR, onay kuyruguna hic
            # girmez, yorum atilmaz. Sebebi seffaflik icin interventions.json'a
            # ve checklist'e yazilir.
            print("\n" + "!" * 60)
            print("  [!] OTOMATIK REDDEDILDI - iddia asiri ciddi (suc + kasitli ortbas/yasadan kacis)")
            print("      Video PRIVATE kaldi, ONAY KUYRUGUNA EKLENMEDI - insan onayina bile sorulmadi")
            print(f"      Taraf : {gate.get('entity') or '(belirsiz)'}")
            print(f"      Sebep : {gate.get('reason', '')}")
            if short.get("video_id"):
                print(f"      Video (herkese hicbir zaman acik olmayacak): https://youtu.be/{short['video_id']}")
                try:
                    from providers import _log_provider_event
                    _log_provider_event("critical_claim_auto_rejected",
                                        f"{short['video_id']}: {gate.get('entity', '')} - {gate.get('reason', '')}"[:300])
                except Exception:
                    pass
            print("!" * 60)
        elif public and gate.get("sensitive"):
            print("\n" + "!" * 60)
            print("  [!] INSAN ONAYI GEREKIYOR - Short PRIVATE olarak yuklendi")
            print(f"      Taraf : {gate.get('entity') or '(belirsiz)'}")
            print(f"      Sebep : {gate.get('reason', '')}")
            print(f"      Kontrol: {gate.get('checked_by', '?')} / siddet={gate.get('severity', '?')}")
            if short.get("video_id"):
                print(f"      Onayla: python publish_youtube.py {short['video_id']}")
                _add_pending_approval(short["video_id"], short.get("title", ""),
                                      gate.get("reason", ""), gate.get("severity", "?"),
                                      gate.get("entity", ""))
            print("!" * 60)
        elif effective_public and short.get("video_id") and not pub_at:
            def _comment():
                from growth_agent import post_engagement_comment
                return post_engagement_comment(short["video_id"], topic)
            _step("Etkilesim yorumu atiliyor", _comment)
        elif pub_at and short.get("video_id"):
            print(f"\n  [i] KOORDINELI DUSUM: {pub_at} otomatik yayina girecek.")
            print(f"      Yayin sonrasi yorum icin: python growth_agent.py "
                  f"{short['video_id']}  (drop aninda private, once yorum atilamaz)")

        # 3b) DAGITIM: arc oynatma listesine ekle (API, risksiz) +
        #     Reddit/Community paylasim taslaklari uret (_share_drafts_auto.md).
        #     Otomatik POST YOK - ban riski (kullanici hard kurali).
        if short.get("video_id") and not short.get("auth_dead"):
            def _route():
                from distribution_agent import route_to_playlist
                route_to_playlist(short["video_id"])
                return "arc listesine eklendi"
            _step("Oynatma listesine yonlendirme", _route)
        if not gate.get("sensitive"):
            def _drafts():
                from distribution_agent import generate_share_pack, ledger_receipt_draft
                m = dict(short)
                m["uploaded_id"] = short.get("video_id")
                generate_share_pack(meta=m)
                ledger_receipt_draft()
                return "_share_drafts_auto.md guncellendi"
            _step("Paylasim taslaklari (Community + Reddit)", _drafts)
    result["steps"]["short"] = short

    # 4) (opsiyonel) haftalik ogrenme
    if learn:
        from analyze_channel import analyze as analyze_ch
        result["steps"]["channel_model"] = _step(
            "Kanal oruntu analizi (icerik modeli)", lambda: analyze_ch(top_n=10, min_age_days=7))

    with open(os.path.join(run_dir, "run.json"), "w", encoding="utf-8") as f:
        json.dump({k: (v if isinstance(v, (dict, list, str, int, float, type(None))) else str(v))
                   for k, v in result["steps"].items()}, f, ensure_ascii=False, indent=2, default=str)
    _print_checklist(result, run_dir, short, ab)


def _short_desc(plan):
    hook = (plan.get("short_hooks") or [plan["decision"]])[0][:200]
    body = "Sign Council's five AIs debate it, unscripted. Full breakdown on the channel."
    try:
        from hashtag_agent import compose_description
        return compose_description(hook, body, plan["decision"],
                                   " ".join(plan.get("angles") or []))
    except Exception:
        return (f"{plan['decision'][:220]}\n\n{body}\n\n"
                "#AI #TechNews #ArtificialIntelligence #SignCouncil")


def _print_checklist(result, run_dir, short, ab):
    plan = result["steps"]["plan"]
    print("\n\n" + "#" * 64)
    print("  AURA MOTORU - BUGUNUN CIKTISI")
    print("#" * 64)
    print(f"\nKONU (Aura'nin karari):\n  {plan['decision']}\n")
    if plan.get("angles"):
        print("TARTISMA ACILARI (go_live.bat --agenda icin):")
        for a in plan["angles"]:
            print(f"  - {a}")
    if plan.get("short_hooks"):
        print("\nSHORT KANCALARI:")
        for h in plan["short_hooks"]:
            print(f"  - {h}")
    if plan.get("studio_note"):
        print(f"\nSTUDIO NOTU: {plan['studio_note']}")
    print(f"\nDOSYALAR: {run_dir}")
    if ab:
        print(f"  A/B kapaklar: assets/thumbnails/episode_*_[A|B|C].png  ({len(ab)} paket)")
    if short:
        vid = short.get("video_id")
        gate = short.get("sensitivity") or {}
        print(f"  Short: {short['file']}  (~{short['seconds']}s)")
        if vid:
            try:
                from daily_limit import record_upload
                record_upload(os.path.join(run_dir, ".uploaded_today.json"), vid)
            except Exception:
                pass
        if vid and gate.get("sensitive"):
            print(f"         YUKLENDI (PRIVATE - INSAN ONAYI GEREKIYOR) -> https://youtu.be/{vid}")
            print(f"         Sebep: {gate.get('reason', '')}")
            print(f"         Onayla: python publish_youtube.py {vid}")
        elif vid:
            print(f"         YUKLENDI -> https://youtu.be/{vid}")
        else:
            _hint = {"leaderboard": "python make_leaderboard_short.py --upload --public",
                     "verdict": "python make_leaderboard_short.py --verdict --upload --public",
                     "evergreen": "python make_evergreen_short.py --upload --public",
                     "hottake": "python make_hottake_short.py --upload --public",
                     "council_decides": "python make_council_decides_short.py --auto --upload --public"}.get(
                         short.get("format"), "python make_topic_short.py --auto --upload --public")
            print(f"         (yuklenmedi - --short-upload verilmediyse normal; elle yuklemek icin: {_hint})")
    sc = result["steps"].get("ledger")
    if isinstance(sc, dict):
        print(f"\nTAHMIN DEFTERI: {sc['accuracy']} isabet  |  {sc['open']} acik tahmin")
        try:
            from ledger import pending_resolution_shorts
            for p in pending_resolution_shorts():
                print(f"  [!] TAHMIN TUTTU - 'onceden soylemistik' Short'u yapilabilir:")
                print(f"      {p['claim'][:110]}")
        except Exception:
            pass

    print("\nSENIN ADIMLARIN:")
    print("  1. Bir A/B kapagi sec, YouTube'da yayinla / A/B testine koy")
    print("  2. sign_council_voice.bat calisiyorsa -> Sign Council - CANLI YAYIN")
    print("     (go_live.bat --agenda'yi yukaridaki acilardan biriyle guncelle)")
    print("  3. Short'u yayinla (yukaridaki komut)")
    print("  4. ~2 gun sonra: python analyze_video.py <link>  (Aura ogrensin)")
    print("#" * 64)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--short-upload", action="store_true", help="Short'u yukle (private)")
    ap.add_argument("--public", action="store_true", help="Short'u herkese acik yukle")
    ap.add_argument("--learn", action="store_true", help="+ analyze_channel (haftalik)")
    ap.add_argument("--plan-only", action="store_true", help="sadece Aura karari + plani")
    ap.add_argument("--leaderboard", action="store_true",
                    help="Short'u siralama/guc-listesi formatinda uret (haftada ~1)")
    ap.add_argument("--hottake", action="store_true",
                    help="Short'u en son bolumun en keskin 45sn'sinden uret")
    ap.add_argument("--evergreen", action="store_true",
                    help="Short'u habere bagli olmayan zamansiz mekanizma anlatimi olarak uret")
    ap.add_argument("--verdict", action="store_true",
                    help="Short'u 'N flagged, M clean' dengeli liste formatinda uret")
    ap.add_argument("--council-decides", action="store_true", dest="council_decides",
                    help="Short'u izleyici-ikilemi 'Konsey Karar Veriyor' formatinda uret "
                         "(13 Eyl 2026: haber nisi disinda, 3 bagimsiz AI danismaninin ortak onerisi)")
    ap.add_argument("--drop", nargs="?", const="", default=None, metavar="HH:MM",
                    help="Koordineli dusum: hemen public yerine belirtilen saatte "
                         "(veya +3s) otomatik yayina koy - tum abonelere ayni anda bildirim")
    ap.add_argument("--force", action="store_true",
                    help="Bugun zaten bir video yuklendiyse bile IKINCI bir video uret (gunde-1-video kilidini asar)")
    a = ap.parse_args()
    run(short_upload=a.short_upload, public=a.public, learn=a.learn, plan_only=a.plan_only,
        leaderboard=a.leaderboard, hottake=a.hottake, evergreen=a.evergreen,
        verdict=a.verdict, council_decides=a.council_decides, drop=a.drop, force=a.force)
