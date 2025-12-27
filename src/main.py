from __future__ import annotations
import os
import tempfile
from openai import OpenAI

from .config import load_settings
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

    led = NeoPixelStatus(settings.gpio_neopixel, settings.neopixel_count, enabled=settings.use_neopixel)
    led.start()
    led.set(Status.IDLE)

    if settings.use_gpio:
        from .gpio_inputs import PushToTalk
        ptt = PushToTalk(settings.gpio_ptt)
        print("KI-Chatbox bereit. Taster gedrückt halten zum Sprechen. Strg+C zum Beenden.")

        def wait_start():
            ptt.wait_for_press()

        def record():
            return record_while_pressed(lambda: ptt.is_pressed)
    else:
        print("KI-Chatbox bereit. (GPIO deaktiviert) Nimmt 5 Sekunden auf und verarbeitet dann.")
        def wait_start():
            input("ENTER zum Starten...")
        def record():
            import sounddevice as sd, io, wave
            samplerate = 16000
            audio = sd.rec(int(5 * samplerate), samplerate=samplerate, channels=1, dtype="int16")
            sd.wait()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(samplerate)
                wf.writeframes(audio.tobytes())
            return buf.getvalue()

    while True:
        try:
            wait_start()
            led.set(Status.LISTENING)

            wav_bytes = record()
            led.set(Status.THINKING)

            wav_path = _bytes_to_tempfile(wav_bytes, ".wav")
            try:
                with open(wav_path, "rb") as f:
                    stt = client.audio.transcriptions.create(model=settings.model_stt, file=f)
                user_text = (stt.text or "").strip()
            finally:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass

            if not user_text:
                led.set(Status.IDLE)
                continue

            chat = client.chat.completions.create(
                model=settings.model_chat,
                messages=[
                    {"role": "system", "content": "Du bist ein hilfreicher, knapper Sprachassistent."},
                    {"role": "user", "content": user_text},
                ],
            )
            answer = (chat.choices[0].message.content or "").strip()

            led.set(Status.SPEAKING)
            speech = client.audio.speech.create(model=settings.model_tts, voice=settings.tts_voice, input=answer)
            mp3_path = _bytes_to_tempfile(speech.read(), ".mp3")

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
