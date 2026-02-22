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
from .chat_assistant import ChatAssistant
from .sentence_detection import (
    SemanticSpeechRecognition,
    should_send_to_chatgpt,
    chatgpt_filter_decision,
    chatgpt_filter_message,
)
from .oled_display import OledDisplay


class SmartMultiLanguageVoskRecognition:
    """
    Intelligente mehrsprachige Spracherkennung:
    - Deutsch als Hauptsprache für Kontext und Semantik
    - Englisch nur für bestimmte ergänzende Wörter (Internet, Computer, Raspberry Pi, cool, etc.)
    """
    
    def __init__(self, model_path_de: str, model_path_en: Optional[str] = None,
                 device: Optional[str | int] = None,
                 chunk_duration: float = 3.0, enable_audio_processing: bool = True,
                 enable_semantic: bool = True,
                 vad_rms_threshold: float = 0.01,
                 vad_noise_multiplier: float = 3.0,
                 vad_noise_alpha: float = 0.1,
                 vad_hangover_factor: float = 0.6,
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
                 confirm_timeout_sec: float = 6.0):
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
        self.device_spec = device
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.chunk_duration = chunk_duration
        self.enable_audio_processing = enable_audio_processing
        self.enable_semantic = enable_semantic
        self.vad_rms_threshold = vad_rms_threshold
        self.vad_noise_multiplier = vad_noise_multiplier
        self.vad_noise_alpha = vad_noise_alpha
        self.vad_hangover_factor = max(0.1, min(vad_hangover_factor, 1.0))
        self.vad_preroll_sec = max(0.0, vad_preroll_sec)
        self._preroll_samples = int(self.samplerate * self.vad_preroll_sec)
        self._preroll_tail = np.zeros(0, dtype=np.int16)
        self._noise_floor = 0.0
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
        self.context_mode = False
        self.prompt_new = prompt_new
        self.prompt_context = prompt_context
        
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
        
        result_text = " ".join(text_parts).strip()
        # Stelle sicher, dass Leerzeichen zwischen Wörtern vorhanden sind
        # Normalisiere mehrfache Leerzeichen zu einem
        result_text = re.sub(r'\s+', ' ', result_text)
        return result_text
    
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
        
        result_text = " ".join(text_parts).strip()
        # Stelle sicher, dass Leerzeichen zwischen Wörtern vorhanden sind
        # Normalisiere mehrfache Leerzeichen zu einem
        result_text = re.sub(r'\s+', ' ', result_text)
        return result_text
    
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
        base_threshold = self.vad_rms_threshold if self.vad_rms_threshold > 0 else threshold
        if self.vad_noise_alpha > 0 and rms < base_threshold:
            if self._noise_floor <= 0:
                self._noise_floor = rms
            else:
                self._noise_floor = (1.0 - self.vad_noise_alpha) * self._noise_floor + self.vad_noise_alpha * rms
        effective_threshold = max(base_threshold, self._noise_floor * self.vad_noise_multiplier)
        if self._speech_active:
            effective_threshold *= self.vad_hangover_factor
        if self.debug_logs:
            self._debug(
                f"vad: rms={rms:.6f} base={base_threshold:.6f} "
                f"noise={self._noise_floor:.6f} mult={self.vad_noise_multiplier:.2f} "
                f"hangover={self.vad_hangover_factor:.2f} th={effective_threshold:.6f}"
            )
        return rms > effective_threshold
    
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
        
        recording = record_audio_chunk(
            frames_to_record,
            samplerate=self.samplerate,
            device_id=self.device_id,
            channels=1,
            dtype="int16",
        )
        
        if self.enable_audio_processing:
            recording = self._normalize_audio(recording)
        
        return recording.flatten()
    
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
        if self.semantic_processor:
            self.semantic_processor.reset()

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
        if self.semantic_processor:
            self.semantic_processor.reset()
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
        if self.semantic_processor:
            self.semantic_processor.reset()
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
        chunk_audio = None
        preroll_tail = self._preroll_tail
        try:
            # Während Ausgabe nichts aufnehmen
            wait_for_playback_end()
            if self._awaiting_confirm and self._confirm_deadline and time.time() > self._confirm_deadline:
                self._cancel_confirmation()
                return
            # Audio aufnehmen
            self._debug("record_chunk: start")
            audio_data = self._record_chunk()
            chunk_audio = audio_data
            self._debug(f"record_chunk: done len={len(audio_data)}")
            
            if not self.is_running:
                return
            
            # Voice Activity Detection
            speech_was_active = self._speech_active
            if not self._detect_speech(audio_data, threshold=0.005):
                if self.pause_duration:
                    self._silence_sec += self.chunk_duration
                    if self._speech_active and self._silence_sec >= self.pause_duration:
                        self._finalize_current_text()
                self._debug("vad: no speech")
                return
            else:
                if self.pause_duration:
                    self._speech_active = True
                    self._silence_sec = 0.0
                if not speech_was_active and self._preroll_samples > 0 and preroll_tail.size:
                    audio_data = np.concatenate([preroll_tail, audio_data])
                    if self.debug_logs:
                        self._debug(f"vad: preroll {len(preroll_tail)} samples prepended")
            
            # Transkribiere mit deutschem Modell (Hauptsprache)
            text_de = self._transcribe_audio_de(audio_data)
            if text_de:
                self._debug(f"transcribe(de): '{text_de}'")
            
            # Transkribiere mit englischem Modell (nur wenn verfügbar)
            text_en = ""
            if self.model_en:
                text_en = self._transcribe_audio_en(audio_data)
                if text_en:
                    self._debug(f"transcribe(en): '{text_en}'")
            
            # Kombiniere Texte intelligent
            text = self._merge_texts(text_de, text_en)
            
            if text:
                self._last_activity_ts = time.time()
                if self._pending_prefix:
                    text = f"{self._pending_prefix} {text}".strip()
                    self._pending_prefix = ""
                    self._debug(f"pending_prefix merged: '{text}'")
                if time.time() < self._ignore_until:
                    if self.chat_filter_debug:
                        print("ChatGPT-Filter: blockiert (nach TTS)")
                    self._debug("ignore: after tts")
                    return
                if not self._should_process_text(text):
                    self._debug("command/listen filter: skip")
                    return
                # Stelle sicher, dass Text Leerzeichen hat
                text = re.sub(r'\s+', ' ', text).strip()
                
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

                    # Neue vollständige Sätze an ChatGPT senden
                if self.chat_assistant and not self.pause_duration:
                        sent_any = False
                        for sentence in result.get("new_sentences", []):
                            if sentence and sentence.text:
                                allowed, reason = chatgpt_filter_decision(
                                    sentence.text, self.min_chat_words, self.trivial_words
                                )
                                if allowed:
                                    if self.debug_logs:
                                        print(f"[DEBUG] prompt=NEW" if not self.context_mode else "[DEBUG] prompt=KONTEXT")
                                    if self.confirm_before_chat and self._request_confirmation(
                                        sentence.text, self._current_prompt()
                                    ):
                                        pass
                                    else:
                                        self.chat_assistant.handle_text(
                                            sentence.text,
                                            system_prompt_override=self._current_prompt(),
                                        )
                                        sent_any = True
                                else:
                                    self._announce_chat_filter_block(reason)
                                    if self.chat_filter_debug:
                                        print(f"ChatGPT-Filter: '{sentence.text}' → blockiert ({reason})")
                        if sent_any:
                            self.current_text = ""
                            self._pending_prefix = ""
                            if self.semantic_processor:
                                self.semantic_processor.reset()
                else:
                    # Standard: Einfache Text-Anzeige
                    self._update_display(self.current_text)

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
        finally:
            if chunk_audio is not None and self._preroll_samples > 0:
                if chunk_audio.size > self._preroll_samples:
                    self._preroll_tail = chunk_audio[-self._preroll_samples:].copy()
                else:
                    self._preroll_tail = chunk_audio.copy()
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte die Live-Spracherkennung."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        self.last_processed_length = 0
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self._last_activity_ts = time.time()
        self.context_mode = False

        # Geräteauswahl anzeigen + Fallback
        self.device_id = select_input_device(self.device_spec, announce=True)
        
        if self.oled:
            self.oled.show_listening()

        self._set_listening(False, "Start")
        
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
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback


