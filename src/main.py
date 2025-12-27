from __future__ import annotations
import os
import sys
import tempfile
from openai import OpenAI

from .config import load_settings
from .gpio_inputs import PushToTalk
from .led_status import LedStatus, Status
from .audio_io import record_while_pressed

def _bytes_to_tempfile(data: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(path, "wb") as f:
        f.write(data)
    return path

def test_leds():
    s = load_settings()
    leds = LedStatus(s.gpio_led_red, s.gpio_led_yellow, s.gpio_led_green, enabled=True)
    from time import sleep
    print("LED-Test: Rot"); leds.set(Status.ERROR); sleep(1)
    print("LED-Test: Gelb"); leds.set(Status.THINKING); sleep(1)
    print("LED-Test: Grün"); leds.set(Status.SPEAKING); sleep(1)
    print("LED-Test: Aus"); leds.set(Status.IDLE); sleep(0.2)
    print("OK")

def main():
    if "--test-leds" in sys.argv:
        test_leds()
        return

    settings = load_settings()
    if not settings.use_gpio:
        print("USE_GPIO=false – dieser Build nutzt GPIO für Button/LEDs. Bitte USE_GPIO=true setzen.")
        return

    client = OpenAI(api_key=settings.openai_api_key)

    leds = LedStatus(settings.gpio_led_red, settings.gpio_led_yellow, settings.gpio_led_green, enabled=True)
    leds.set(Status.IDLE)

    ptt = PushToTalk(settings.gpio_ptt)
    print("KI-Chatbox bereit. Taster gedrückt halten zum Sprechen. Strg+C zum Beenden.")

    while True:
        try:
            ptt.wait_for_press()
            leds.set(Status.LISTENING)

            wav_bytes = record_while_pressed(lambda: ptt.is_pressed)
            leds.set(Status.THINKING)

            wav_path = _bytes_to_tempfile(wav_bytes, ".wav")
            try:
                with open(wav_path, "rb") as f_audio:
                    stt = client.audio.transcriptions.create(model=settings.model_stt, file=f_audio)
                user_text = (stt.text or "").strip()
            finally:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

            if not user_text:
                leds.set(Status.IDLE)
                continue

            chat = client.chat.completions.create(
                model=settings.model_chat,
                messages=[
                    {"role": "system", "content": "Du bist ein hilfreicher, knapper Sprachassistent."},
                    {"role": "user", "content": user_text},
                ],
            )
            answer = (chat.choices[0].message.content or "").strip()

            leds.set(Status.SPEAKING)
            speech = client.audio.speech.create(model=settings.model_tts, voice=settings.tts_voice, input=answer)
            mp3_path = _bytes_to_tempfile(speech.read(), ".mp3")

            os.system(f'ffplay -autoexit -nodisp -loglevel quiet "{mp3_path}"')
            try:
                os.remove(mp3_path)
            except OSError:
                pass

            leds.set(Status.IDLE)

        except KeyboardInterrupt:
            leds.set(Status.IDLE)
            print("\nBeendet.")
            break
        except Exception as e:
            print("Fehler:", e)
            leds.blink_error()
            leds.set(Status.IDLE)

if __name__ == "__main__":
    main()
