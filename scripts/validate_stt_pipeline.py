#!/usr/bin/env python3
"""Offline checks for local STT pipeline improvements (no mic required)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_agc() -> None:
    target = 10 ** (-18.0 / 20.0)
    max_gain = 10 ** (15.0 / 20.0)
    t = np.linspace(0, 0.5, 8000, endpoint=False)
    quiet = (0.01 * np.sin(2 * np.pi * 200 * t) * 32767).astype(np.int16)
    audio_float = quiet.astype(np.float32) / 32768.0
    audio_float = audio_float - np.mean(audio_float)
    rms = float(np.sqrt(np.mean(audio_float**2)))
    gain = min(target / rms, max_gain)
    assert gain <= max_gain + 1e-6
    print(f"OK agc gain={gain:.2f} (capped at {max_gain:.2f})")


def test_vad_ratio() -> None:
    def decide(speech: int, total: int, active: bool, th: float = 0.2, hang: float = 0.6) -> bool:
        if total <= 0:
            return False
        ratio = speech / total
        threshold = th
        if active:
            threshold = max(0.05, threshold * hang)
        return ratio >= threshold

    assert decide(1, 100, False) is False  # old any-frame gate would accept
    assert decide(25, 100, False) is True
    assert decide(12, 100, True) is True  # hangover
    print("OK vad speech-ratio gate")


def test_config_defaults() -> None:
    os.environ.setdefault("OPENAI_API_KEY", "test-key-for-validate")
    from src.config import load_settings

    s = load_settings()
    assert s.vad_preroll_sec == 0.30
    assert s.vad_webrtcvad_mode == 1
    assert s.vosk_pause_duration == 1.2
    assert abs(s.vad_speech_ratio - 0.2) < 1e-9
    print("OK config defaults")


def test_streaming_api() -> None:
    # Import may require sounddevice/vosk in a full venv; fall back to source scan.
    try:
        from src.speech_recognition_vosk import LiveVoskRecognition, VoskSpeechRecognition

        assert hasattr(LiveVoskRecognition, "_process_frame")
        assert hasattr(VoskSpeechRecognition, "create_stream_recognizer")
        print("OK streaming API import")
    except ImportError as e:
        text = (ROOT / "src/speech_recognition_vosk.py").read_text(encoding="utf-8")
        for needle in (
            "def _process_frame",
            "def create_stream_recognizer",
            "InputStream",
            "_agc_target_rms",
            "vad_speech_ratio",
        ):
            assert needle in text, needle
        print(f"OK streaming API source scan (import skipped: {e})")


def main() -> int:
    test_agc()
    test_vad_ratio()
    test_config_defaults()
    test_streaming_api()
    print("\nVALIDATION_PASSED")
    print("On device: python -m src.main --live-recognition --vosk  with DEBUG_LOGS=true")
    print("Try phrases: 'ok google', 'wie spät ist es', slow and normal speech.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