def run_smart_multilang_recognition(
    model_path_de: str,
    model_path_en: Optional[str] = None,
    device: Optional[str | int] = None,
    enable_chatgpt: bool = False,
):
    """Hauptfunktion für intelligente mehrsprachige Spracherkennung."""
    import time
    from .config import load_settings
    
    settings = load_settings()

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
        )
        try:
            chat_assistant = ChatAssistant(**kwargs)
        except TypeError:
            kwargs.pop("announce_chat_request", None)
            kwargs.pop("echo_input_local_tts", None)
            try:
                chat_assistant = ChatAssistant(**kwargs)
            except TypeError:
                kwargs.pop("echo_input_before_chat", None)
                chat_assistant = ChatAssistant(**kwargs)

    # Initialisiere Erkennung
    recognizer = SmartMultiLanguageVoskRecognition(
        model_path_de=model_path_de,
        model_path_en=model_path_en,
        device=device,
        chunk_duration=settings.vosk_chunk_duration,
        vad_rms_threshold=settings.vad_rms_threshold,
        vad_noise_multiplier=settings.vad_noise_multiplier,
        vad_noise_alpha=settings.vad_noise_alpha,
        vad_hangover_factor=settings.vad_hangover_factor,
        vad_preroll_sec=settings.vad_preroll_sec,
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
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(recognizer._on_tts_done)
    
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
