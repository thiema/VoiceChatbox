from __future__ import annotations
import io
import wave
import json
import numpy as np
import sounddevice as sd
from typing import Callable, Optional
from pathlib import Path

from .audio_io import _resolve_device_id
from .oled_display import OledDisplay


class VoskSpeechRecognition:
    """Lokale Spracherkennung mit Vosk (Deutsch)."""
    
    def __init__(self, model_path: str, device: Optional[str | int] = None):
        """
        Initialisiere Vosk-Spracherkennung.
        
        Args:
            model_path: Pfad zum Vosk-Modell (z. B. "models/vosk-model-de-0.22")
            device: Audio-Eingabegerät (ID, Name oder None für Standard)
        """
        self.model_path = Path(model_path)
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.recognizer = None
        self._init_model()
    
    def _init_model(self) -> None:
        """Initialisiere das Vosk-Modell."""
        try:
            from vosk import Model, SetLogLevel
            
            # Setze Log-Level (optional, reduziert Ausgaben)
            SetLogLevel(-1)
            
            if not self.model_path.exists():
                raise FileNotFoundError(
                    f"Vosk-Modell nicht gefunden: {self.model_path}\n"
                    f"Bitte Modell herunterladen von: https://alphacephei.com/vosk/models\n"
                    f"Empfohlen für Deutsch: vosk-model-de-0.22 (klein) oder vosk-model-de-0.6-900k (groß)"
                )
            
            print(f"Lade Vosk-Modell von: {self.model_path}")
            model = Model(str(self.model_path))
            self.recognizer = model
            print("Vosk-Modell geladen.")
        except ImportError:
            raise ImportError(
                "Vosk ist nicht installiert. Bitte installieren mit:\n"
                "pip install vosk"
            )
        except Exception as e:
            raise RuntimeError(f"Fehler beim Laden des Vosk-Modells: {e}")
    
    def transcribe_audio(self, wav_bytes: bytes) -> str:
        """
        Transkribiere Audio-Daten zu Text.
        
        Args:
            wav_bytes: WAV-formatierte Audio-Daten
            
        Returns:
            Erkannten Text (leer wenn nichts erkannt)
        """
        try:
            from vosk import KaldiRecognizer
            
            # Erstelle Recognizer für diesen Chunk
            rec = KaldiRecognizer(self.recognizer, self.samplerate)
            rec.SetWords(False)  # Nur Text, keine Wort-Timestamps
            
            # Lese WAV-Daten
            wav_file = wave.open(io.BytesIO(wav_bytes))
            
            text_parts = []
            while True:
                data = wav_file.readframes(4000)  # 4000 Frames pro Chunk
                if len(data) == 0:
                    break
                
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    if result.get("text"):
                        text_parts.append(result["text"])
            
            # Finale Erkennung
            final_result = json.loads(rec.FinalResult())
            if final_result.get("text"):
                text_parts.append(final_result["text"])
            
            return " ".join(text_parts).strip()
        except Exception as e:
            print(f"Fehler bei Vosk-Transkription: {e}")
            return ""
    
    def transcribe_audio_stream(self, audio_data: np.ndarray) -> str:
        """
        Transkribiere Audio-Daten direkt aus numpy-Array.
        
        Args:
            audio_data: numpy-Array mit Audio-Daten (int16, mono, 16kHz)
            
        Returns:
            Erkannten Text
        """
        try:
            from vosk import KaldiRecognizer
            
            # Erstelle Recognizer mit optimierten Einstellungen
            rec = KaldiRecognizer(self.recognizer, self.samplerate)
            rec.SetWords(False)  # Nur Text, keine Wort-Timestamps
            
            # Alternative: SetWords(True) für mehr Kontext, aber langsamer
            # rec.SetWords(True)
            
            # Konvertiere zu bytes
            audio_bytes = audio_data.tobytes()
            
            # Verarbeite in kleineren Chunks für bessere Erkennung
            # Kleinere Chunks = häufigeres Processing = bessere Ergebnisse
            chunk_size = 4000 * 2  # 4000 Frames * 2 bytes (int16) = ~0.5 Sekunden
            text_parts = []
            
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                if len(chunk) == 0:
                    break
                    
                if rec.AcceptWaveform(chunk):
                    result = json.loads(rec.Result())
                    if result.get("text"):
                        text_parts.append(result["text"])
            
            # Finale Erkennung (wichtig für letzten Teil)
            final_result = json.loads(rec.FinalResult())
            if final_result.get("text"):
                text_parts.append(final_result["text"])
            
            return " ".join(text_parts).strip()
        except Exception as e:
            print(f"Fehler bei Vosk-Stream-Transkription: {e}")
            return ""


