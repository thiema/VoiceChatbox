from __future__ import annotations
import os
import sys
import tempfile
from time import sleep
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

def _tts_play(client: OpenAI, model_tts: str, voice: str, text: str) -> None:
    speech = client.audio.speech.create(model=model_tts, voice=voice, input=text)
    mp3_path = _bytes_to_tempfile(speech.read(), ".mp3")
    os.system(f'ffplay -autoexit -nodisp -loglevel quiet "{mp3_path}"')
    try:
        os.remove(mp3_path)
    except OSError:
        pass

def _stt_transcribe(client: OpenAI, model_stt: str, wav_bytes: bytes) -> str:
    wav_path = _bytes_to_tempfile(wav_bytes, ".wav")
    try:
        with open(wav_path, "rb") as f_audio:
            stt = client.audio.transcriptions.create(model=model_stt, file=f_audio)
        return (stt.text or "").strip()
    finally:
        try:
            os.remove(wav_path)
        except OSError:
            pass

def test_leds():
    s = load_settings()
    leds = LedStatus(s.gpio_led_red, s.gpio_led_yellow, s.gpio_led_green, enabled=True)
    print("LED-Test: Rot"); leds.set(Status.ERROR); sleep(1)
    print("LED-Test: Gelb"); leds.set(Status.THINKING); sleep(1)
    print("LED-Test: Grün"); leds.set(Status.SPEAKING); sleep(1)
    print("LED-Test: Aus"); leds.set(Status.IDLE); sleep(0.2)
    print("OK")

def test_ptt():
    """PTT-Test: zeigt PRESSED/RELEASED und signalisiert mit grüner LED."""
    s = load_settings()
    if not s.use_gpio:
        print("USE_GPIO=false – PTT-Test benötigt GPIO.")
        return
    leds = LedStatus(s.gpio_led_red, s.gpio_led_yellow, s.gpio_led_green, enabled=True)
    ptt = PushToTalk(s.gpio_ptt)
    print("PTT-Test läuft. Verbinde GPIO17 kurz mit GND (Improvisierter Kontakt). Strg+C zum Beenden.")
    last = None
    try:
        while True:
            state = ptt.is_pressed
            if state != last:
                last = state
                if state:
                    print("PRESSED")
                    leds.set(Status.SPEAKING)  # grün an
                else:
                    print("RELEASED")
                    leds.set(Status.IDLE)
            sleep(0.05)
    except KeyboardInterrupt:
        leds.set(Status.IDLE)
        print("\nBeendet.")

def _select_mode_by_voice(client: OpenAI, settings, ptt: PushToTalk, leds: LedStatus) -> str:
    prompt = (
        "Willkommen. Bitte sage jetzt entweder: Echo. Oder: Chatbox. "
        "Halte dazu den Kontakt gedrückt und sprich."
    )
    _tts_play(client, settings.model_tts, settings.tts_voice, prompt)

    for _ in range(3):
        ptt.wait_for_press()
        leds.set(Status.LISTENING)
        wav_bytes = record_while_pressed(lambda: ptt.is_pressed)
        leds.set(Status.THINKING)

        text = _stt_transcribe(client, settings.model_stt, wav_bytes).lower()
        if "echo" in text:
            _tts_play(client, settings.model_tts, settings.tts_voice, "Echo Modus aktiviert.")
            return "echo"
        if "chat" in text or "chatbox" in text:
            _tts_play(client, settings.model_tts, settings.tts_voice, "Chatbox Modus aktiviert.")
            return "chatbox"

        _tts_play(client, settings.model_tts, settings.tts_voice,
                  "Ich habe das nicht verstanden. Bitte sage Echo oder Chatbox.")

    _tts_play(client, settings.model_tts, settings.tts_voice, "Ich wähle automatisch Chatbox.")
    return "chatbox"

def main():
    if "--test-leds" in sys.argv:
        test_leds()
        return
    if "--test-ptt" in sys.argv:
        test_ptt()
        return
    if "--test-oled" in sys.argv:
        from .oled_test import run_oled_test
        run_oled_test()
        return

    forced_mode = None
    if "--mode" in sys.argv:
        try:
            forced_mode = sys.argv[sys.argv.index("--mode") + 1].strip().lower()
        except Exception:
            forced_mode = None

    settings = load_settings()
    # Optional OLED Statusanzeige
    oled = None
    try:
        from .oled_display import OledDisplay
        oled = OledDisplay()
        if oled.init():
            oled.show_ready()
        else:
            oled = None
    except Exception:
        oled = None

    if not settings.use_gpio:
        print("USE_GPIO=false – dieser Build nutzt GPIO für Kontakt/LEDs. Bitte USE_GPIO=true setzen.")
        return

    client = OpenAI(api_key=settings.openai_api_key)

    leds = LedStatus(settings.gpio_led_red, settings.gpio_led_yellow, settings.gpio_led_green, enabled=True)
    leds.set(Status.IDLE)

    ptt = PushToTalk(settings.gpio_ptt)

    if forced_mode in ("echo", "chatbox"):
        mode = forced_mode
    else:
        mode = _select_mode_by_voice(client, settings, ptt, leds)

    print(f"Modus: {mode}")
    print("Bereit. Kontakt gedrückt halten zum Sprechen. Strg+C zum Beenden.")

    while True:
        try:
            ptt.wait_for_press()
            leds.set(Status.LISTENING)

            wav_bytes = record_while_pressed(lambda: ptt.is_pressed)
            leds.set(Status.THINKING)

            user_text = _stt_transcribe(client, settings.model_stt, wav_bytes)

            if not user_text:
                leds.set(Status.IDLE)
                continue

            if mode == "echo":
                answer = user_text
            else:
                chat = client.chat.completions.create(
                    model=settings.model_chat,
                    messages=[
                        {"role": "system", "content": "Du bist ein hilfreicher, knapper Sprachassistent."},
                        {"role": "user", "content": user_text},
                    ],
                )
                answer = (chat.choices[0].message.content or "").strip()

            leds.set(Status.SPEAKING)
            _tts_play(client, settings.model_tts, settings.tts_voice, answer)
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
