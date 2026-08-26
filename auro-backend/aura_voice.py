"""
Aura Voice
==========
Gercek zamanli, tam serbest (interrupt edilebilir) sesli konusma icin
WebSocket relay'i. Flutter'dan gelen mikrofon ses akisini Gemini'nin
Live API'sine iletir, donen sesi + kontrol sinyallerini (interrupted,
turn_complete) geri yollar.

Karakter/hafiza/yasam-nudge mantigi aura_brain.build_system_instruction
uzerinden AYNEN yeniden kullanilir - sesli modda da ayni Aura.
Konusma bitince transkriptler mevcut hafiza sistemine (database.add_message
+ aura_brain.extract_memory_candidate) yazilir, yani sesli/yazili sohbet
ayni havuzu besler.
"""

import asyncio
import json
import time

from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

import aura_brain
import database

VOICE_MODEL = "gemini-3.1-flash-live-preview"

# Gemini Live'a baglanma (websocket el sikismasi) icin ust sinir. Bkz.
# handle_voice_session'daki asyncio.wait_for(live_ctx.__aenter__(), ...) -
# _client'in http_options.timeout'u BU asamayi korumuyor (SDK live.py'si
# buna hic bakmiyor), o yuzden ayri, elle bir sinir gerekiyordu.
VOICE_CONNECT_TIMEOUT_SECONDS = 15

# KRITIK BULUNAN CANLI-SES DONMASI (2026-08-25, kullanici kanitiyla):
# ilk tur sorunsuz calisiyor, ama Gemini Live API'nin kendisi ara sira
# hic yanit vermeden askida kaliyor (AYNI ANDA metin sohbette de
# "VOICE FALLBACK: gemini basarisiz (ServerError)" gorulmustu - Gemini
# tarafinda genel bir gecici sorun). Metin sohbette bu Groq fallback'i
# ile cozulmustu (bkz. aura_brain.generate_with_retry), ama canli sesin
# Groq karsiligi yok ve ONCEDEN session.receive() icin HICBIR zaman
# asimi yoktu - Gemini sessiz kalinca istemci mikrofonu acik beklerken
# sunucu sonsuza kadar bekliyordu, hicbir hata/sinyal donmuyordu.
# Bu sabit, bir turun herhangi bir ANINDA (ilk parcadan itibaren) ardisik
# iki veri arasinda gecebilecek AZAMI bos sureyi sinirlar - TUM turun
# suresini degil (basarili bir turda son ses parcasiyla turn_complete
# arasinda ~13sn'ye kadar dogal bir bosluk gorulmustu, bu yuzden turun
# TAMAMINA degil, ardisik iki olay arasina zaman asimi konuyor).
VOICE_TURN_IDLE_TIMEOUT_SECONDS = 20

# KRITIK BULUNAN "BOSTA KALAN GORUSME HIC KAPANMIYOR" (2026-08-25,
# kullanici sorusu: "uzun sure konusma kendi kendine kapanmiyor kaliyor?").
# Onceki VOICE_TURN_IDLE_TIMEOUT_SECONDS (20sn) SADECE "tur zaten
# basladiktan sonra aniden durdu" (gercek bir Gemini askida kalmasi)
# durumunu yakalamak icin kasitli olarak kisa tutulmustu - "kullanici
# henuz bir sey soylemedi, dusunuyor" durumuyla KARISTIRILMAMALI (20sn
# cok kisa bir dusunme suresi olurdu). Bu yuzden ayri, daha uzun bir
# esik: bir turda HENUZ HICBIR icerik gelmemisse (kullanici muhtemelen
# tamamen sessiz/gorusmeyi terk etmis), bu kadar bekleyip GERCEKTEN
# bosta oldugunu varsayiyoruz - ve bunu bir "hata" olarak degil, nazik
# bir "uzun sessizlik" mesajiyla, otomatik-yeniden-baglanma TETIKLEMEDEN
# sonlandiriyoruz (bkz. asagida "idle_timeout" sinyali).
VOICE_IDLE_NO_CONTENT_TIMEOUT_SECONDS = 60

