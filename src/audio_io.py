from __future__ import annotations
import io
import wave
import numpy as np
import sounddevice as sd

def record_while_pressed(is_pressed_fn, samplerate: int = 16000) -> bytes:
    """Record mono audio until is_pressed_fn() becomes False. Returns WAV bytes."""
    channels = 1
    dtype = "int16"
    frames = []

    with sd.InputStream(samplerate=samplerate, channels=channels, dtype=dtype):
        while is_pressed_fn():
            data, _overflowed = sd.rec(int(samplerate * 0.1), samplerate=samplerate, channels=channels, dtype=dtype), None
            sd.wait()
            frames.append(data.copy())

    audio = np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype=np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
