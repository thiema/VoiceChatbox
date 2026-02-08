from __future__ import annotations
import io
import wave
import json
import re
import time
import numpy as np
import sounddevice as sd
from typing import Callable, Optional
from pathlib import Path

from .audio_io import _resolve_device_id, select_input_device, wait_for_playback_end, play_beep_sequence, play_hangup_tone
from .oled_display import OledDisplay
from .sentence_detection import SemanticSpeechRecognition, should_send_to_chatgpt, chatgpt_filter_decision
from .chat_assistant import ChatAssistant


class VoskSpeechRecognition:
    """Lokale Spracherkennung mit Vosk (Deutsch)."""
    
    def __init__(self, model_path: str, device: Optional[str | int] = None, debug: bool = False):
        """
        Initialisiere Vosk-Spracherkennung.
        
        Args:
            model_path: Pfad zum Vosk-Modell (z. B. "models/vosk-model-de-0.22")
            device: Audio-Eingabegerät (ID, Name oder None für Standard)
        """
        self.model_path = Path(model_path)
        self.device_spec = device
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.recognizer = None
        self.debug = debug
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
            
            start_ts = time.time()
            print(f"Lade Vosk-Modell von: {self.model_path}")
            model = Model(str(self.model_path))
            self.recognizer = model
            elapsed = time.time() - start_ts
            print(f"Vosk-Modell geladen. ({elapsed:.1f}s)")
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
            
            result_text = " ".join(text_parts).strip()
            # Stelle sicher, dass Leerzeichen zwischen Wörtern vorhanden sind
            # Normalisiere mehrfache Leerzeichen zu einem
            result_text = re.sub(r'\s+', ' ', result_text)
            return result_text
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
            
            result_text = " ".join(text_parts).strip()
            # Stelle sicher, dass Leerzeichen zwischen Wörtern vorhanden sind
            # Normalisiere mehrfache Leerzeichen zu einem
            result_text = re.sub(r'\s+', ' ', result_text)
            return result_text
        except Exception as e:
            print(f"Fehler bei Vosk-Stream-Transkription: {e}")
            return ""