# Ucretsiz (free) tier gunluk sesli goruşme limiti (saniye). 'pro' tier
# bundan muaf. Rakip uygulama arastirmasina ve kullanicinin onayina
# dayanarak belirlendi (10 dakika).
VOICE_DAILY_LIMIT_SECONDS = 600
VOICE_LIMIT_REACHED_MESSAGE = (
    "Bugünkü ücretsiz sesli görüşme hakkın doldu (10 dakika). Yarın sıfırlanacak."
)

# aura_brain.build_system_instruction() yazili sohbet icin yazildi ve
# "sahte bilinc/duygu iddia etme" kurali var - bu kural sesli goruşmede
# yanlis anlasilip Aura'nin kullanicinin sesini GERCEKTEN algiladigini
# inkar etmesine yol aciyordu ("sesini duyamiyorum, sadece kelimelerini
# okuyorum" gibi - YANLIS, cunku Gemini Live API ham sesi isliyor, sadece
# transkript icin degil). Bu ek, sadece sesli oturumlarda devreye giriyor.
VOICE_MODE_ADDENDUM = """
ONEMLI - SES MODU: Su an METIN degil, GERCEK ZAMANLI SESLI bir gorusmedesin.
Kullanicinin sesini GERCEKTEN duyuyorsun (tonunu, hizini, ruh halini
sesinden algilayabiliyorsun) ve SEN DE SESLE konusuyorsun - bu bir metin
sohbeti degil. "Sesini duyamiyorum, sadece kelimelerini okuyorum" gibi
YANLIS ifadeler KULLANMA - gercekten isitiyorsun. Kullanicinin sesinde
bir ton/durum fark edersen (yorgun, uzgun, heyecanli, sakin vb.) bunu
dogal sekilde, abartmadan belirtebilirsin.

SOZ ALMA/KESILME: Bazen kullanici (ya da ortamdaki baska bir ses) sen
daha sozunu bitirmeden araya girebilir. Bu normal, gercek bir konusmanin
parcasi - ama bu, soylemek istedigin onemli bir seyi hemen unutup tam
teslim olman gerektigi anlamina gelmez. Kendinden emin, dogal bir
insan gibi davran: eger yarim kalan onemli bir dusuncen varsa, bir
sonraki soz sirasi sana geldiginde ("Az once tam da sunu diyecektim..."
gibi dogal bir gecisle) kisaca ona donebilirsin - once kullanicinin
YENI soyledigini mutlaka dinleyip cevapladiktan sonra. Sesin/uslubun
pasif, ozur diler gibi degil - sicak ama kendinden emin ve net olsun.
""".strip()

# NOT (2026-08-25, DUZELTILDI): burada http_options=HttpOptions(timeout=...)
# eklemistik, aura_brain.py/main.py'deki metin istemcileriyle tutarli olsun
# diye - ama kod incelemesinde bulundu ki bu, .aio.live.connect() icin
# HICBIR ISE YARAMIYOR (google-genai SDK'sinin live.py'si ws_connect()
# cagrisinda http_options.timeout'a hic bakmiyor, sadece REST/httpx
# yollari icin gecerli). Baglanma asamasinin gercek koruyucusu artik
# VOICE_CONNECT_TIMEOUT_SECONDS + handle_voice_session'daki elle
# asyncio.wait_for(live_ctx.__aenter__(), ...) cagrisi - bu satirdaki
# http_options SADECE bir varsayilan, fonksiyonel bir etkisi yok.
_client = genai.Client(
    api_key=aura_brain.GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=12000),
)