class LiveVoskRecognition:
    """Live Spracherkennung mit Vosk (lokal, offline)."""
    
    def __init__(self, model_path: str, device: Optional[str | int] = None, 
                 chunk_duration: float = 3.0, enable_audio_processing: bool = True,
                 enable_semantic: bool = True, language: str = "de"):
        """
        Initialisiere Live-Vosk-Spracherkennung.
        
        Args:
            model_path: Pfad zum Vosk-Modell
            device: Audio-Eingabegerät
            chunk_duration: Dauer pro Chunk in Sekunden (länger = besser, aber langsamer)
            enable_audio_processing: Audio-Vorverarbeitung aktivieren (Normalisierung, etc.)
            enable_semantic: Semantische Satzerkennung aktivieren
            language: Sprache für semantische Analyse
        """
        self.vosk = VoskSpeechRecognition(model_path, device)
        self.samplerate = 16000
        self.chunk_duration = chunk_duration  # Längere Chunks = besserer Kontext
        self.enable_audio_processing = enable_audio_processing
        self.is_running = False
        self.current_text = ""
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self.enable_semantic = enable_semantic
        self.semantic_processor = SemanticSpeechRecognition(language=language) if enable_semantic else None
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalisiere Audio für bessere Erkennung."""
        # Konvertiere zu float32 für Verarbeitung
        audio_float = audio.astype(np.float32) / 32768.0
        
        # Entferne DC-Offset
        audio_float = audio_float - np.mean(audio_float)
        
        # Normalisiere auf -1.0 bis 1.0 (verhindert Clipping)
        max_val = np.max(np.abs(audio_float))
        if max_val > 0:
            # Leichte Normalisierung (nicht zu aggressiv, sonst Verzerrung)
            audio_float = audio_float / (max_val * 1.1)  # 10% Headroom
        
        # Konvertiere zurück zu int16
        audio_normalized = (audio_float * 32767.0).astype(np.int16)
        return audio_normalized
    
    def _apply_highpass_filter(self, audio: np.ndarray, cutoff: float = 80.0) -> np.ndarray:
        """Einfacher High-Pass Filter um tiefe Frequenzen zu entfernen."""
        try:
            from scipy import signal
            nyquist = self.samplerate / 2
            normal_cutoff = cutoff / nyquist
            b, a = signal.butter(2, normal_cutoff, btype='high', analog=False)
            audio_float = audio.astype(np.float32) / 32768.0
            filtered = signal.filtfilt(b, a, audio_float)
            return (filtered * 32767.0).astype(np.int16)
        except ImportError:
            # Falls scipy nicht verfügbar, keine Filterung
            return audio
    
    def _detect_speech(self, audio: np.ndarray, threshold: float = 0.01) -> bool:
        """Einfache Voice Activity Detection (VAD)."""
        # Berechne RMS (Root Mean Square) für Signalpegel
        audio_float = audio.astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        return rms > threshold
    
    def _record_chunk(self) -> np.ndarray:
        """Nimmt einen Audio-Chunk auf und gibt numpy-Array zurück."""
        channels = 1
        dtype = "int16"
        frames_to_record = int(self.samplerate * self.chunk_duration)
        
        recording = sd.rec(
            frames_to_record,
            samplerate=self.samplerate,
            channels=channels,
            dtype=dtype,
            device=self.vosk.device_id
        )
        sd.wait()
        
        # Konvertiere zu mono (falls stereo)
        if len(recording.shape) > 1:
            recording = recording[:, 0]
        
        # Audio-Vorverarbeitung für bessere Erkennung
        if self.enable_audio_processing:
            # High-Pass Filter (entfernt tiefe Frequenzen/Rauschen)
            recording = self._apply_highpass_filter(recording, cutoff=80.0)
            
            # Normalisierung
            recording = self._normalize_audio(recording)
        
        return recording
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display mit Laufband-Text."""
        if self.oled and self.oled.device:
            self.oled.show_text_scroll(text)
    
    def _process_chunk(self) -> None:
        """Nimmt einen Chunk auf, transkribiert ihn und aktualisiert das Display."""
        try:
            # Audio aufnehmen
            audio_data = self._record_chunk()
            
            if not self.is_running:
                return
            
            # Voice Activity Detection - überspringe leise Chunks
            if not self._detect_speech(audio_data, threshold=0.005):
                # Keine Sprache erkannt, überspringe
                return
            
            # Transkribieren (direkt mit numpy-Array)
            text = self.vosk.transcribe_audio_stream(audio_data)
            
            if text:
                # Text aktualisieren
                if self.current_text:
                    self.current_text += " " + text
                else:
                    self.current_text = text
                
                # Semantische Satzerkennung
                if self.semantic_processor:
                    result = self.semantic_processor.process_text(self.current_text)
                    
                    # Zeige neue Sätze mit semantischer Info
                    for info in result['semantic_info']:
                        sentence = info['sentence']
                        analysis = info['analysis']
                        sentence_type = info['type']
                        
                        type_emoji = {
                            'question': '❓',
                            'imperative': '❗',
                            'exclamation': '❗',
                            'statement': '💬'
                        }
                        emoji = type_emoji.get(sentence_type, '💬')
                        
                        print(f"{emoji} [{sentence_type.upper()}] {sentence.text}")
                        if analysis['sentiment'] != 'neutral':
                            print(f"   Sentiment: {analysis['sentiment']}")
                    
                    # Verwende satz-basierte Anzeige für Display
                    display_text = self.semantic_processor.get_display_text(max_sentences=2)
                    if display_text:
                        self._update_display(display_text)
                    else:
                        self._update_display(self.current_text)
                else:
                    # Standard: Einfache Text-Anzeige
                    self._update_display(self.current_text)
                
                # Callback aufrufen
                if self.text_callback:
                    self.text_callback(self.current_text)
                
                print(f"Erkannt: {text}")
                print(f"Gesamt: {self.current_text}")
            else:
                # Kein Text erkannt - könnte auf schlechte Audio-Qualität hindeuten
                pass
        except Exception as e:
            print(f"Fehler bei Verarbeitung: {e}")
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte die Live-Spracherkennung."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        
        if self.oled:
            self.oled.show_listening()
        
        print("Live-Spracherkennung (Vosk, lokal) gestartet. Strg+C zum Beenden.")
        print("Sprich jetzt...")
        
        try:
            # Kontinuierliche Verarbeitung
            while self.is_running:
                self._process_chunk()
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stoppe die Live-Spracherkennung."""
        self.is_running = False
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_live_vosk_recognition(model_path: Optional[str] = None):
    """Hauptfunktion für Live-Spracherkennung mit Vosk."""
    import os
    import time
    from .config import load_settings
    
    # Modell-Pfad aus Parameter, Umgebungsvariable oder Standard
    if model_path is None:
        settings = load_settings()
        model_path = settings.vosk_model_path or os.getenv("VOSK_MODEL_PATH", "models/vosk-model-de-0.22")
    
    settings = load_settings()
    
    # OLED initialisieren
    oled = None
    try:
        from .oled_display import OledDisplay
        oled = OledDisplay()
        if not oled.init():
            print("OLED konnte nicht initialisiert werden. Fortfahren ohne Display.")
            oled = None
        else:
            oled.show_ready()
            time.sleep(1)
    except Exception as e:
        print(f"OLED-Fehler: {e}. Fortfahren ohne Display.")
        oled = None
    
    # Live-Spracherkennung starten
    recognizer = LiveVoskRecognition(
        model_path=model_path,
        device=settings.audio_input_device
    )
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_live_vosk_recognition(model_path)
