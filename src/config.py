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
    live_pause_duration: float
    wake_phrases: list[str]
    context_phrases: list[str]
    stop_phrases: list[str]
    min_chat_words: int
    trivial_words: list[str]
    chat_filter_debug: bool
    chat_ignore_after_tts_sec: float
    auto_pause_after_sec: float
    debug_logs: bool
    chat_system_prompt_new: str
    chat_system_prompt_context: str
    echo_input_before_chat: bool
    echo_input_local_tts: bool
    enable_audio_processing: bool
    vad_rms_threshold: float
    vad_noise_multiplier: float
    vad_noise_alpha: float

def load_settings() -> Settings:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "PASTE_YOUR_KEY_HERE":
        raise RuntimeError("OPENAI_API_KEY fehlt. Bitte in .env setzen.")

    wake_phrases = [p.strip().lower() for p in os.getenv("WAKE_PHRASES", "ok google,okay google,hey google,start").split(",") if p.strip()]
    context_phrases = [p.strip().lower() for p in os.getenv(
        "CONTEXT_PHRASES", "ok google weiter,okay google weiter,hey google weiter"
    ).split(",") if p.strip()]
    stop_phrases = [p.strip().lower() for p in os.getenv("STOP_PHRASES", "stopp,stop").split(",") if p.strip()]
    min_chat_words = int(os.getenv("MIN_CHAT_WORDS", "2"))
    trivial_words = [p.strip().lower() for p in os.getenv("TRIVIAL_WORDS", "").split(",") if p.strip()]
    chat_filter_debug = _get_bool("CHAT_FILTER_DEBUG", False)
    chat_ignore_after_tts_sec = float(os.getenv("CHAT_IGNORE_AFTER_TTS_SEC", "2.0"))
    auto_pause_after_sec = float(os.getenv("AUTO_PAUSE_AFTER_SEC", "10"))
    debug_logs = _get_bool("DEBUG_LOGS", False)
    echo_input_before_chat = _get_bool("ECHO_INPUT_BEFORE_CHAT", True)
    echo_input_local_tts = _get_bool("ECHO_INPUT_LOCAL_TTS", True)
    enable_audio_processing = _get_bool("ENABLE_AUDIO_PROCESSING", True)
    vad_rms_threshold = float(os.getenv("VAD_RMS_THRESHOLD", "0.01"))
    vad_noise_multiplier = float(os.getenv("VAD_NOISE_MULTIPLIER", "3.0"))
    vad_noise_alpha = float(os.getenv("VAD_NOISE_ALPHA", "0.1"))
    chat_system_prompt_new = os.getenv(
        "CHAT_SYSTEM_PROMPT_NEW",
        "Du behandelst jede Eingabe als eigenständige, neue Frage. "
        "Kein Bezug zu früheren Fragen oder Antworten. Keine Kontextübernahme."
    )
    chat_system_prompt_context = os.getenv(
        "CHAT_SYSTEM_PROMPT_CONTEXT",
        "Du bist ein hilfreicher, knapper Sprachassistent. "
        "Du darfst Kontext der laufenden Unterhaltung berücksichtigen."
    )

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

        audio_input_device=os.getenv("AUDIO_INPUT_DEVICE") or "reSpeaker XVF3800 4-Mic Array",
        audio_output_device=os.getenv("AUDIO_OUTPUT_DEVICE") or "Logitech USB Headset",
        
        vosk_model_path=os.getenv("VOSK_MODEL_PATH") or None,
        vosk_model_path_en=os.getenv("VOSK_MODEL_PATH_EN") or None,
        live_pause_duration=float(os.getenv("LIVE_PAUSE_DURATION", "0.9")),
        wake_phrases=wake_phrases,
        context_phrases=context_phrases,
        stop_phrases=stop_phrases,
        min_chat_words=min_chat_words,
        trivial_words=trivial_words,
        chat_filter_debug=chat_filter_debug,
        chat_ignore_after_tts_sec=chat_ignore_after_tts_sec,
        auto_pause_after_sec=auto_pause_after_sec,
        debug_logs=debug_logs,
        chat_system_prompt_new=chat_system_prompt_new,
        chat_system_prompt_context=chat_system_prompt_context,
        echo_input_before_chat=echo_input_before_chat,
        echo_input_local_tts=echo_input_local_tts,
        enable_audio_processing=enable_audio_processing,
        vad_rms_threshold=vad_rms_threshold,
        vad_noise_multiplier=vad_noise_multiplier,
        vad_noise_alpha=vad_noise_alpha,
    )
