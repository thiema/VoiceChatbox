from __future__ import annotations
import io
import wave
import numpy as np
import sounddevice as sd

def _resolve_device_id(device_spec: str | int | None) -> int | None:
    """Resolve device specification (name or ID) to device ID."""
    if device_spec is None:
        return None
    
    # If it's already an integer, return it
    if isinstance(device_spec, int):
        return device_spec
    
    # Try to parse as integer
    try:
        return int(device_spec)
    except ValueError:
        pass
    
    # Search by name (case-insensitive partial match)
    devices = sd.query_devices()
    device_spec_lower = device_spec.lower()
    for i, device in enumerate(devices):
        if device_spec_lower in device['name'].lower():
            return i
    
    # Not found, return None (will use default)
    return None

def record_while_pressed(is_pressed_fn, samplerate: int = 16000, device: str | int | None = None) -> bytes:
    """
    Record mono audio until is_pressed_fn() becomes False. Returns WAV bytes.
    
    Args:
        is_pressed_fn: Function that returns True while recording should continue
        samplerate: Sample rate in Hz (default: 16000)
        device: Audio input device (ID, name, or None for default)
    """
    channels = 1
    dtype = "int16"
    frames = []
    
    device_id = _resolve_device_id(device)

    with sd.InputStream(device=device_id, samplerate=samplerate, channels=channels, dtype=dtype):
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
