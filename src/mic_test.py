from __future__ import annotations

import sys
import time
import numpy as np
import sounddevice as sd


def list_input_devices() -> list[tuple[int, dict]]:
    """Liste alle verfügbaren Eingabegeräte und gib sie zurück."""
    devices = sd.query_devices()
    input_devices: list[tuple[int, dict]] = []
    print("\n=== Verfügbare Mikrofone ===\n")
    print(f"{'ID':<4} {'Name':<60} {'Kanäle'}")
    print("-" * 90)
    for i, d in enumerate(devices):
        if d.get("max_input_channels", 0) > 0:
            input_devices.append((i, d))
            print(f"{i:<4} {d['name']:<60} {d['max_input_channels']}")
    print()
    return input_devices


def prompt_for_device(input_devices: list[tuple[int, dict]]) -> int | None:
    """Frage den Nutzer nach einem Gerät und gib die Device-ID zurück."""
    if not input_devices:
        print("❌ Keine Eingabegeräte gefunden.")
        return None

    default_input = sd.query_devices(kind="input")
    default_id = default_input.get("index")
    print(f"Standard-Eingabe: {default_input['name']} (ID: {default_id})")

    while True:
        choice = input("Bitte Mikrofon-ID wählen (Enter = Standard): ").strip()
        if choice == "":
            return default_id
        try:
            device_id = int(choice)
        except ValueError:
            print("❌ Ungültige Eingabe. Bitte eine Zahl eingeben.")
            continue

        if any(device_id == dev_id for dev_id, _ in input_devices):
            return device_id
        print("❌ Diese ID ist kein Eingabegerät.")


def play_beep(samplerate: int = 16000, duration: float = 0.2, freq: float = 880.0) -> None:
    """Spiele einen kurzen Piepton ab."""
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    tone = 0.2 * np.sin(2 * np.pi * freq * t).astype(np.float32)
    sd.play(tone, samplerate=samplerate)
    sd.wait()


def record_and_playback(device_id: int | None, duration: float = 5.0, samplerate: int = 16000) -> None:
    """Nimmt Audio auf und spielt es direkt wieder ab."""
    print("\nBitte nach dem Piepton ein paar Sätze sprechen.")
    time.sleep(0.5)
    play_beep(samplerate=samplerate)

    print(f"Aufnahme läuft ({duration:.1f}s)...")
    recording = sd.rec(
        int(duration * samplerate),
        samplerate=samplerate,
        channels=1,
        dtype="float32",
        device=device_id,
    )
    sd.wait()
    print("Aufnahme beendet. Wiedergabe startet...")
    sd.play(recording, samplerate=samplerate)
    sd.wait()
    print("Fertig.")


def main() -> None:
    input_devices = list_input_devices()
    device_id = prompt_for_device(input_devices)
    if device_id is None:
        sys.exit(1)

    try:
        device_info = sd.query_devices(device_id, kind="input")
        print(f"\nVerwende: {device_info['name']} (ID: {device_id})")
    except Exception:
        print(f"\nVerwende Gerät ID: {device_id}")

    record_and_playback(device_id=device_id)


if __name__ == "__main__":
    main()
