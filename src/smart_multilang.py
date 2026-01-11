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
from .sentence_detection import SemanticSpeechRecognition


class SmartMultiLanguageVoskRecognition:
    """
    Intelligente mehrsprachige Spracherkennung:
    - Deutsch als Hauptsprache für Kontext und Semantik
    - Englisch nur für bestimmte ergänzende Wörter (Internet, Computer, Raspberry Pi, cool, etc.)
    """
    
    def __init__(self, model_path_de: str, model_path_en: Optional[str] = None,
                 device: Optional[str | int] = None,
                 chunk_duration: float = 3.0, enable_audio_processing: bool = True,
                 enable_semantic: bool = True):
        """
        Initialisiere intelligente mehrsprachige Spracherkennung.
        
        Args:
            model_path_de: Pfad zum deutschen Vosk-Modell
            model_path_en: Pfad zum englischen Vosk-Modell (optional)
            device: Audio-Eingabegerät
            chunk_duration: Dauer pro Chunk in Sekunden
            enable_audio_processing: Audio-Vorverarbeitung aktivieren
            enable_semantic: Semantische Satzerkennung aktivieren
        """
        self.model_path_de = Path(model_path_de)
        self.model_path_en = Path(model_path_en) if model_path_en else None
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.chunk_duration = chunk_duration
        self.enable_audio_processing = enable_audio_processing
        self.enable_semantic = enable_semantic
        
        # Englische Wörter, die im deutschen Kontext verwendet werden
        self.english_words = {
            'internet', 'computer', 'raspberry', 'pi', 'python', 'linux', 'wifi',
            'cool', 'okay', 'ok', 'yes', 'no', 'hello', 'hi', 'thanks', 'please',
            'software', 'hardware', 'server', 'network', 'data', 'file', 'folder',
            'error', 'bug', 'update', 'install', 'download', 'upload', 'email',
            'website', 'online', 'offline', 'app', 'application', 'program',
            'code', 'coding', 'developer', 'programming', 'algorithm', 'api',
            'usb', 'hdmi', 'gpu', 'cpu', 'ram', 'ssd', 'hdd', 'led', 'oled',
            'bluetooth', 'nfc', 'qr', 'gps', 'wlan', 'ethernet', 'router',
            'smartphone', 'tablet', 'laptop', 'desktop', 'monitor', 'keyboard',
            'mouse', 'touchpad', 'speaker', 'microphone', 'headphone', 'camera',
            'video', 'audio', 'stream', 'streaming', 'podcast', 'youtube',
            'facebook', 'twitter', 'instagram', 'whatsapp', 'telegram', 'skype',
            'zoom', 'teams', 'slack', 'discord', 'github', 'git', 'docker',
            'cloud', 'aws', 'azure', 'google', 'microsoft', 'apple', 'amazon',
            'netflix', 'spotify', 'amazon', 'alexa', 'siri', 'google', 'assistant'
        }
        
        self.model_de = None
        self.model_en = None
        self.is_running = False
        self.current_text = ""
        self.last_processed_length = 0  # Länge des zuletzt verarbeiteten Textes
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self.semantic_processor = SemanticSpeechRecognition(language="de") if enable_semantic else None
        
        self._init_models()
    
    def _init_models(self) -> None:
        """Initialisiere Sprachmodelle."""
        try:
            from vosk import Model, SetLogLevel
            
            SetLogLevel(-1)
            
            # Deutsches Modell (erforderlich)
            if not self.model_path_de.exists():
                raise RuntimeError(f"Deutsches Modell nicht gefunden: {self.model_path_de}")
            
            print(f"Lade deutsches Vosk-Modell: {self.model_path_de}")
            self.model_de = Model(str(self.model_path_de))
            print("✅ Deutsches Modell geladen.")
            
            # Englisches Modell (optional)
            if self.model_path_en and self.model_path_en.exists():
                print(f"Lade englisches Vosk-Modell: {self.model_path_en}")
                self.model_en = Model(str(self.model_path_en))
                print("✅ Englisches Modell geladen.")
            elif self.model_path_en:
                print(f"⚠️  Englisches Modell nicht gefunden: {self.model_path_en}")
                print("   Fortfahren ohne englische Ergänzungen.")
        
        except ImportError:
            raise ImportError(
                "Vosk ist nicht installiert. Bitte installieren mit:\n"
                "pip install vosk"
            )
        except Exception as e:
            raise RuntimeError(f"Fehler beim Laden der Vosk-Modelle: {e}")
    
    def _transcribe_audio_de(self, audio_data: np.ndarray) -> str:
        """Transkribiere Audio mit deutschem Modell."""
        from vosk import KaldiRecognizer
        
        rec = KaldiRecognizer(self.model_de, self.samplerate)
        rec.SetWords(False)
        
        # Konvertiere numpy-Array zu WAV-Bytes
        wav_bytes = self._audio_to_wav_bytes(audio_data)
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
        
        return " ".join(text_parts).strip()
    
    def _transcribe_audio_en(self, audio_data: np.ndarray) -> str:
        """Transkribiere Audio mit englischem Modell (nur wenn verfügbar)."""
        if not self.model_en:
            return ""
        
        from vosk import KaldiRecognizer
        
        rec = KaldiRecognizer(self.model_en, self.samplerate)
        rec.SetWords(False)
        
        # Konvertiere numpy-Array zu WAV-Bytes
        wav_bytes = self._audio_to_wav_bytes(audio_data)
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
        
        return " ".join(text_parts).strip()
    
    def _audio_to_wav_bytes(self, audio_data: np.ndarray) -> bytes:
        """Konvertiere numpy-Array zu WAV-Bytes."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.samplerate)
            wf.writeframes(audio_data.tobytes())
        return buf.getvalue()
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """Normalisiere Audio (DC-Offset entfernen, Normalisierung)."""
        # Konvertiere zu float
        audio_float = audio.astype(np.float32) / 32768.0
        
        # Entferne DC-Offset
        audio_float = audio_float - np.mean(audio_float)
        
        # Normalisiere auf -1.0 bis 1.0
        max_val = np.max(np.abs(audio_float))
        if max_val > 0:
            audio_float = audio_float / (max_val * 1.1)
        
        # Konvertiere zurück zu int16
        audio_normalized = (audio_float * 32767.0).astype(np.int16)
        return audio_normalized
    
    def _detect_speech(self, audio: np.ndarray, threshold: float = 0.01) -> bool:
        """Einfache Voice Activity Detection (VAD)."""
        audio_float = audio.astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        return rms > threshold
    
    def _merge_texts(self, text_de: str, text_en: str) -> str:
        """
        Kombiniere deutsche und englische Erkennung intelligent.
        
        Strategie:
        1. Verwende deutschen Text als Basis
        2. Ergänze nur englische Wörter, die in der Liste stehen
        3. Ersetze deutsche Fehlerkennungen durch englische, wenn passend
        """
        if not text_de:
            return text_en if text_en else ""
        
        if not text_en:
            return text_de
        
        # Teile beide Texte in Wörter
        words_de = text_de.lower().split()
        words_en = text_en.lower().split()
        
        # Erstelle Mapping: deutsche Wörter -> mögliche englische Ersetzungen
        result_words = []
        en_index = 0
        
        for word_de in words_de:
            # Prüfe, ob es ein englisches Wort gibt, das besser passt
            best_match = None
            best_similarity = 0.0
            
            # Suche in englischem Text nach ähnlichen Wörtern
            for i, word_en in enumerate(words_en[en_index:], start=en_index):
                # Prüfe, ob englisches Wort in der Liste steht
                if word_en in self.english_words:
                    # Prüfe Ähnlichkeit
                    similarity = self._word_similarity(word_de, word_en)
                    if similarity > 0.7 and similarity > best_similarity:
                        best_match = word_en
                        best_similarity = similarity
                        en_index = i + 1
                        break
            
            if best_match:
                result_words.append(best_match)
            else:
                result_words.append(word_de)
        
        # Füge verbleibende englische Wörter hinzu, wenn sie in der Liste stehen
        for word_en in words_en[en_index:]:
            if word_en in self.english_words:
                result_words.append(word_en)
        
        return " ".join(result_words)
    
    def _word_similarity(self, word1: str, word2: str) -> float:
        """Berechne Ähnlichkeit zwischen zwei Wörtern."""
        from difflib import SequenceMatcher
        return SequenceMatcher(None, word1.lower(), word2.lower()).ratio()
    
    def _record_chunk(self) -> np.ndarray:
        """Nimmt einen Audio-Chunk auf."""
        frames_to_record = int(self.samplerate * self.chunk_duration)
        
        recording = sd.rec(
            frames_to_record,
            samplerate=self.samplerate,
            channels=1,
            dtype="int16",
            device=self.device_id
        )
        sd.wait()
        
        if self.enable_audio_processing:
            recording = self._normalize_audio(recording)
        
        return recording.flatten()
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display."""
        if self.oled and self.oled.device:
            self.oled.show_text_scroll(text)
    
    def _process_chunk(self) -> None:
        """Verarbeite einen Audio-Chunk."""
        try:
            # Audio aufnehmen
            audio_data = self._record_chunk()
            
            if not self.is_running:
                return
            
            # Voice Activity Detection
            if not self._detect_speech(audio_data, threshold=0.005):
                return
            
            # Transkribiere mit deutschem Modell (Hauptsprache)
            text_de = self._transcribe_audio_de(audio_data)
            
            # Transkribiere mit englischem Modell (nur wenn verfügbar)
            text_en = ""
            if self.model_en:
                text_en = self._transcribe_audio_en(audio_data)
            
            # Kombiniere Texte intelligent
            text = self._merge_texts(text_de, text_en)
            
            if text:
                # Nur neuen Text hinzufügen (verhindert Doppel-Ausgabe)
                # Prüfe, ob Text bereits verarbeitet wurde
                if self.current_text:
                    # Prüfe, ob der neue Text bereits im letzten Teil des current_text enthalten ist
                    # (verhindert Doppel-Ausgabe bei überlappenden Chunks)
                    current_lower = self.current_text.lower()
                    text_lower = text.lower()
                    
                    # Prüfe, ob der neue Text bereits am Ende des current_text steht
                    if current_lower.endswith(text_lower) or text_lower in current_lower[-len(text_lower)*2:]:
                        # Überspringe, wenn bereits vorhanden
                        return
                    
                    self.current_text += " " + text
                else:
                    self.current_text = text
                
                # Semantische Satzerkennung mit kontext-basierter Korrektur
                if self.semantic_processor:
                    # Verwende nur den neuen Teil für Verarbeitung
                    result = self.semantic_processor.process_text(self.current_text)
                    
                    # Verwende korrigierten Text
                    corrected_text = result.get('corrected_text', self.current_text)
                    self.current_text = corrected_text
                    
                    # Zeige Korrekturen an
                    corrections = result.get('corrections', [])
                    if corrections:
                        print(f"🔧 {len(corrections)} Korrektur(en) angewendet")
                    
                    # Zeige Kontext-Info
                    context = result.get('context')
                    if context and context.domain:
                        print(f"📋 Kontext: {context.domain} (Themen: {', '.join(context.topics)})")
                    
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
                # Kein Text erkannt
                pass
        except Exception as e:
            print(f"Fehler bei Verarbeitung: {e}")
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte die Live-Spracherkennung."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        self.last_processed_length = 0
        
        if self.oled:
            self.oled.show_listening()
        
        print("="*60)
        print("Intelligente mehrsprachige Spracherkennung (DE + EN)")
        print("="*60)
        print("Deutsch: Hauptsprache für Kontext und Semantik")
        if self.model_en:
            print("Englisch: Ergänzungen für bestimmte Wörter")
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
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback


def run_smart_multilang_recognition(model_path_de: str, model_path_en: Optional[str] = None,
                                    device: Optional[str | int] = None):
    """Hauptfunktion für intelligente mehrsprachige Spracherkennung."""
    import time
    
    # Initialisiere Erkennung
    recognizer = SmartMultiLanguageVoskRecognition(
        model_path_de=model_path_de,
        model_path_en=model_path_en,
        device=device
    )
    
    # OLED initialisieren
    oled = None
    try:
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
    
    # Starte Erkennung
    recognizer.start(oled=oled)
