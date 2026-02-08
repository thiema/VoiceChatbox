from __future__ import annotations
import io
import sys
import time
import threading
import wave
import re
import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

_playback_active = threading.Event()

def is_playback_active() -> bool:
    return _playback_active.is_set()

def wait_for_playback_end(poll_interval: float = 0.05) -> None:
    """Block until playback is finished."""
    while _playback_active.is_set():
        time.sleep(poll_interval)

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

def _get_output_devices() -> list[tuple[int, dict]]:
    """Return list of (device_id, device_info) for output-capable devices."""
    try:
        devices = sd.query_devices()
        return [
            (i, d)
            for i, d in enumerate(devices)
            if d.get("max_output_channels", 0) > 0
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

def _print_output_devices() -> None:
    """Print available output devices for troubleshooting."""
    output_devices = _get_output_devices()
    if not output_devices:
        return
    print("Verfügbare Output-Geräte:", file=sys.stderr)
    for i, d in output_devices:
        print(f"  {i}: {d['name']} (out={d['max_output_channels']})", file=sys.stderr)

def select_input_device(device_spec: str | int | None, announce: bool = True) -> int | None:
    """Select input device; optionally announce list and selection.

    Falls back to first available input device if spec not found.
    """
    if announce:
        _print_input_devices()
    device_id = _resolve_device_id(device_spec)
    if device_id is None:
        input_devices = _get_input_devices()
        if input_devices:
            fallback_id, _ = input_devices[0]
            if announce and device_spec:
                print(
                    f"⚠️  Eingabegerät '{device_spec}' nicht gefunden. "
                    f"Fallback auf erstes verfügbares Gerät (ID: {fallback_id}).",
                    file=sys.stderr
                )
            device_id = fallback_id
    if announce and device_id is not None:
        try:
            dev_info = sd.query_devices(device_id)
            print(f"Verwendetes Input-Gerät: {dev_info['name']} (ID: {device_id})", file=sys.stderr)
        except Exception:
            pass
    return device_id

def select_output_device(device_spec: str | int | None, announce: bool = True) -> int | None:
    """Select output device; optionally announce list and selection.

    Falls back to first available output device if spec not found.
    """
    if announce:
        _print_output_devices()
    device_id = _resolve_device_id(device_spec)
    if device_id is not None:
        try:
            dev_info = sd.query_devices(device_id)
            if dev_info.get("max_output_channels", 0) <= 0:
                device_id = None
        except Exception:
            device_id = None
    if device_id is None:
        output_devices = _get_output_devices()
        if output_devices:
            fallback_id, _ = output_devices[0]
            if announce and device_spec:
                print(
                    f"⚠️  Ausgabegerät '{device_spec}' nicht gefunden. "
                    f"Fallback auf erstes verfügbares Gerät (ID: {fallback_id}).",
                    file=sys.stderr
                )
            device_id = fallback_id
    if announce and device_id is not None:
        try:
            dev_info = sd.query_devices(device_id)
            print(f"Verwendetes Output-Gerät: {dev_info['name']} (ID: {device_id})", file=sys.stderr)
        except Exception:
            pass
    return device_id

def play_wav_bytes(wav_bytes: bytes, device: str | int | None = None, announce: bool = True) -> None:
    """Play WAV audio bytes via the selected output device."""
    if not wav_bytes:
        return
    device_id = select_output_device(device, announce=announce)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        samplerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        raise ValueError(f"Unsupported sample width: {sampwidth * 8} bits")

    audio = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        audio = audio.reshape(-1, channels)

    dev_info = None
    try:
        if device_id is not None:
            dev_info = sd.query_devices(device_id)
    except Exception:
        dev_info = None

    target_channels = channels
    if dev_info and channels == 1 and dev_info.get("max_output_channels", 0) >= 2:
        target_channels = 2

    # If the device rejects the sample rate, resample to a supported rate.
    target_sr = samplerate
    try:
        sd.check_output_settings(
            device=device_id,
            samplerate=target_sr,
            channels=target_channels,
            dtype="int16",
        )
    except sd.PortAudioError:
        default_sr = int((dev_info or {}).get("default_samplerate") or 48000)
        for sr in (default_sr, 48000, 44100):
            try:
                sd.check_output_settings(
                    device=device_id,
                    samplerate=sr,
                    channels=target_channels,
                    dtype="int16",
                )
                target_sr = sr
                break
            except sd.PortAudioError:
                continue
        else:
            target_sr = default_sr

    if target_sr != samplerate and audio.size > 0:
        # Resample using polyphase filtering for quality.
        audio = resample_poly(audio, target_sr, samplerate, axis=0).astype(np.int16)

    if target_channels == 2 and channels == 1 and audio.size > 0:
        audio = np.column_stack([audio, audio])

    if audio.size == 0:
        return

    # Use a dedicated OutputStream to avoid PortAudio crashes on stop/play.
    stream = sd.OutputStream(
        device=device_id,
        samplerate=target_sr,
        channels=target_channels,
        dtype="int16",
    )
    _playback_active.set()
    try:
        stream.start()
        stream.write(audio)
    finally:
        _playback_active.clear()
        stream.stop()
        stream.close()

def _tone_wav_bytes(
    frequency: float = 880.0,
    duration_sec: float = 0.08,
    samplerate: int = 48000,
    volume: float = 0.2,
) -> bytes:
    """Generate a short sine beep as WAV bytes."""
    t = np.linspace(0, duration_sec, int(samplerate * duration_sec), endpoint=False)
    wave_data = np.sin(2 * np.pi * frequency * t) * volume
    # Apply short fade-in/out to avoid clicks
    fade_len = max(1, int(0.005 * samplerate))
    fade = np.linspace(0, 1, fade_len)
    wave_data[:fade_len] *= fade
    wave_data[-fade_len:] *= fade[::-1]
    audio = (wave_data * 32767.0).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()

def play_beep_sequence(
    count: int = 2,
    gap_sec: float = 0.06,
    frequency: float = 880.0,
    duration_sec: float = 0.08,
    volume: float = 0.2,
    device: str | int | None = None,
    announce: bool = False,
) -> None:
    """Play a short double-beep sequence."""
    if count <= 0:
        return
    beep = _tone_wav_bytes(
        frequency=frequency,
        duration_sec=duration_sec,
        volume=volume,
    )
    for i in range(count):
        play_wav_bytes(beep, device=device, announce=announce)
        if i < count - 1:
            time.sleep(gap_sec)

def play_hangup_tone(device: str | int | None = None, announce: bool = False) -> None:
    """Play a short descending tone (MS Teams-like hangup)."""
    play_beep_sequence(
        count=1,
        gap_sec=0.0,
        frequency=740.0,
        duration_sec=0.08,
        volume=0.18,
        device=device,
        announce=announce,
    )
    time.sleep(0.04)
    play_beep_sequence(
        count=1,
        gap_sec=0.0,
        frequency=520.0,
        duration_sec=0.1,
        volume=0.18,
        device=device,
        announce=announce,
    )

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
    
    # Warte, falls gerade Ausgabe läuft
    wait_for_playback_end()

    # Liste Geräte und zeige gewähltes Device
    device_id = select_input_device(device, announce=True)
    
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
