from __future__ import annotations
import sys
import time
import sounddevice as sd
import numpy as np
from .config import load_settings

def list_audio_devices():
    """Liste alle verfügbaren Audio-Ein- und Ausgabegeräte."""
    print("\n=== Verfügbare Audio-Geräte ===\n")
    devices = sd.query_devices()
    print(f"{'ID':<4} {'Name':<40} {'Channels':<12} {'Sample Rate':<12} {'Default'}")
    print("-" * 90)
    
    default_input = sd.query_devices(kind='input')
    default_output = sd.query_devices(kind='output')
    
    for i, device in enumerate(devices):
        default_str = ""
        if device['name'] == default_input['name']:
            default_str += " [IN]"
        if device['name'] == default_output['name']:
            default_str += " [OUT]"
        
        channels_str = f"{device['max_input_channels']} in / {device['max_output_channels']} out"
        print(f"{i:<4} {device['name']:<40} {channels_str:<12} {device['default_samplerate']:<12.0f} {default_str}")
    
    print("\n=== Standard-Geräte ===")
    print(f"Standard-Eingabe: {default_input['name']} (ID: {default_input['index']})")
    print(f"Standard-Ausgabe: {default_output['name']} (ID: {default_output['index']})")
    print()

def test_microphone(device_id=None, duration=3, samplerate=16000):
    """Teste das Mikrofon: Aufnahme und Anzeige des Signalpegels."""
    print(f"\n=== Mikrofon-Test ===")
    print(f"Gerät: {device_id if device_id is not None else 'Standard'}")
    print(f"Dauer: {duration} Sekunden")
    print("Sprich jetzt ins Mikrofon...\n")
    
    try:
        if device_id is not None:
            device_info = sd.query_devices(device_id, kind='input')
            print(f"Verwende: {device_info['name']}")
            print(f"Kanäle: {device_info['max_input_channels']}")
            print(f"Sample Rate: {device_info['default_samplerate']} Hz\n")
        
        frames = []
        max_level = 0.0
        
        def callback(indata, frames, time, status):
            nonlocal max_level
            if status:
                print(f"Status: {status}", file=sys.stderr)
            # Berechne RMS (Root Mean Square) für Signalpegel
            level = np.sqrt(np.mean(indata**2))
            max_level = max(max_level, level)
            # Zeige einfache Pegelanzeige
            bar_length = int(level * 50)
            bar = "█" * bar_length + "░" * (50 - bar_length)
            print(f"\rPegel: {bar} {level:.4f}", end="", flush=True)
        
        with sd.InputStream(device=device_id, samplerate=samplerate, channels=1, 
                           dtype='float32', callback=callback):
            time.sleep(duration)
        
        print(f"\n\nMaximaler Pegel: {max_level:.4f}")
        if max_level < 0.01:
            print("⚠️  WARNUNG: Sehr niedriger Pegel! Prüfe:")
            print("   - Ist das Mikrofon angeschlossen?")
            print("   - Ist das richtige Gerät ausgewählt?")
            print("   - Sprichst du laut genug?")
        elif max_level > 0.5:
            print("⚠️  WARNUNG: Sehr hoher Pegel! Möglicherweise Verzerrung.")
        else:
            print("✓ Mikrofon funktioniert!")
        
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        return False
    
    return True

def test_speaker(device_id=None, frequency=440, duration=2, samplerate=44100):
    """Teste den Lautsprecher: Spiele einen Testton ab."""
    print(f"\n=== Lautsprecher-Test ===")
    print(f"Gerät: {device_id if device_id is not None else 'Standard'}")
    print(f"Frequenz: {frequency} Hz (Kammerton A)")
    print(f"Dauer: {duration} Sekunden")
    print("\nDu solltest jetzt einen Ton hören...\n")
    
    try:
        if device_id is not None:
            device_info = sd.query_devices(device_id, kind='output')
            print(f"Verwende: {device_info['name']}")
            print(f"Kanäle: {device_info['max_output_channels']}")
            print(f"Sample Rate: {device_info['default_samplerate']} Hz\n")
        
        # Erzeuge Sinuston
        t = np.linspace(0, duration, int(samplerate * duration), False)
        tone = np.sin(2 * np.pi * frequency * t).astype(np.float32)
        
        # Spiele ab
        sd.play(tone, samplerate=samplerate, device=device_id)
        sd.wait()
        
        print("✓ Testton abgespielt!")
        print("Hast du den Ton gehört? (j/n): ", end="")
        response = input().strip().lower()
        if response == 'j' or response == 'y':
            print("✓ Lautsprecher funktioniert!")
            return True
        else:
            print("⚠️  Kein Ton gehört. Prüfe:")
            print("   - Ist der Lautsprecher angeschlossen?")
            print("   - Ist das richtige Gerät ausgewählt?")
            print("   - Ist die Lautstärke aufgedreht?")
            return False
        
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        return False