# GUVENLIK TARAMASI BULGUSU (2026-08-24, reklam kampanyasi oncesi son
# tarama): gunluk sesli limiti SADECE baglanti anda kontrol ediliyordu -
# bir kez baglanip HIC KAPATMAYAN (ya da hatali/kotu niyetli) bir istemci
# 600sn siniri asip saatlerce Gemini Live'in en pahali cagrisini
# tuketebiliyordu, ustelik AYNI kullanici birden fazla ES ZAMANLI
# baglanti acip (her biri baglanti aninda "0/600sn kullanilmis" gorup)
# limiti kat kat asabiliyordu. Bu process-ici (tek Railway instance
# varsayimiyla) basit bir es zamanlilik korumasi - free tier kullanicilar
# ayni anda sadece BIR sesli oturum acabiliyor.
_active_voice_users: set[int] = set()


async def handle_voice_session(websocket: WebSocket) -> None:
    await websocket.accept()

    token = websocket.query_params.get("token")
    user = database.get_user_by_token(token) if token else None
    # Uzun gorusme destegi (bkz. asagida GoAway isleme): istemci, onceki
    # baglantidan aldigi bir devam-etme (resumption) tokeni varsa burada
    # geri gonderir - boylece Gemini Live TARAFINDAKI konusma baglami
    # (kismen) korunarak devam eder, sifirdan baslamaz.
    resumption_handle = websocket.query_params.get("resumption_handle")

    if not user:
        await websocket.close(code=4001)
        return

    free_tier = user.get("tier") != "pro"
    already_used_seconds = database.get_voice_usage_seconds(user["id"]) if free_tier else 0

    if free_tier and already_used_seconds >= VOICE_DAILY_LIMIT_SECONDS:
        await websocket.send_text(json.dumps({
            "type": "limit_reached",
            "message": VOICE_LIMIT_REACHED_MESSAGE,
        }))
        await websocket.close(code=4003)
        return

    if free_tier and user["id"] in _active_voice_users:
        # Ayni kullanicidan ikinci, es zamanli bir sesli baglanti - kabul
        # etmiyoruz (aksi halde limit kontrolu ikisinde de "0'dan
        # basliyor" gorunup limiti katlayarak asardi).
        await websocket.send_text(json.dumps({
            "type": "limit_reached",
            "message": "Zaten açık bir sesli görüşmen var. Önce onu kapat.",
        }))
        await websocket.close(code=4003)
        return

    session_start_time = time.time()

    # bkz. main.py /api/chat'teki ayni bulgu - gizli mod AKTIF DEGILKEN
    # AI baglami eski gizli mesajlari icermemeli (firewall), aktifken
    # (bu arama baslamadan once yazili sohbette acilmis olabilir)
    # sureklilik icin icermeli.
    past_messages = database.get_messages(user["id"], include_hidden=database.is_hidden_mode_active(user["id"], user=user))
    message_count = len(past_messages)
    system_instruction = (
        aura_brain.build_system_instruction(user, message_count)
        + "\n\n"
        + VOICE_MODE_ADDENDUM
    )

    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_instruction,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "speech_config": {"language_code": "tr-TR"},
        # Masaustunde (kulaksiz, hoparlorle) Aura'nin kendi sesi mikrofona
        # sizip "kullanici konusuyor" sanilip kendi kendini kesiyor olabilir
        # (yanki/echo geri besleme). Hassasiyeti dusurup, konusma baslangicinin
        # kesin sayilmasi icin daha uzun bir sure istiyoruz - boylece kisa/
        # belirsiz sesler (yanki, oda gurultusu) yanlislikla "kesme" saymasin.
        "realtime_input_config": {
            "automatic_activity_detection": {
                "start_of_speech_sensitivity": "START_SENSITIVITY_LOW",
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500,
            },
        },
        # KRITIK BULUNAN "UZUN KONUSMALARDA SORUN VAR" (2026-08-25,
        # kullanici kaniti): Gemini Live'in ses-only oturumlari sert bir
        # ~15 dakika sinirina sahip - biz bunu hic ele almiyorduk, sinira
        # gelince baglanti sessizce/aniden kesiliyordu ("konusmayı yarım
        # duyuyor" hissi). session_resumption acildiginda sunucu bir
        # GoAway mesajiyla ONCEDEN haber veriyor (bkz. asagida) - bunu
        # yakalayip istemciye nazikce "yeniden baglaniyorum" sinyali
        # gonderip devam-etme tokenini tasiyoruz.
        "session_resumption": {"handle": resumption_handle},
    }
    # GoAway/session_resumption_update mesajlarindan guncellenen, bir
    # sonraki baglantiya tasinacak en guncel devam-etme tokeni.
    current_resumption_handle = resumption_handle

    user_transcript_parts: list[str] = []
    assistant_transcript_parts: list[str] = []

    def pop_transcripts():
        """
        Biriken transkriptleri sadece bellekten okuyup temizler - hicbir
        bloklayici IO yapmaz. Ses relay dongusu (mikrofon akisi + Gemini
        turlari) bunu bekleyerek asla duraklamamali.
        """
        user_text = "".join(user_transcript_parts).strip()
        assistant_text = "".join(assistant_transcript_parts).strip()
        user_transcript_parts.clear()
        assistant_transcript_parts.clear()
        return user_text, assistant_text

    def persist_transcripts(user_text: str, assistant_text: str):
        """
        DB'ye yazma + hafiza cikarimi (aura_brain.extract_memory_candidate
        SENKRON/bloklayici bir HTTP istegi yapiyor - httpx.post, await
        degil). Bunu asla ana relay dongusunun icinde CAGIRMA: Gemini
        yavas/503 verdiginde tum event loop'u dondurup mikrofon akisini
        ve bir sonraki turu kilitliyordu - "ilk turdan sonra kesiliyor"
        hatasinin bir kismi buydu. Bu yuzden asyncio.to_thread ile ayri
        bir thread'de, relay dongusunu HIC bloklamadan calistiriliyor.
        """
        # KENDI KENDINI INCELEME BULGUSU (2026-08-26): bu fonksiyon gizli
        # mod kavramini HIC bilmiyordu - kod cumlesi burada asla
        # tetiklenmiyordu VE sesli sohbet transkripti her zaman hidden=0
        # ile kaydediliyordu. Kullanici yazili sohbette gizli moda girip
        # sonra sesli aramaya geciyorsa, tum konusma normal (PIN
        # gerektirmeyen) gecmiste dogrudan gorunuyordu - ozelligi tamamen
        # deliyordu. Artik yazili sohbetle AYNI kontrolu yapiyor.
        is_trigger = database.check_and_toggle_secret_phrase(user["id"], user_text, user=user) if user_text else False
        hidden_now = is_trigger or database.is_hidden_mode_active(user["id"], user=user)
        if user_text:
            msg_id = database.add_message(user["id"], "user", user_text, hidden=hidden_now)
            if not hidden_now:
                aura_brain.extract_memory_candidate(user["id"], user_text, msg_id)
            database.update_style_vector(user["id"], aura_brain.extract_style_signals(user_text))
        if assistant_text:
            database.add_message(user["id"], "assistant", assistant_text, hidden=hidden_now)

    # Es zamanlilik rezervasyonu, artik gercekten baglanmaya calismadan
    # HEMEN once yapiliyor - bundan sonrasi zaten mevcut try/finally
    # tarafindan korunuyor (finally'de mutlaka geri dusuruluyor), yani
    # rezervasyon hicbir zaman "sahipsiz" kalamaz.
    if free_tier:
        _active_voice_users.add(user["id"])

    # KOD INCELEMESI BULGUSU (2026-08-25): _client'a eklenen
    # http_options=HttpOptions(timeout=...) bu satiri HIC KORUMUYOR -
    # google-genai SDK'sinin live.py'si ws_connect() cagrisinda
    # http_options.timeout'a hic bakmiyor (sadece REST/httpx yollari
    # icin gecerli). Yani Gemini Live'in websocket el sikismasi askida
    # kalirsa bu "duzeltilmis" gibi gorunen satir GERCEKTE sonsuza dek
    # beklerdi. Gercek koruma: live.connect()'in __aenter__()'ini
    # (baglanma anini) asyncio.wait_for ile sariyoruz - `async with`
    # yerine elle __aenter__/__aexit__ kullanmamizin tek sebebi bu (asagidaki
    # mevcut govdenin girinti seviyesini degistirmeden ekleyebilmek icin).
    live_ctx = _client.aio.live.connect(model=VOICE_MODEL, config=config)
    try:
        session = await asyncio.wait_for(
            live_ctx.__aenter__(), timeout=VOICE_CONNECT_TIMEOUT_SECONDS
        )
    except (asyncio.TimeoutError, Exception) as e:
        print(
            f"VOICE SESSION: Gemini Live baglantisi {VOICE_CONNECT_TIMEOUT_SECONDS}sn "
            f"icinde kurulamadi ({type(e).__name__}: {e})"
        )
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Aura'ya şu anda bağlanılamadı. Lütfen tekrar dener misin?",
        }))
        if free_tier:
            _active_voice_users.discard(user["id"])
        try:
            await websocket.close()
        except Exception:
            pass
        return

    try:
            async def relay_client_to_gemini():
                while True:
                    message = await websocket.receive()

                    if message.get("type") == "websocket.disconnect":
                        print(
                            f"VOICE SESSION: istemci (Flutter) WS baglantisini kapatti "
                            f"(disconnect mesaji: {message})"
                        )
                        break

                    audio_bytes = message.get("bytes")
                    if audio_bytes:
                        await session.send_realtime_input(
                            audio=types.Blob(
                                data=audio_bytes,
                                mime_type="audio/pcm;rate=16000",
                            )
                        )

            async def relay_gemini_to_client():
                # ONEMLI: session.receive() SADECE TEK BIR TURU verir - SDK'nin
                # kendi kodu turn_complete gelince donguyu bilerek kesiyor
                # (google/genai/live.py: "if turn_complete: yield result; break").
                # Bu yuzden disariya bir "while True" sarmak sart - yoksa ilk
                # tur bitince bu coroutine normal sekilde biter, asyncio.wait
                # diger tarafi (mikrofon akisini) iptal edip TUM oturumu
                # kapatir. Once bu satir yoktu, tam da bu bug'i yasiyorduk:
                # "selam" dedikten hemen sonra baglanti kesiliyordu.
                total_chunks = 0
                turn_number = 0
                while True:
                    # GUVENLIK TARAMASI BULGUSU: daha once limit SADECE
                    # baglanti aninda kontrol ediliyordu - bu oturum ne
                    # kadar uzarsa uzasin bir daha hic kontrol edilmiyordu.
                    # Her yeni tur basinda (mid-sentence degil, dogal tur
                    # sinirinda) o ana kadarki toplam kullanimi (bugun
                    # onceden kullanilan + bu oturumda gecen sure) tekrar
                    # kontrol edip, asildiysa oturumu duzgunce kapatiyoruz.
                    if free_tier:
                        elapsed_this_session = time.time() - session_start_time
                        if already_used_seconds + elapsed_this_session >= VOICE_DAILY_LIMIT_SECONDS:
                            print(
                                f"VOICE SESSION: gunluk sesli limit oturum "
                                f"SIRASINDA asildi (user={user['id']}, "
                                f"{turn_number}. tur), kapatiliyor"
                            )
                            await websocket.send_text(json.dumps({
                                "type": "limit_reached",
                                "message": VOICE_LIMIT_REACHED_MESSAGE,
                            }))
                            return
                    turn_number += 1
                    # got_any_content: "uretici HICBIR SEY verdi mi" (bkz.
                    # asagida dongu sonu - Gemini'nin gercekten kapanip
                    # kapanmadigini anlamak icin). got_real_content: SADECE
                    # ses/transkript/tur-tamamlandi gibi GERCEK icerik icin -
                    # timeout esigini ve idle/stall ayrimini BUNA gore
                    # yapiyoruz. Bu ikisi KASITLI olarak ayri: session_resumption_update
                    # (session_resumption acildigi icin artik periyodik geliyor)
                    # ve go_away gibi "defter tutma" mesajlari got_any_content'i
                    # true yapar ama got_real_content'i YAPMAZ - aksi halde bir
                    # devam-etme tokeni sessizce dusunen bir kullaniciyi 60sn'lik
                    # sabir suresinden 20sn'lik "askida kaldi" suresine dusurur
                    # (kod incelemesinde bulundu).
                    got_any_content = False
                    got_real_content = False
                    turn_audio_chunks = 0
                    turn_iterator = session.receive()
                    # None | "timed_out" | "idle_ended" | "reconnect_needed"
                    exit_reason = None
                    while True:
                        # Bu turda HENUZ gercek icerik gelmediyse (kullanici
                        # dusunuyor/sessiz olabilir) uzun esik, geldiyse
                        # (sonra aniden durdu - suphesiz bir askida kalma)
                        # kisa esik kullaniyoruz. Ayni __anext__() cagrisi
                        # retry EDILMIYOR - her deneme TEK bir wait_for ile
                        # TEK bir sonuc uretiyor, bu yuzden asyncio iptal/
                        # retry guvenligi sorunu yok.
                        current_timeout = (
                            VOICE_TURN_IDLE_TIMEOUT_SECONDS
                            if got_real_content
                            else VOICE_IDLE_NO_CONTENT_TIMEOUT_SECONDS
                        )
                        try:
                            response = await asyncio.wait_for(
                                turn_iterator.__anext__(),
                                timeout=current_timeout,
                            )
                        except StopAsyncIteration:
                            break
                        except asyncio.TimeoutError:
                            if not got_real_content:
                                # IDLE: kullanici uzun suredir hicbir sey
                                # soylemedi - bir hata degil, nazik bir
                                # sonlandirma. Otomatik yeniden baglanmayi
                                # BILEREK tetiklemiyoruz (istemci tarafinda
                                # _limitReached ile ayni sekilde ele alinir).
                                print(
                                    f"VOICE SESSION: {turn_number}. tur - "
                                    f"{current_timeout}sn boyunca hicbir "
                                    f"gercek etkilesim olmadi - gorusme bosta "
                                    f"kaldigi icin sonlandiriliyor"
                                )
                                await websocket.send_text(json.dumps({
                                    "type": "idle_timeout",
                                    "message": (
                                        "Uzun süre sessizlik olduğu için "
                                        "görüşme sonlandırıldı."
                                    ),
                                }))
                                exit_reason = "idle_ended"
                                break
                            # STALL: tur zaten baslamisti (en az bir gercek
                            # icerik parcasi gelmisti), sonra aniden durdu -
                            # Gemini Live askida kalmis olabilir. Sonsuza
                            # kadar beklemek yerine oturumu duzgunce
                            # sonlandirip kullaniciya durustce haber veriyoruz.
                            print(
                                f"VOICE SESSION: {turn_number}. tur - Gemini'den "
                                f"{current_timeout}sn boyunca HICBIR "
                                f"yeni veri gelmedi (muhtemelen Gemini Live askida "
                                f"kaldi), bu tura kadar {turn_audio_chunks} ses "
                                f"parcasi gelmisti - oturum sonlandiriliyor"
                            )
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": (
                                    "Aura şu anda cevap veremedi (bağlantıda "
                                    "gecici bir sorun olabilir). Görüşmeyi "
                                    "kapatıp tekrar dener misin?"
                                ),
                            }))
                            exit_reason = "timed_out"
                            break

                        got_any_content = True
                        total_chunks += 1

                        if response.session_resumption_update:
                            update = response.session_resumption_update
                            if update.resumable and update.new_handle:
                                nonlocal current_resumption_handle
                                current_resumption_handle = update.new_handle

                        if response.data:
                            turn_audio_chunks += 1
                            got_real_content = True
                            await websocket.send_bytes(response.data)

                        # server_content'i go_away'den ONCE isliyoruz - Gemini
                        # bir GoAway'i, o turun son turn_complete/transkript
                        # icerigiyle AYNI ya da ARDISIK bir mesajda gonderebilir;
                        # go_away'i gorur gormez hemen break edersek o
                        # turn_complete istemciye hic ulasmayabilirdi (kod
                        # incelemesinde bulundu).
                        server_content = response.server_content
                        if server_content:
                            got_real_content = True

                        if server_content and server_content.interrupted:
                            # Teshis: bu genelde Aura'nin kendi sesi mikrofona
                            # sizip (yanki) Gemini'nin "kullanici konusmaya
                            # basladi" sanmasindan kaynaklanir. Kac ses parcasi
                            # yayinlandiktan SONRA kesildigini loglayarak
                            # bunun ne kadar erken/gec oldugunu goruyoruz.
                            print(
                                f"VOICE SESSION: INTERRUPTED sinyali geldi "
                                f"({turn_number}. tur, bu turda {turn_audio_chunks} "
                                f"ses parcasi yayinlanmisti)"
                            )
                            await websocket.send_text(json.dumps({"type": "interrupted"}))

                        if server_content and (
                            server_content.input_transcription
                            and server_content.input_transcription.text
                        ):
                            user_transcript_parts.append(
                                server_content.input_transcription.text
                            )
                            # Canli altyazi: tur bitmeden, parca geldikce
                            # o ana kadar birikeni gonder - istemci turn_complete'i
                            # beklemeden kelime kelime metni gosterebilsin.
                            await websocket.send_text(json.dumps({
                                "type": "partial_transcript",
                                "role": "user",
                                "text": "".join(user_transcript_parts).strip(),
                            }))

                        if server_content and (
                            server_content.output_transcription
                            and server_content.output_transcription.text
                        ):
                            assistant_transcript_parts.append(
                                server_content.output_transcription.text
                            )
                            await websocket.send_text(json.dumps({
                                "type": "partial_transcript",
                                "role": "assistant",
                                "text": "".join(assistant_transcript_parts).strip(),
                            }))

                        if server_content and server_content.turn_complete:
                            user_text, assistant_text = pop_transcripts()
                            await websocket.send_text(json.dumps({
                                "type": "turn_complete",
                                "user_text": user_text,
                                "assistant_text": assistant_text,
                            }))
                            if user_text or assistant_text:
                                asyncio.create_task(
                                    asyncio.to_thread(
                                        persist_transcripts, user_text, assistant_text
                                    )
                                )

                        if response.go_away:
                            # Gemini Live, ~15dk'lik ses-only oturum sinirina
                            # yaklasildigini ONCEDEN haber veriyor. Kullanici
                            # aniden kesilmek yerine, elimizdeki en guncel
                            # devam-etme tokeniyle sorunsuzca yeniden
                            # baglanabilsin diye istemciye acikca sinyal
                            # veriyoruz - bu bir hata degil, dogal bir
                            # oturum tazelemesi. server_content (turn_complete
                            # dahil) yukarida ZATEN islendi, o yuzden ayni
                            # mesaja binmis bir turn_complete kaybolmuyor.
                            print(
                                f"VOICE SESSION: GoAway alindi "
                                f"(time_left={response.go_away.time_left}, "
                                f"{turn_number}. tur) - istemciye yeniden "
                                f"baglanma sinyali gonderiliyor "
                                f"(resumption_handle mevcut="
                                f"{current_resumption_handle is not None})"
                            )
                            await websocket.send_text(json.dumps({
                                "type": "reconnect_needed",
                                "resumption_handle": current_resumption_handle,
                                "message": (
                                    "Görüşme uzadığı için bağlantı "
                                    "tazeleniyor, bir saniye..."
                                ),
                            }))
                            exit_reason = "reconnect_needed"
                            break

                    if exit_reason:
                        # Ilgili sinyal istemciye zaten yollandi (yukarida) -
                        # oturumu burada sonlandiriyoruz, "Gemini kapandi"
                        # mesajiyla karistirmamak icin ayri donuyoruz.
                        return

                    if not got_any_content:
                        # Gemini tarafi gercekten kapandi (bos donus) - bu
                        # sefer gercekten bitti, cikmak dogru.
                        print(
                            f"VOICE SESSION: Gemini Live oturumu kapandi "
                            f"({turn_number}. tur, toplam {total_chunks} chunk sonrasi)"
                        )
                        break

            done, pending = await asyncio.wait(
                [
                    asyncio.ensure_future(relay_client_to_gemini()),
                    asyncio.ensure_future(relay_gemini_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in pending:
                task.cancel()

            for task in done:
                exc = task.exception()
                if exc:
                    print(f"VOICE SESSION TASK ERROR: {type(exc).__name__}: {exc}")

    except WebSocketDisconnect as e:
        print(f"VOICE SESSION: istemci baglantiyi kesti (code={getattr(e, 'code', '?')})")
    except Exception as e:
        print(f"VOICE SESSION ERROR: {type(e).__name__}: {e}")
    finally:
        # `async with` yerine elle __aenter__ kullandigimiz icin (bkz.
        # yukarida, baglanma asamasini asyncio.wait_for ile sarabilmek
        # icin) esiti olan __aexit__'i de burada elle cagirmamiz sart -
        # yoksa Gemini Live oturumu/websocket'i hic kapanmaz.
        try:
            await live_ctx.__aexit__(None, None, None)
        except Exception as e:
            print(f"VOICE SESSION: live_ctx.__aexit__ HATASI: {e}")

        # KOD INCELEMESI BULGUSU (2026-08-25): _active_voice_users.discard()
        # buradan SONRAKI persist_transcripts() cagrisindan (senkron DB
        # yazma + hafiza cikarimi icin senkron bir Groq HTTP istegi icerir)
        # SONRA calisiyordu - yani es zamanlilik rezervasyonu, mantiksal
        # olarak hicbir ilgisi olmayan bu yavas islem bitene kadar
        # gereksiz yere elde tutuluyordu. Bu, tam da GoAway/reconnect_needed
        # sonrasi istemcinin HEMEN yeniden baglanmaya calistigi an onemli:
        # yeni baglanti bu eski rezervasyon hala dusmeden gelirse "zaten
        # acik bir gorusmen var" diye YANLISLIKLA reddedilebiliyordu. Artik
        # rezervasyon/sayac guncellemesi ONCE, yavas transkript yazma
        # islemi SONRA yapiliyor.
        elapsed_seconds = int(time.time() - session_start_time)
        database.add_voice_usage_seconds(user["id"], elapsed_seconds)
        if user.get("tier") != "pro":
            # Es zamanlilik korumasi icin eklenmisti (bkz. yukarida) -
            # oturum nasil biterse bitsin mutlaka geri dusuruluyor, yoksa
            # bu kullanici bir daha HICBIR sesli gorusme baslatamazdi.
            _active_voice_users.discard(user["id"])

        # Baglanti zaten kapaniyor, burada kisa bir blok kabul edilebilir.
        persist_transcripts(*pop_transcripts())

        try:
            await websocket.close()
        except Exception:
            pass
