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

_client = genai.Client(api_key=aura_brain.GEMINI_API_KEY)

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

    past_messages = database.get_messages(user["id"])
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
    }

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
        if user_text:
            msg_id = database.add_message(user["id"], "user", user_text)
            aura_brain.extract_memory_candidate(user["id"], user_text, msg_id)
        if assistant_text:
            database.add_message(user["id"], "assistant", assistant_text)

    # Es zamanlilik rezervasyonu, artik gercekten baglanmaya calismadan
    # HEMEN once yapiliyor - bundan sonrasi zaten mevcut try/finally
    # tarafindan korunuyor (finally'de mutlaka geri dusuruluyor), yani
    # rezervasyon hicbir zaman "sahipsiz" kalamaz.
    if free_tier:
        _active_voice_users.add(user["id"])

    try:
        async with _client.aio.live.connect(model=VOICE_MODEL, config=config) as session:

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
                    got_any_content = False
                    turn_audio_chunks = 0
                    async for response in session.receive():
                        got_any_content = True
                        total_chunks += 1
                        if response.data:
                            turn_audio_chunks += 1
                            await websocket.send_bytes(response.data)

                        server_content = response.server_content
                        if not server_content:
                            continue

                        if server_content.interrupted:
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

                        if (
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

                        if (
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

                        if server_content.turn_complete:
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
        # Baglanti zaten kapaniyor, burada kisa bir blok kabul edilebilir.
        persist_transcripts(*pop_transcripts())
        # Gorusme nasil biterse bitsin (normal, hata, baglanti kopmasi)
        # gecen sureyi gunluk kullanim sayacina ekle - free tier icin.
        if user.get("tier") != "pro":
            elapsed_seconds = int(time.time() - session_start_time)
            database.add_voice_usage_seconds(user["id"], elapsed_seconds)
            # Es zamanlilik korumasi icin eklenmisti (bkz. yukarida) -
            # oturum nasil biterse bitsin mutlaka geri dusuruluyor, yoksa
            # bu kullanici bir daha HICBIR sesli gorusme baslatamazdi.
            _active_voice_users.discard(user["id"])
        try:
            await websocket.close()
        except Exception:
            pass