def test_record_and_playback(device_input=None, device_output=None, duration=3, samplerate=16000):
    """Teste Aufnahme und Wiedergabe: Recorde Audio und spiele es sofort ab."""
    print(f"\n=== Aufnahme & Wiedergabe-Test ===")
    print(f"Eingabe: {device_input if device_input is not None else 'Standard'}")
    print(f"Ausgabe: {device_output if device_output is not None else 'Standard'}")
    print(f"Dauer: {duration} Sekunden")
    print("\nSprich jetzt ins Mikrofon...")
    
    try:
        # Aufnahme
        print("Aufnahme läuft...")
        recording = sd.rec(int(samplerate * duration), samplerate=samplerate, 
                          channels=1, dtype='float32', device=device_input)
        sd.wait()
        print("✓ Aufnahme abgeschlossen")
        
        # Wiedergabe
        print("Spiele Aufnahme ab...")
        sd.play(recording, samplerate=samplerate, device=device_output)
        sd.wait()
        print("✓ Wiedergabe abgeschlossen")
        
        print("\nHast du deine Stimme gehört? (j/n): ", end="")
        response = input().strip().lower()
        if response == 'j' or response == 'y':
            print("✓ Audio-Pipeline funktioniert vollständig!")
            return True
        else:
            print("⚠️  Problem erkannt. Prüfe Geräteauswahl und Verbindungen.")
            return False
        
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        return False

def run_audio_test():
    """Hauptfunktion für Audio-Tests."""
    if "--list" in sys.argv:
        list_audio_devices()
        return
    
    if "--mic" in sys.argv:
        device_id = None
        if "--device" in sys.argv:
            try:
                idx = sys.argv.index("--device")
                device_id = int(sys.argv[idx + 1])
            except (ValueError, IndexError):
                print("❌ Ungültige Geräte-ID")
                return
        
        duration = 3
        if "--duration" in sys.argv:
            try:
                idx = sys.argv.index("--duration")
                duration = int(sys.argv[idx + 1])
            except (ValueError, IndexError):
                pass
        
        test_microphone(device_id=device_id, duration=duration)
        return
    
    if "--speaker" in sys.argv:
        device_id = None
        if "--device" in sys.argv:
            try:
                idx = sys.argv.index("--device")
                device_id = int(sys.argv[idx + 1])
            except (ValueError, IndexError):
                print("❌ Ungültige Geräte-ID")
                return
        
        test_speaker(device_id=device_id)
        return
    
    if "--full" in sys.argv:
        # Vollständiger Test mit Konfiguration aus .env
        try:
            settings = load_settings()
            input_id = None
            output_id = None
            
            if settings.audio_input_device:
                # Versuche Gerätename oder ID zu finden
                devices = sd.query_devices()
                for i, dev in enumerate(devices):
                    if settings.audio_input_device.lower() in dev['name'].lower():
                        input_id = i
                        break
                if input_id is None:
                    try:
                        input_id = int(settings.audio_input_device)
                    except ValueError:
                        pass
            
            if settings.audio_output_device:
                devices = sd.query_devices()
                for i, dev in enumerate(devices):
                    if settings.audio_output_device.lower() in dev['name'].lower():
                        output_id = i
                        break
                if output_id is None:
                    try:
                        output_id = int(settings.audio_output_device)
                    except ValueError:
                        pass
            
            print("=== Vollständiger Audio-Test ===")
            print(f"Konfiguration aus .env:")
            print(f"  Eingabe: {settings.audio_input_device or 'Standard'}")
            print(f"  Ausgabe: {settings.audio_output_device or 'Standard'}\n")
            
            list_audio_devices()
            
            print("\n1. Mikrofon-Test")
            test_microphone(device_id=input_id, duration=3)
            
            print("\n2. Lautsprecher-Test")
            test_speaker(device_id=output_id)
            
            print("\n3. Aufnahme & Wiedergabe-Test")
            test_record_and_playback(device_input=input_id, device_output=output_id, duration=3)
            
        except Exception as e:
            print(f"❌ Fehler beim Laden der Konfiguration: {e}")
            print("Führe Tests ohne .env-Konfiguration durch...\n")
            list_audio_devices()
            test_microphone()
            test_speaker()
            test_record_and_playback()
        return
    
    # Standard: Zeige Hilfe
    print("""
Audio-Test-Skript für VoiceChatbox

Verwendung:
  python -m src.audio_test --list                    # Liste alle Audio-Geräte
  python -m src.audio_test --mic                     # Teste Mikrofon (Standard-Gerät)
  python -m src.audio_test --mic --device 2          # Teste Mikrofon (Gerät ID 2)
  python -m src.audio_test --mic --duration 5        # Teste Mikrofon für 5 Sekunden
  python -m src.audio_test --speaker                 # Teste Lautsprecher (Standard-Gerät)
  python -m src.audio_test --speaker --device 1      # Teste Lautsprecher (Gerät ID 1)
  python -m src.audio_test --full                    # Vollständiger Test (mit .env-Konfiguration)

Beispiele:
  # Erst Geräte auflisten
  python -m src.audio_test --list
  
  # Dann einzelne Geräte testen
  python -m src.audio_test --mic --device 2
  python -m src.audio_test --speaker --device 1
  
  # Vollständiger Test mit Konfiguration
  python -m src.audio_test --full
""")

if __name__ == "__main__":
    run_audio_test()

