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

from .audio_io import (
    _resolve_device_id,
    select_input_device,
    wait_for_playback_end,
    play_beep_sequence,
    play_hangup_tone,
    stop_playback,
    record_audio_chunk,
)
from .oled_display import OledDisplay
from .chat_assistant import ChatAssistant
from .sentence_detection import should_send_to_chatgpt, chatgpt_filter_decision, chatgpt_filter_message


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
                 pause_duration: float | None = None,
                 debug_logs: bool = False,
                 audio_output_device: str | int | None = None,
                 prompt_new: str | None = None,
                 prompt_context: str | None = None,
                 chat_assistant: Optional[ChatAssistant] = None,
                 confirm_before_chat: bool = False,
                 confirm_phrases: tuple[str, ...] | None = None,
                 reject_phrases: tuple[str, ...] | None = None,
                 confirm_timeout_sec: float = 6.0,
                 ready_hold_sec: float = 10.0):
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
        self.pause_duration = pause_duration if pause_duration is not None else 0.0
        if self.pause_duration <= 0:
            self.pause_duration = None
        self._silence_sec = 0.0
        self._speech_active = False
        self.debug_logs = debug_logs
        self.audio_output_device = audio_output_device
        self.confirm_before_chat = confirm_before_chat
        self.confirm_phrases = confirm_phrases or ("ok", "okay", "ja", "yes")
        self.reject_phrases = reject_phrases or ("nein", "no", "falsch", "abbruch")
        self.confirm_timeout_sec = confirm_timeout_sec
        self._awaiting_confirm = False
        self._pending_confirm_text: Optional[str] = None
        self._pending_confirm_prompt: Optional[str] = None
        self._confirm_deadline: Optional[float] = None
        self._ignore_until = 0.0
        self._last_tts_text = ""
        self._pending_prefix = ""
        self._last_activity_ts = time.time()
        self._force_ready_until = 0.0
        self.ready_hold_sec = ready_hold_sec
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
        
        recording = record_audio_chunk(
            frames_to_record,
            samplerate=self.samplerate,
            device_id=self.vosk.device_id,
            channels=channels,
            dtype=dtype,
        )
        
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

    def _set_listening(
        self,
        active: bool,
        reason: str,
        context_mode: bool | None = None,
        announce: bool = True,
    ) -> None:
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
            if announce:
                play_beep_sequence(device=self.audio_output_device, announce=False)
        elif prev_active and not active:
            self.context_mode = False
            self._force_ready_until = 0.0
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
        self._last_activity_ts = time.time()
        self._force_ready_until = time.time() + self.ready_hold_sec
        self._set_listening(True, "Antwort fertig", context_mode=False, announce=False)

    def _announce_chat_filter_block(self, reason: str | None) -> None:
        if not self.chat_assistant:
            return
        message = chatgpt_filter_message(reason, self.min_chat_words)
        if not message:
            return
        try:
            # Avoid feedback loop: mark as "just spoken" and ignore briefly.
            self._last_tts_text = (message or "").strip().lower()
            self._ignore_until = time.time() + self.chat_ignore_after_tts_sec
            self.chat_assistant.speak(message, notify=False)
        except Exception as e:
            if self.chat_filter_debug:
                print(f"ChatGPT-Filter: Audio-Fehler ({e})")

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        text = (text or "").lower()
        text = re.sub(r"[^a-z0-9äöüß ]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _history_index(self, text: str) -> int | None:
        norm = self._normalize_command_text(text)
        match = re.search(r"\bhistorie\s+(\d+)\b", norm)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
        return _history_word_to_index(norm)

def _history_word_to_index(norm_text: str) -> int | None:
    match = re.search(r"\bhistorie\s+([a-zäöüß]+)\b", norm_text)
    if not match:
        return None
    word = match.group(1)
    mapping = {
        "eins": 1,
        "ein": 1,
        "zwei": 2,
        "drei": 3,
        "vier": 4,
        "fuenf": 5,
        "fünf": 5,
        "sechs": 6,
        "sieben": 7,
        "acht": 8,
        "neun": 9,
        "zehn": 10,
    }
    return mapping.get(word)

    def _handle_history_command(self, text: str) -> bool:
        if not self.chat_assistant:
            return False
        index = self._history_index(text)
        if index is None:
            return False
        if not self.chat_assistant.play_history(index):
            if self.debug_logs:
                print(f"[DEBUG] historie: index {index} not available")
        return True

    def _check_confirmation(self, text: str) -> str | None:
        norm = self._normalize_command_text(text)
        padded = f" {norm} "
        if any(f" {phrase} " in padded for phrase in self.confirm_phrases):
            return "confirm"
        if any(f" {phrase} " in padded for phrase in self.reject_phrases):
            return "reject"
        return None

    def _request_confirmation(self, text: str, system_prompt_override: Optional[str]) -> bool:
        if self._awaiting_confirm or not self.chat_assistant:
            return False
        message = f"Ich habe verstanden: {text}. Sag OK oder Nein."
        self._last_tts_text = (message or "").strip().lower()
        self._ignore_until = time.time() + self.chat_ignore_after_tts_sec
        try:
            if hasattr(self.chat_assistant, "speak_blocking"):
                ok = self.chat_assistant.speak_blocking(message, notify=False)
            else:
                self.chat_assistant.speak(message, notify=False)
                ok = True
        except Exception as e:
            if self.debug_logs:
                print(f"[DEBUG] confirm: tts failed ({e})")
            return False
        if not ok:
            return False
        if self.debug_logs:
            print(f"[DEBUG] confirm: ask '{text}'")
        self._awaiting_confirm = True
        self._pending_confirm_text = text
        self._pending_confirm_prompt = system_prompt_override
        self._confirm_deadline = time.time() + self.confirm_timeout_sec
        return True

    def _cancel_confirmation(self) -> None:
        if self.chat_assistant:
            message = "Okay, verworfen."
            self._last_tts_text = (message or "").strip().lower()
            self._ignore_until = time.time() + self.chat_ignore_after_tts_sec
            self.chat_assistant.speak(message, notify=False)
        self._awaiting_confirm = False
        self._pending_confirm_text = None
        self._pending_confirm_prompt = None
        self._confirm_deadline = None
        self.current_text = ""
        self._pending_prefix = ""
        self._last_activity_ts = time.time()
        self._force_ready_until = time.time() + self.ready_hold_sec
        self._set_listening(True, "Frage verworfen", context_mode=False, announce=False)

    def _handle_confirmation(self, text: str) -> bool:
        if not self._awaiting_confirm:
            return False
        decision = self._check_confirmation(text)
        if not decision:
            return True
        if decision == "confirm" and self.chat_assistant and self._pending_confirm_text:
            if self.debug_logs:
                print(f"[DEBUG] confirm: send '{self._pending_confirm_text}'")
            self.chat_assistant.handle_text(
                self._pending_confirm_text,
                system_prompt_override=self._pending_confirm_prompt,
            )
        else:
            self._cancel_confirmation()
            return True
        self._awaiting_confirm = False
        self._pending_confirm_text = None
        self._pending_confirm_prompt = None
        self._confirm_deadline = None
        self.current_text = ""
        self._pending_prefix = ""
        return True

    def _finalize_current_text(self) -> None:
        if not self.pause_duration:
            return
        if self._awaiting_confirm:
            return
        if not self.listening_active:
            self._speech_active = False
            self._silence_sec = 0.0
            return
        text = (self.current_text or "").strip()
        if self._pending_prefix:
            if text:
                text = f"{self._pending_prefix} {text}".strip()
            else:
                text = self._pending_prefix
        if not text:
            self._speech_active = False
            self._silence_sec = 0.0
            return
        if self.chat_assistant and self._last_chat_text != text:
            allowed, reason = chatgpt_filter_decision(text, self.min_chat_words, self.trivial_words)
            if allowed:
                self._last_chat_text = text
                if self.debug_logs:
                    print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                if self.confirm_before_chat:
                    self._request_confirmation(text, self._current_prompt())
                else:
                    self.chat_assistant.handle_text(
                        text,
                        system_prompt_override=self._current_prompt(),
                    )
            else:
                self._pending_prefix = text
                self._announce_chat_filter_block(reason)
        self.current_text = ""
        self._pending_prefix = ""
        self._speech_active = False
        self._silence_sec = 0.0

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
        if self._handle_history_command(text):
            return False
        cmd = self._check_commands(text)
        if cmd == "stop":
            stop_playback()
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
        if self._awaiting_confirm:
            return not self._handle_confirmation(text)
        return True
    
    def _process_chunk(self) -> None:
        """Verarbeite einen Audio-Chunk."""
        try:
            # Während Ausgabe nichts aufnehmen
            wait_for_playback_end()
            if self._awaiting_confirm and self._confirm_deadline and time.time() > self._confirm_deadline:
                self._cancel_confirmation()
                return
            self._debug("record_chunk: start")
            audio_data = self._record_chunk()
            self._debug(f"record_chunk: done len={len(audio_data)}")
            
            if not self.is_running:
                return
            
            wav_bytes = self._audio_to_wav_bytes(audio_data)
            
            # Transkribiere je nach Modus
            if self.mode == "best":
                lang, text = self.vosk.transcribe_audio_best(wav_bytes)
                if not text:
                    if self.pause_duration:
                        self._silence_sec += self.chunk_duration
                        if self._speech_active and self._silence_sec >= self.pause_duration:
                            self._finalize_current_text()
                    return
                if self.pause_duration:
                    self._speech_active = True
                    self._silence_sec = 0.0
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
                    if self.chat_assistant and self._last_chat_text != text and not self.pause_duration:
                        allowed, reason = chatgpt_filter_decision(
                            text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            self._last_chat_text = text
                            if self.debug_logs:
                                print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                            if self.confirm_before_chat and self._request_confirmation(
                                text, self._current_prompt()
                            ):
                                pass
                            else:
                                self.chat_assistant.handle_text(
                                    text,
                                    system_prompt_override=self._current_prompt(),
                                )
                                self.current_text = ""
                                self._pending_prefix = ""
                        else:
                            self._announce_chat_filter_block(reason)
                            if self.chat_filter_debug:
                                print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")
                            else:
                                self._pending_prefix = text
            
            elif self.mode == "combined":
                text = self.vosk.transcribe_audio_combined(wav_bytes)
                if not text:
                    if self.pause_duration:
                        self._silence_sec += self.chunk_duration
                        if self._speech_active and self._silence_sec >= self.pause_duration:
                            self._finalize_current_text()
                    return
                if self.pause_duration:
                    self._speech_active = True
                    self._silence_sec = 0.0
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
                    if self.chat_assistant and self._last_chat_text != text and not self.pause_duration:
                        allowed, reason = chatgpt_filter_decision(
                            text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            self._last_chat_text = text
                            if self.debug_logs:
                                print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                            if self.confirm_before_chat and self._request_confirmation(
                                text, self._current_prompt()
                            ):
                                pass
                            else:
                                self.chat_assistant.handle_text(
                                    text,
                                    system_prompt_override=self._current_prompt(),
                                )
                                self.current_text = ""
                                self._pending_prefix = ""
                        else:
                            self._announce_chat_filter_block(reason)
                            if self.chat_filter_debug:
                                print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")
                            else:
                                self._pending_prefix = text
            
            elif self.mode == "all":
                results = self.vosk.transcribe_audio(wav_bytes)
                if not results:
                    if self.pause_duration:
                        self._silence_sec += self.chunk_duration
                        if self._speech_active and self._silence_sec >= self.pause_duration:
                            self._finalize_current_text()
                    return
                if self.pause_duration:
                    self._speech_active = True
                    self._silence_sec = 0.0
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
                    if self.chat_assistant and self._last_chat_text != text and not self.pause_duration:
                        allowed, reason = chatgpt_filter_decision(
                            text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            self._last_chat_text = text
                            if self.debug_logs:
                                print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                            if self.confirm_before_chat and self._request_confirmation(
                                text, self._current_prompt()
                            ):
                                pass
                            else:
                                self.chat_assistant.handle_text(
                                    text,
                                    system_prompt_override=self._current_prompt(),
                                )
                                self.current_text = ""
                                self._pending_prefix = ""
                        else:
                            self._announce_chat_filter_block(reason)
                            if self.chat_filter_debug:
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
                    if self._force_ready_until and time.time() < self._force_ready_until:
                        pass
                    elif (time.time() - self._last_activity_ts) >= self.auto_pause_after_sec:
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
        kwargs = dict(
            client=client,
            model_chat=settings.model_chat,
            model_tts=settings.model_tts,
            tts_voice=settings.tts_voice,
            audio_output_device=settings.audio_output_device,
            echo_input_before_chat=settings.echo_input_before_chat,
            echo_input_local_tts=settings.echo_input_local_tts,
            announce_chat_request=settings.announce_chat_request,
            history_path=settings.history_path,
            history_dir=settings.history_dir,
            history_max=settings.history_max,
        )
        try:
            chat_assistant = ChatAssistant(**kwargs)
        except TypeError:
            kwargs.pop("announce_chat_request", None)
            kwargs.pop("echo_input_local_tts", None)
            kwargs.pop("history_path", None)
            kwargs.pop("history_dir", None)
            kwargs.pop("history_max", None)
            try:
                chat_assistant = ChatAssistant(**kwargs)
            except TypeError:
                kwargs.pop("echo_input_before_chat", None)
                chat_assistant = ChatAssistant(**kwargs)

    # Live-Spracherkennung starten
    recognizer = LiveMultiLanguageVoskRecognition(
        model_paths=model_paths,
        device=settings.audio_input_device,
        mode=mode,
        chunk_duration=settings.vosk_chunk_duration,
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
        confirm_before_chat=settings.confirm_before_chat,
        confirm_phrases=tuple(settings.confirm_phrases),
        reject_phrases=tuple(settings.reject_phrases),
        pause_duration=settings.vosk_pause_duration,
        confirm_timeout_sec=settings.confirm_timeout_sec,
        ready_hold_sec=settings.ready_hold_sec,
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