class LiveVoskRecognition:
    """Live Spracherkennung mit Vosk (lokal, offline)."""
    
    def __init__(self, model_path: str, device: Optional[str | int] = None,
                 chunk_duration: float = 3.0, enable_audio_processing: bool = True,
                 enable_semantic: bool = True, language: str = "de",
                 wake_phrases: tuple[str, ...] | None = None,
                 stop_phrases: tuple[str, ...] | None = None,
                 min_chat_words: int = 2,
                 trivial_words: list[str] | None = None,
                 chat_filter_debug: bool = False,
                 chat_ignore_after_tts_sec: float = 2.0,
                 auto_pause_after_sec: float = 10.0,
                 debug_logs: bool = False,
                 audio_output_device: str | int | None = None,
                 chat_assistant: Optional[ChatAssistant] = None):
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
        self.debug_logs = debug_logs
        self.audio_output_device = audio_output_device
        self.vosk = VoskSpeechRecognition(model_path, device, debug=debug_logs)
        self.samplerate = 16000
        self.chunk_duration = chunk_duration  # Längere Chunks = besserer Kontext
        self.enable_audio_processing = enable_audio_processing
        self.is_running = False
        self.current_text = ""
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self.enable_semantic = enable_semantic
        self.semantic_processor = SemanticSpeechRecognition(language=language) if enable_semantic else None
        self.chat_assistant = chat_assistant
        self._last_chat_text: Optional[str] = None
        self.listening_active = False
        self._paused_notice = False
        self._status_text: Optional[str] = None
        self.wake_phrases = wake_phrases or ("ok google", "okay google")
        self.stop_phrases = stop_phrases or ("stopp", "stop")
        self.min_chat_words = min_chat_words
        self.trivial_words = set(trivial_words or [])
        self.chat_filter_debug = chat_filter_debug
        self.chat_ignore_after_tts_sec = chat_ignore_after_tts_sec
        self.auto_pause_after_sec = auto_pause_after_sec
        self._ignore_until = 0.0
        self._last_tts_text = ""
        self._pending_prefix = ""
        self._last_activity_ts = time.time()
    
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

    def _set_listening(self, active: bool, reason: str) -> None:
        status_text = "BEREIT" if active else "PAUSE"
        prev_active = self.listening_active
        if self.listening_active == active and self._status_text == status_text:
            return
        self.listening_active = active
        self._paused_notice = not active
        self._status_text = status_text
        self._update_display(status_text)
        print(f"STATUS: {status_text} ({reason})")
        if active:
            self._last_activity_ts = time.time()
            play_beep_sequence(device=self.audio_output_device, announce=False)
        elif prev_active and not active:
            play_hangup_tone(device=self.audio_output_device, announce=False)

    def _debug(self, msg: str) -> None:
        if self.debug_logs:
            ts = time.strftime("%H:%M:%S")
            print(f"[DEBUG {ts}] {msg}")

    def _on_tts_done(self, text: str) -> None:
        self._last_tts_text = (text or "").strip().lower()
        self._ignore_until = time.time() + self.chat_ignore_after_tts_sec
        self._set_listening(False, "TTS fertig")

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9äöüß ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _check_commands(self, text: str) -> str | None:
        norm = self._normalize_command_text(text)
        padded = f" {norm} "
        if any(f" {phrase} " in padded for phrase in self.stop_phrases):
            return "stop"
        if any(f" {phrase} " in padded for phrase in self.wake_phrases):
            return "wake"
        return None
    
    def _process_chunk(self) -> None:
        """Nimmt einen Chunk auf, transkribiert ihn und aktualisiert das Display."""
        try:
            # Während Ausgabe nichts aufnehmen
            wait_for_playback_end()
            # Audio aufnehmen
            self._debug("record_chunk: start")
            audio_data = self._record_chunk()
            self._debug(f"record_chunk: done len={len(audio_data)}")
            
            if not self.is_running:
                return
            
            # Voice Activity Detection - überspringe leise Chunks
            if not self._detect_speech(audio_data, threshold=0.005):
                # Keine Sprache erkannt, überspringe
                self._debug("vad: no speech")
                return
            
            # Transkribieren (direkt mit numpy-Array)
            self._debug("transcribe: start")
            text = self.vosk.transcribe_audio_stream(audio_data)
            self._debug(f"transcribe: done text='{text}'")
            
            if text:
                self._last_activity_ts = time.time()
                # Stelle sicher, dass Text Leerzeichen hat
                text = re.sub(r'\s+', ' ', text).strip()

                now = time.time()
                if now < self._ignore_until:
                    if self.chat_filter_debug:
                        print("ChatGPT-Filter: blockiert (nach TTS)")
                    return
                norm_text = self._normalize_command_text(text)
                if self._last_tts_text and norm_text:
                    if norm_text in self._last_tts_text or self._last_tts_text in norm_text:
                        if self.chat_filter_debug:
                            print("ChatGPT-Filter: blockiert (Echo von TTS)")
                        return

                cmd = self._check_commands(text)
                if cmd == "stop":
                    self._set_listening(False, "STOPP erkannt")
                    self._debug("command: stop")
                    return
                if cmd == "wake":
                    self._set_listening(True, "OK GOOGLE erkannt")
                    self._debug("command: wake")
                    return

                if not self.listening_active:
                    self._set_listening(False, "Warte auf Wake")
                    self._debug("listening inactive: skip")
                    return

                if self._pending_prefix:
                    text = f"{self._pending_prefix} {text}".strip()
                    self._pending_prefix = ""
                
                # Prüfe, ob Text bereits vorhanden ist (verhindert Doppel-Ausgabe)
                if self.current_text and text.lower() in self.current_text.lower():
                    # Überspringe, wenn bereits vorhanden
                    return
                
                # Semantische Satzerkennung mit kontext-basierter Korrektur
                if self.semantic_processor:
                    # Text temporär hinzufügen für Verarbeitung
                    temp_text = self.current_text + " " + text if self.current_text else text
                    result = self.semantic_processor.process_text(temp_text)
                    
                    # Verwende korrigierten Text
                    corrected_text = result.get('corrected_text', temp_text)
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

                    # Neue vollständige Sätze an ChatGPT senden
                    if self.chat_assistant:
                        for sentence in result.get("new_sentences", []):
                            if sentence and sentence.text:
                                allowed, reason = chatgpt_filter_decision(
                                    sentence.text, self.min_chat_words, self.trivial_words
                                )
                                if allowed:
                                    self.chat_assistant.handle_text(sentence.text)
                                else:
                                    self._pending_prefix = sentence.text
                                    if self.chat_filter_debug:
                                        print(f"ChatGPT-Filter: '{sentence.text}' → blockiert ({reason})")
                else:
                    # Standard: Einfache Text-Anzeige (ohne Korrektur)
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    self._update_display(self.current_text)

                    # Fallback: gesamten Text senden (ohne Semantik)
                    if self.chat_assistant:
                        if self._last_chat_text != text:
                            allowed, reason = chatgpt_filter_decision(
                                text, self.min_chat_words, self.trivial_words
                            )
                            if allowed:
                                self._last_chat_text = text
                                self.chat_assistant.handle_text(text)
                            else:
                                self._pending_prefix = text
                                if self.chat_filter_debug:
                                    print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")
                
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
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self._last_activity_ts = time.time()

        # Geräteauswahl anzeigen + Fallback
        self.vosk.device_id = select_input_device(self.vosk.device_spec, announce=True)
        
        if self.oled:
            self.oled.show_listening()

        self._set_listening(False, "Start")
        
        print("Live-Spracherkennung (Vosk, lokal) gestartet. Strg+C zum Beenden.")
        print("Sprich jetzt...")
        
        try:
            # Kontinuierliche Verarbeitung
            while self.is_running:
                if self.listening_active and self.auto_pause_after_sec > 0:
                    if (time.time() - self._last_activity_ts) >= self.auto_pause_after_sec:
                        self._set_listening(False, "Inaktivität")
                self._process_chunk()
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stoppe die Live-Spracherkennung."""
        self.is_running = False
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_live_vosk_recognition(model_path: Optional[str] = None, enable_chatgpt: bool = False):
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
    
    # ChatGPT-Assistent (optional)
    chat_assistant = None
    if enable_chatgpt:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        chat_assistant = ChatAssistant(
            client=client,
            model_chat=settings.model_chat,
            model_tts=settings.model_tts,
            tts_voice=settings.tts_voice,
            audio_output_device=settings.audio_output_device,
        )

    # Live-Spracherkennung starten
    recognizer = LiveVoskRecognition(
        model_path=model_path,
        device=settings.audio_input_device,
        wake_phrases=tuple(settings.wake_phrases),
        stop_phrases=tuple(settings.stop_phrases),
        min_chat_words=settings.min_chat_words,
        trivial_words=settings.trivial_words,
        chat_filter_debug=settings.chat_filter_debug,
        chat_ignore_after_tts_sec=settings.chat_ignore_after_tts_sec,
        auto_pause_after_sec=settings.auto_pause_after_sec,
        debug_logs=settings.debug_logs,
        audio_output_device=settings.audio_output_device,
        chat_assistant=chat_assistant,
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(recognizer._on_tts_done)
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_live_vosk_recognition(model_path)
