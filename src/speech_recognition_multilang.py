from __future__ import annotations
import io
import wave
import json
import re
import time
import numpy as np
import sounddevice as sd
from typing import Callable, Optional, Dict, List, Tuple
from pathlib import Path

from .audio_io import _resolve_device_id, select_input_device, wait_for_playback_end, play_beep_sequence, play_hangup_tone
from .oled_display import OledDisplay
from .chat_assistant import ChatAssistant
from .sentence_detection import should_send_to_chatgpt, chatgpt_filter_decision


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
        self.device_spec = device
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
                 chunk_duration: float = 3.0, mode: str = "best",
                 wake_phrases: tuple[str, ...] | None = None,
                 context_phrases: tuple[str, ...] | None = None,
                 stop_phrases: tuple[str, ...] | None = None,
                 min_chat_words: int = 2,
                 trivial_words: list[str] | None = None,
                 chat_filter_debug: bool = False,
                 chat_ignore_after_tts_sec: float = 2.0,
                 auto_pause_after_sec: float = 10.0,
                 debug_logs: bool = False,
                 audio_output_device: str | int | None = None,
                 prompt_new: str | None = None,
                 prompt_context: str | None = None,
                 chat_assistant: Optional[ChatAssistant] = None):
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
        self.chat_assistant = chat_assistant
        self._last_chat_text: Optional[str] = None
        self.listening_active = False
        self._paused_notice = False
        self._status_text: Optional[str] = None
        self.wake_phrases = wake_phrases or ("ok google", "okay google")
        self.context_phrases = context_phrases or ("ok google weiter", "okay google weiter")
        self.stop_phrases = stop_phrases or ("stopp", "stop")
        self.min_chat_words = min_chat_words
        self.trivial_words = set(trivial_words or [])
        self.chat_filter_debug = chat_filter_debug
        self.chat_ignore_after_tts_sec = chat_ignore_after_tts_sec
        self.auto_pause_after_sec = auto_pause_after_sec
        self.debug_logs = debug_logs
        self.audio_output_device = audio_output_device
        self._ignore_until = 0.0
        self._last_tts_text = ""
        self._pending_prefix = ""
        self._last_activity_ts = time.time()
        self.context_mode = False
        self.prompt_new = prompt_new
        self.prompt_context = prompt_context
    
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

    def _set_listening(self, active: bool, reason: str, context_mode: bool | None = None) -> None:
        if context_mode is not None:
            self.context_mode = context_mode
        status_text = "BEREIT MIT Kontext" if active and self.context_mode else "BEREIT" if active else "PAUSE"
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
            self.context_mode = False
            play_hangup_tone(device=self.audio_output_device, announce=False)

    def _debug(self, msg: str) -> None:
        if self.debug_logs:
            ts = time.strftime("%H:%M:%S")
            print(f"[DEBUG {ts}] {msg}")

    def _current_prompt(self) -> Optional[str]:
        return self.prompt_context if self.context_mode else self.prompt_new

    def _on_tts_done(self, text: str) -> None:
        self._last_tts_text = (text or "").strip().lower()
        self._ignore_until = time.time() + self.chat_ignore_after_tts_sec
        self._set_listening(False, "TTS fertig", context_mode=False)

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9äöüß ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _check_commands(self, text: str) -> str | None:
        norm = self._normalize_command_text(text)
        padded = f" {norm} "
        if self.debug_logs and norm:
            print(f"[DEBUG] cmd: norm='{norm}'")
            print(f"[DEBUG] cmd: wake={self.wake_phrases} context={self.context_phrases} stop={self.stop_phrases}")
        if any(f" {phrase} " in padded for phrase in self.stop_phrases):
            return "stop"
        if any(f" {phrase} " in padded for phrase in self.context_phrases):
            return "wake_context"
        if any(f" {phrase} " in padded for phrase in self.wake_phrases):
            return "wake"
        if self.debug_logs and norm:
            print("[DEBUG] cmd: no match")
        return None

    def _should_process_text(self, text: str) -> bool:
        cmd = self._check_commands(text)
        if cmd == "stop":
            self._set_listening(False, "STOPP erkannt", context_mode=False)
            return False
        if cmd == "wake":
            self._set_listening(True, "OK GOOGLE erkannt", context_mode=False)
            return False
        if cmd == "wake_context":
            self._set_listening(True, "OK GOOGLE WEITER erkannt", context_mode=True)
            return False
        if not self.listening_active:
            self._set_listening(False, "Warte auf Wake")
            return False
        return True
    
    def _process_chunk(self) -> None:
        """Verarbeite einen Audio-Chunk."""
        try:
            # Während Ausgabe nichts aufnehmen
            wait_for_playback_end()
            self._debug("record_chunk: start")
            audio_data = self._record_chunk()
            self._debug(f"record_chunk: done len={len(audio_data)}")
            
            if not self.is_running:
                return
            
            wav_bytes = self._audio_to_wav_bytes(audio_data)
            
            # Transkribiere je nach Modus
            if self.mode == "best":
                lang, text = self.vosk.transcribe_audio_best(wav_bytes)
                if text:
                    self._debug(f"transcribe(best): '{text}'")
                    self._last_activity_ts = time.time()
                    if time.time() < self._ignore_until:
                        if self.chat_filter_debug:
                            print("ChatGPT-Filter: blockiert (nach TTS)")
                        self._debug("ignore: after tts")
                        return
                    if not self._should_process_text(text):
                        self._debug("command/listen filter: skip")
                        return
                    if self._pending_prefix:
                        text = f"{self._pending_prefix} {text}".strip()
                        self._pending_prefix = ""
                        self._debug(f"pending_prefix merged: '{text}'")
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    print(f"[{lang.upper()}] {text}")
                    if self.chat_assistant and self._last_chat_text != text:
                        allowed, reason = chatgpt_filter_decision(
                            text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            self._last_chat_text = text
                            if self.debug_logs:
                                print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                            self.chat_assistant.handle_text(
                                text,
                                system_prompt_override=self._current_prompt(),
                            )
                        elif self.chat_filter_debug:
                            print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")
                        else:
                            self._pending_prefix = text
            
            elif self.mode == "combined":
                text = self.vosk.transcribe_audio_combined(wav_bytes)
                if text:
                    self._debug(f"transcribe(combined): '{text}'")
                    self._last_activity_ts = time.time()
                    if time.time() < self._ignore_until:
                        if self.chat_filter_debug:
                            print("ChatGPT-Filter: blockiert (nach TTS)")
                        self._debug("ignore: after tts")
                        return
                    if not self._should_process_text(text):
                        self._debug("command/listen filter: skip")
                        return
                    if self._pending_prefix:
                        text = f"{self._pending_prefix} {text}".strip()
                        self._pending_prefix = ""
                        self._debug(f"pending_prefix merged: '{text}'")
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    print(f"[KOMBINIERT] {text}")
                    if self.chat_assistant and self._last_chat_text != text:
                        allowed, reason = chatgpt_filter_decision(
                            text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            self._last_chat_text = text
                            if self.debug_logs:
                                print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                            self.chat_assistant.handle_text(
                                text,
                                system_prompt_override=self._current_prompt(),
                            )
                        elif self.chat_filter_debug:
                            print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")
                        else:
                            self._pending_prefix = text
            
            elif self.mode == "all":
                results = self.vosk.transcribe_audio(wav_bytes)
                if results:
                    for lang, text in results.items():
                        print(f"[{lang.upper()}] {text}")
                    # Verwende das beste Ergebnis für Display
                    best_lang = max(results.keys(), key=lambda k: len(results[k]))
                    text = results[best_lang]
                    self._debug(f"transcribe(all best={best_lang}): '{text}'")
                    self._last_activity_ts = time.time()
                    if time.time() < self._ignore_until:
                        if self.chat_filter_debug:
                            print("ChatGPT-Filter: blockiert (nach TTS)")
                        self._debug("ignore: after tts")
                        return
                    if text and not self._should_process_text(text):
                        self._debug("command/listen filter: skip")
                        return
                    if self._pending_prefix:
                        text = f"{self._pending_prefix} {text}".strip()
                        self._pending_prefix = ""
                        self._debug(f"pending_prefix merged: '{text}'")
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    if self.chat_assistant and self._last_chat_text != text:
                        allowed, reason = chatgpt_filter_decision(
                            text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            self._last_chat_text = text
                            if self.debug_logs:
                                print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                            self.chat_assistant.handle_text(
                                text,
                                system_prompt_override=self._current_prompt(),
                            )
                        elif self.chat_filter_debug:
                            print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")
                        else:
                            self._pending_prefix = text
            
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
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self._last_activity_ts = time.time()
        self.context_mode = False

        # Geräteauswahl anzeigen + Fallback
        self.vosk.device_id = select_input_device(self.vosk.device_spec, announce=True)
        
        if self.oled:
            self.oled.show_listening()

        self._set_listening(False, "Start")
        
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
                if self.listening_active and self.auto_pause_after_sec > 0:
                    if (time.time() - self._last_activity_ts) >= self.auto_pause_after_sec:
                        self._set_listening(False, "Inaktivität")
                self._process_chunk()
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stoppe die Spracherkennung."""
        self.is_running = False
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self.context_mode = False
        self.listening_active = False
        self._paused_notice = False
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_multilang_vosk_recognition(
    model_paths: Optional[Dict[str, str]] = None,
    mode: str = "best",
    enable_chatgpt: bool = False,
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
            echo_input_before_chat=settings.echo_input_before_chat,
            echo_input_local_tts=settings.echo_input_local_tts,
        )

    # Live-Spracherkennung starten
    recognizer = LiveMultiLanguageVoskRecognition(
        model_paths=model_paths,
        device=settings.audio_input_device,
        mode=mode,
        wake_phrases=tuple(settings.wake_phrases),
        context_phrases=tuple(settings.context_phrases),
        stop_phrases=tuple(settings.stop_phrases),
        min_chat_words=settings.min_chat_words,
        trivial_words=settings.trivial_words,
        chat_filter_debug=settings.chat_filter_debug,
        chat_ignore_after_tts_sec=settings.chat_ignore_after_tts_sec,
        auto_pause_after_sec=settings.auto_pause_after_sec,
        debug_logs=settings.debug_logs,
        audio_output_device=settings.audio_output_device,
        prompt_new=settings.chat_system_prompt_new,
        prompt_context=settings.chat_system_prompt_context,
        chat_assistant=chat_assistant,
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(recognizer._on_tts_done)
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    
    mode = "best"
    if "--combined" in sys.argv:
        mode = "combined"
    elif "--all" in sys.argv:
        mode = "all"
    
    run_multilang_vosk_recognition(mode=mode)
