from __future__ import annotations
import io
import sys
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
    
    # Verwende InputStream mit Callback statt sd.rec() um Konflikte zu vermeiden
    def callback(indata, frames_count, time_info, status):
        if status:
            print(f"Audio-Status: {status}", file=sys.stderr)
        frames.append(indata.copy())
    
    # Erstelle InputStream und starte Aufnahme
    stream = sd.InputStream(
        device=device_id,
        samplerate=samplerate,
        channels=channels,
        dtype=dtype,
        callback=callback,
        blocksize=int(samplerate * 0.1)  # 0.1 Sekunden Blöcke
    )
    
    try:
        stream.start()
        
        # Warte während Taster gedrückt ist
        while is_pressed_fn():
            sd.sleep(100)  # 100ms Pause
        
        # Kurze Pause um letzten Block zu erfassen
        sd.sleep(100)
        
    finally:
        stream.stop()
        stream.close()
    
    # Konkateniere alle Frames
    if frames:
        audio = np.concatenate(frames, axis=0)
        # Konvertiere zu mono falls nötig
        if len(audio.shape) > 1:
            audio = audio[:, 0]
    else:
        audio = np.zeros((0,), dtype=np.int16)

    # Konvertiere zu WAV
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # int16
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()
