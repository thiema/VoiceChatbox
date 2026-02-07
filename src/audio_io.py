from __future__ import annotations
import io
import sys
import time
import wave
import re
import numpy as np
import sounddevice as sd

def _get_input_devices() -> list[tuple[int, dict]]:
    """Return list of (device_id, device_info) for input-capable devices."""
    try:
        devices = sd.query_devices()
        return [
            (i, d)
            for i, d in enumerate(devices)
            if d.get("max_input_channels", 0) > 0
        ]
    except Exception:
        return []

def _resolve_device_id(device_spec: str | int | None) -> int | None:
    """Resolve device specification (name or ID) to device ID.

    Supports:
    - int or numeric string (device ID)
    - partial name match
    - composite match using "token1|token2" (all tokens must match)
    - key-value match like "card=...;device=..." or "card=... , device=..."
    """
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
    
    spec = str(device_spec).strip()
    tokens: list[str] = []
    
    # Parse key-value spec: card=...;device=...
    if "card=" in spec.lower() or "device=" in spec.lower():
        parts = re.split(r"[;,]", spec)
        kv = {}
        for part in parts:
            if "=" in part:
                k, v = part.split("=", 1)
                kv[k.strip().lower()] = v.strip()
        card = kv.get("card")
        device = kv.get("device")
        if card:
            tokens.append(card)
        if device:
            tokens.append(device)
        # If numeric card/device are provided, add hw:card,device token
        if card and device and card.isdigit() and device.isdigit():
            tokens.append(f"hw:{card},{device}")
    elif "|" in spec:
        tokens = [t.strip() for t in spec.split("|") if t.strip()]
    else:
        tokens = [spec]
    
    # Search by name (case-insensitive partial match for all tokens)
    devices = sd.query_devices()
    tokens_lower = [t.lower() for t in tokens if t]
    for i, device in enumerate(devices):
        name = device.get('name', '').lower()
        if all(token in name for token in tokens_lower):
            return i
    
    # Not found, return None (caller may fallback)
    return None

def _print_input_devices() -> None:
    """Print available input devices for troubleshooting."""
    input_devices = _get_input_devices()
    if not input_devices:
        return
    print("Verfügbare Input-Geräte:", file=sys.stderr)
    for i, d in input_devices:
        print(f"  {i}: {d['name']} (in={d['max_input_channels']})", file=sys.stderr)

def _select_input_device(device_spec: str | int | None) -> int | None:
    """Select input device. Falls back to first available if spec not found."""
    device_id = _resolve_device_id(device_spec)
    if device_id is not None:
        return device_id
    input_devices = _get_input_devices()
    if input_devices:
        fallback_id, _ = input_devices[0]
        return fallback_id
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
    
    # Liste Geräte und zeige gewähltes Device
    _print_input_devices()
    device_id = _select_input_device(device)
    if device_id is not None:
        try:
            dev_info = sd.query_devices(device_id)
            print(f"Verwendetes Input-Gerät: {dev_info['name']} (ID: {device_id})", file=sys.stderr)
        except Exception:
            pass
    
    # Verwende InputStream mit Callback statt sd.rec() um Konflikte zu vermeiden
    def callback(indata, frames_count, time_info, status):
        if status:
            print(f"Audio-Status: {status}", file=sys.stderr)
        frames.append(indata.copy())
    
    def _open_stream(selected_device: int | None):
        return sd.InputStream(
            device=selected_device,
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
            callback=callback,
            blocksize=int(samplerate * 0.1)  # 0.1 Sekunden Blöcke
        )
    
    stream = None
    try:
        try:
            stream = _open_stream(device_id)
            stream.start()
        except sd.PortAudioError as e:
            print(f"Audio-Fehler beim Öffnen InputStream (device={device_id}): {e}", file=sys.stderr)
            if device_id is not None:
                # Fallback auf Standardgerät
                print("Versuche Standardgerät...", file=sys.stderr)
                time.sleep(0.1)
                stream = _open_stream(None)
                stream.start()
            else:
                _print_input_devices()
                raise
        
        # Warte während Taster gedrückt ist
        while is_pressed_fn():
            sd.sleep(100)  # 100ms Pause
        
        # Kurze Pause um letzten Block zu erfassen
        sd.sleep(100)
        
    except sd.PortAudioError:
        _print_input_devices()
        raise
    finally:
        if stream is not None:
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
