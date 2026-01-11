from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _get_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")

@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    model_chat: str
    model_stt: str
    model_tts: str
    tts_voice: str

    use_gpio: bool
    gpiozero_pin_factory: str | None

    gpio_ptt: int
    gpio_led_red: int
    gpio_led_yellow: int
    gpio_led_green: int

    audio_input_device: str | None
    audio_output_device: str | None
    
    # Vosk (lokales Sprachmodell)
    vosk_model_path: str | None
    vosk_model_path_en: str | None  # Englisch

def load_settings() -> Settings:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "PASTE_YOUR_KEY_HERE":
        raise RuntimeError("OPENAI_API_KEY fehlt. Bitte in .env setzen.")

    return Settings(
        openai_api_key=key,
        model_chat=os.getenv("OPENAI_MODEL_CHAT", "gpt-4.1-mini"),
        model_stt=os.getenv("OPENAI_MODEL_STT", "gpt-4o-mini-transcribe"),
        model_tts=os.getenv("OPENAI_MODEL_TTS", "gpt-4o-mini-tts"),
        tts_voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),

        use_gpio=_get_bool("USE_GPIO", True),
        gpiozero_pin_factory=(os.getenv("GPIOZERO_PIN_FACTORY") or None),

        gpio_ptt=int(os.getenv("GPIO_PTT", "17")),
        gpio_led_red=int(os.getenv("GPIO_LED_RED", "16")),
        gpio_led_yellow=int(os.getenv("GPIO_LED_YELLOW", "20")),
        gpio_led_green=int(os.getenv("GPIO_LED_GREEN", "21")),

        audio_input_device=os.getenv("AUDIO_INPUT_DEVICE") or None,
        audio_output_device=os.getenv("AUDIO_OUTPUT_DEVICE") or None,
        
        vosk_model_path=os.getenv("VOSK_MODEL_PATH") or None,
        vosk_model_path_en=os.getenv("VOSK_MODEL_PATH_EN") or None,
    )
