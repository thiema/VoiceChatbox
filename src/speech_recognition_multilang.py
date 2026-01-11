from __future__ import annotations
import io
import wave
import json
import numpy as np
import sounddevice as sd
from typing import Callable, Optional, Dict, List, Tuple
from pathlib import Path

from .audio_io import _resolve_device_id
from .oled_display import OledDisplay


class MultiLanguageVoskRecognition:
    """Mehrsprachige Spracherkennung mit mehreren Vosk-Modellen."""
    
    def __init__(self, model_paths: Dict[str, str], device: Optional[str | int] = None):
        """
        Initialisiere mehrsprachige Vosk-Spracherkennung.
        
        Args:
            model_paths: Dictionary mit Sprache -> Modell-Pfad
                        z.B. {"de": "models/vosk-model-de-0.22", "en": "models/vosk-model-en-us-0.22"}
            device: Audio-Eingabegerät
        """
        self.model_paths = {lang: Path(path) for lang, path in model_paths.items()}
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.models: Dict[str, any] = {}
        self._init_models()
    
    def _init_models(self) -> None:
        """Initialisiere alle Sprachmodelle."""
        try:
            from vosk import Model, SetLogLevel
            
            SetLogLevel(-1)
            
            for lang, model_path in self.model_paths.items():
                if not model_path.exists():
                    print(f"⚠️  Warnung: Modell für {lang} nicht gefunden: {model_path}")
                    continue
                
                print(f"Lade Vosk-Modell für {lang.upper()}: {model_path}")
                try:
                    model = Model(str(model_path))
                    self.models[lang] = model
                    print(f"✅ Modell für {lang.upper()} geladen.")
                except Exception as e:
                    print(f"❌ Fehler beim Laden des Modells für {lang}: {e}")
            
            if not self.models:
                raise RuntimeError("Keine Modelle konnten geladen werden!")
            
            print(f"✅ {len(self.models)} Modell(e) geladen: {', '.join(self.models.keys())}")
            
        except ImportError:
            raise ImportError(
                "Vosk ist nicht installiert. Bitte installieren mit:\n"
                "pip install vosk"
            )
        except Exception as e:
            raise RuntimeError(f"Fehler beim Laden der Vosk-Modelle: {e}")
    
    def transcribe_audio(self, wav_bytes: bytes, languages: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Transkribiere Audio mit allen verfügbaren Modellen.
        
        Args:
            wav_bytes: WAV-formatierte Audio-Daten
            languages: Liste der zu verwendenden Sprachen (None = alle)
            
        Returns:
            Dictionary mit Sprache -> erkannten Text
        """
        results = {}
        languages_to_use = languages or list(self.models.keys())
        
        for lang in languages_to_use:
            if lang not in self.models:
                continue
            
            try:
                from vosk import KaldiRecognizer
                
                rec = KaldiRecognizer(self.models[lang], self.samplerate)
                rec.SetWords(False)
                
                wav_file = wave.open(io.BytesIO(wav_bytes))
                text_parts = []
                
                while True:
                    data = wav_file.readframes(4000)
                    if len(data) == 0:
                        break
                    
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        if result.get("text"):
                            text_parts.append(result["text"])
                
                final_result = json.loads(rec.FinalResult())
                if final_result.get("text"):
                    text_parts.append(final_result["text"])
                
                text = " ".join(text_parts).strip()
                # Stelle sicher, dass Leerzeichen zwischen Wörtern vorhanden sind
                # Normalisiere mehrfache Leerzeichen zu einem
                text = re.sub(r'\s+', ' ', text)
                if text:
                    results[lang] = text
                    
            except Exception as e:
                print(f"Fehler bei Transkription mit {lang}: {e}")
        
        return results
    
    def transcribe_audio_best(self, wav_bytes: bytes, languages: Optional[List[str]] = None) -> Tuple[str, str]:
        """
        Transkribiere Audio und wähle das beste Ergebnis.
        
        Args:
            wav_bytes: WAV-formatierte Audio-Daten
            languages: Liste der zu verwendenden Sprachen (None = alle)
            
        Returns:
            Tuple (Sprache, Text) des besten Ergebnisses
        """
        results = self.transcribe_audio(wav_bytes, languages)
        
        if not results:
            return ("", "")
        
        # Wähle das Ergebnis mit dem längsten Text (meist das beste)
        best_lang = max(results.keys(), key=lambda k: len(results[k]))
        return (best_lang, results[best_lang])
    
    def transcribe_audio_combined(self, wav_bytes: bytes, languages: Optional[List[str]] = None) -> str:
        """
        Transkribiere Audio und kombiniere Ergebnisse aller Sprachen.
        
        Args:
            wav_bytes: WAV-formatierte Audio-Daten
            languages: Liste der zu verwendenden Sprachen (None = alle)
            
        Returns:
            Kombinierter Text (alle Sprachen)
        """
        results = self.transcribe_audio(wav_bytes, languages)
        
        if not results:
            return ""
        
        # Kombiniere alle Ergebnisse
        combined = " ".join(results.values())
        return combined.strip()


class LiveMultiLanguageVoskRecognition:
    """Live mehrsprachige Spracherkennung mit Vosk."""
    
    def __init__(self, model_paths: Dict[str, str], device: Optional[str | int] = None,
                 chunk_duration: float = 3.0, mode: str = "best"):
        """
        Initialisiere Live mehrsprachige Spracherkennung.
        
        Args:
            model_paths: Dictionary mit Sprache -> Modell-Pfad
            device: Audio-Eingabegerät
            chunk_duration: Dauer pro Chunk in Sekunden
            mode: "best" = bestes Ergebnis, "combined" = alle kombinieren, "all" = alle anzeigen
        """
        self.vosk = MultiLanguageVoskRecognition(model_paths, device)
        self.samplerate = 16000
        self.chunk_duration = chunk_duration
        self.mode = mode
        self.is_running = False
        self.current_text = ""
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback
    
    def _record_chunk(self) -> np.ndarray:
        """Nimmt einen Audio-Chunk auf."""
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
        
        if len(recording.shape) > 1:
            recording = recording[:, 0]
        
        return recording
    
    def _audio_to_wav_bytes(self, audio_data: np.ndarray) -> bytes:
        """Konvertiere numpy-Array zu WAV-Bytes."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.samplerate)
            wf.writeframes(audio_data.tobytes())
        return buf.getvalue()
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display."""
        if self.oled and self.oled.device:
            self.oled.show_text_scroll(text)
    
    def _process_chunk(self) -> None:
        """Verarbeite einen Audio-Chunk."""
        try:
            audio_data = self._record_chunk()
            
            if not self.is_running:
                return
            
            wav_bytes = self._audio_to_wav_bytes(audio_data)
            
            # Transkribiere je nach Modus
            if self.mode == "best":
                lang, text = self.vosk.transcribe_audio_best(wav_bytes)
                if text:
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    print(f"[{lang.upper()}] {text}")
            
            elif self.mode == "combined":
                text = self.vosk.transcribe_audio_combined(wav_bytes)
                if text:
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    print(f"[KOMBINIERT] {text}")
            
            elif self.mode == "all":
                results = self.vosk.transcribe_audio(wav_bytes)
                if results:
                    for lang, text in results.items():
                        print(f"[{lang.upper()}] {text}")
                    # Verwende das beste Ergebnis für Display
                    best_lang = max(results.keys(), key=lambda k: len(results[k]))
                    text = results[best_lang]
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
            
            if self.current_text:
                self._update_display(self.current_text)
                if self.text_callback:
                    self.text_callback(self.current_text)
                
        except Exception as e:
            print(f"Fehler bei Verarbeitung: {e}")
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte die Live-Spracherkennung."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        
        if self.oled:
            self.oled.show_listening()
        
        print("="*60)
        print("Mehrsprachige Live-Spracherkennung (Vosk)")
        print("="*60)
        print(f"Modi: {', '.join(self.vosk.models.keys())}")
        print(f"Modus: {self.mode}")
        print("Strg+C zum Beenden.")
        print("="*60)
        print()
        
        try:
            while self.is_running:
                self._process_chunk()
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stoppe die Spracherkennung."""
        self.is_running = False
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_multilang_vosk_recognition(
    model_paths: Optional[Dict[str, str]] = None,
    mode: str = "best"
):
    """Hauptfunktion für mehrsprachige Live-Spracherkennung."""
    import os
    import time
    from .config import load_settings
    
    settings = load_settings()
    
    # Modell-Pfade aus Parameter oder Umgebungsvariablen
    if model_paths is None:
        model_paths = {}
        
        # Deutsch
        de_path = settings.vosk_model_path or os.getenv("VOSK_MODEL_PATH_DE", "models/vosk-model-de-0.22")
        if de_path:
            model_paths["de"] = de_path
        
        # Englisch
        en_path = os.getenv("VOSK_MODEL_PATH_EN", "models/vosk-model-en-us-0.22")
        if en_path:
            model_paths["en"] = en_path
    
    if not model_paths:
        print("❌ Keine Modell-Pfade angegeben!")
        print("   Setze VOSK_MODEL_PATH_DE und/oder VOSK_MODEL_PATH_EN in .env")
        return
    
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
    recognizer = LiveMultiLanguageVoskRecognition(
        model_paths=model_paths,
        device=settings.audio_input_device,
        mode=mode
    )
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    
    mode = "best"
    if "--combined" in sys.argv:
        mode = "combined"
    elif "--all" in sys.argv:
        mode = "all"
    
    run_multilang_vosk_recognition(mode=mode)
