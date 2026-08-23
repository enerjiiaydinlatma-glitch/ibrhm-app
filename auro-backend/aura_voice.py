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

from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

import aura_brain
import database

VOICE_MODEL = "gemini-3.1-flash-live-preview"

_client = genai.Client(api_key=aura_brain.GEMINI_API_KEY)


async def handle_voice_session(websocket: WebSocket) -> None:
    await websocket.accept()

    token = websocket.query_params.get("token")
    user = database.get_user_by_token(token) if token else None

    if not user:
        await websocket.close(code=4001)
        return

    past_messages = database.get_messages(user["id"])
    message_count = len(past_messages)
    system_instruction = aura_brain.build_system_instruction(user, message_count)

    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": system_instruction,
        "input_audio_transcription": {},
        "output_audio_transcription": {},
        "speech_config": {"language_code": "tr-TR"},
    }

    user_transcript_parts: list[str] = []
    assistant_transcript_parts: list[str] = []

    def flush_transcripts():
        """
        Biriken transkriptleri hafizaya yazar VE geri doner - boylece
        istemci ayni sozleri sohbet baloncugu olarak gosterebilir
        (yazili/sesli mesajlar ayni akista birlesir).
        """
        user_text = "".join(user_transcript_parts).strip()
        assistant_text = "".join(assistant_transcript_parts).strip()
        user_transcript_parts.clear()
        assistant_transcript_parts.clear()

        if user_text:
            msg_id = database.add_message(user["id"], "user", user_text)
            aura_brain.extract_memory_candidate(user["id"], user_text, msg_id)
        if assistant_text:
            database.add_message(user["id"], "assistant", assistant_text)

        return user_text, assistant_text

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
                    turn_number += 1
                    got_any_content = False
                    async for response in session.receive():
                        got_any_content = True
                        total_chunks += 1
                        if response.data:
                            await websocket.send_bytes(response.data)

                        server_content = response.server_content
                        if not server_content:
                            continue

                        if server_content.interrupted:
                            await websocket.send_text(json.dumps({"type": "interrupted"}))

                        if (
                            server_content.input_transcription
                            and server_content.input_transcription.text
                        ):
                            user_transcript_parts.append(
                                server_content.input_transcription.text
                            )

                        if (
                            server_content.output_transcription
                            and server_content.output_transcription.text
                        ):
                            assistant_transcript_parts.append(
                                server_content.output_transcription.text
                            )

                        if server_content.turn_complete:
                            user_text, assistant_text = flush_transcripts()
                            await websocket.send_text(json.dumps({
                                "type": "turn_complete",
                                "user_text": user_text,
                                "assistant_text": assistant_text,
                            }))

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
        flush_transcripts()
        try:
            await websocket.close()
        except Exception:
            pass
