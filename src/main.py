from __future__ import annotations
import io
import os
import tempfile
from openai import OpenAI

from .config import load_settings
from .gpio_inputs import PushToTalk
from .led_status import NeoPixelStatus, Status
from .audio_io import record_while_pressed

def _bytes_to_tempfile(data: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "wb") as f:
        f.write(data)
    return path

def main():
    settings = load_settings()

    client = OpenAI(api_key=settings.openai_api_key)

    ptt = PushToTalk(settings.gpio_ptt)
    led = NeoPixelStatus(settings.gpio_neopixel, settings.neopixel_count)
    led.start()
    led.set(Status.IDLE)

    print("KI-Chatbox bereit. Halte den Taster gedrückt zum Sprechen. Strg+C zum Beenden.")

    while True:
        try:
            ptt.wait_for_press()
            led.set(Status.LISTENING)

            wav_bytes = record_while_pressed(lambda: ptt.is_pressed)
            led.set(Status.THINKING)

            wav_path = _bytes_to_tempfile(wav_bytes, ".wav")
            try:
                with open(wav_path, "rb") as f:
                    stt = client.audio.transcriptions.create(
                        model=settings.model_stt,
                        file=f,
                    )
                user_text = (stt.text or "").strip()
            finally:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

            if not user_text:
                led.set(Status.IDLE)
                continue

            # Chat completion
            chat = client.chat.completions.create(
                model=settings.model_chat,
                messages=[
                    {"role": "system", "content": "Du bist ein hilfreicher, knapper Sprachassistent."},
                    {"role": "user", "content": user_text},
                ],
            )
            answer = (chat.choices[0].message.content or "").strip()

            # TTS to mp3
            led.set(Status.SPEAKING)
            speech = client.audio.speech.create(
                model=settings.model_tts,
                voice=settings.tts_voice,
                input=answer,
            )

            mp3_path = _bytes_to_tempfile(speech.read(), ".mp3")

            # Play using ffplay (comes with ffmpeg)
            os.system(f'ffplay -autoexit -nodisp -loglevel quiet "{mp3_path}"')

            try:
                os.remove(mp3_path)
            except OSError:
                pass

            led.set(Status.IDLE)

        except KeyboardInterrupt:
            led.set(Status.IDLE)
            print("\nBeendet.")
            break
        except Exception as e:
            print("Fehler:", e)
            led.blink_error()
            led.set(Status.IDLE)

if __name__ == "__main__":
    main()
