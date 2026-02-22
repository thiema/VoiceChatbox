from __future__ import annotations
import io
import wave
import json
import re
import time
import threading
import numpy as np
import sounddevice as sd
from typing import Callable, Optional
from pathlib import Path

from .audio_io import (
    _resolve_device_id,
    select_input_device,
    wait_for_playback_end,
    play_beep_sequence,
    play_hangup_tone,
    stop_playback,
    record_audio_chunk,
    play_status_listening,
)
from .oled_display import OledDisplay
from .sentence_detection import (
    SemanticSpeechRecognition,
    should_send_to_chatgpt,
    chatgpt_filter_decision,
    chatgpt_filter_message,
)
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
            stop_event = threading.Event()

            def _progress():
                expected_sec = 15.0
                while not stop_event.is_set():
                    elapsed = time.time() - start_ts
                    pct = min(int((elapsed / expected_sec) * 100), 99)
                    print(f"\rLade Vosk-Modell... {pct}%", end="", flush=True)
                    time.sleep(0.2)

            thread = threading.Thread(target=_progress, daemon=True)
            thread.start()
            model = Model(str(self.model_path))
            self.recognizer = model
            stop_event.set()
            thread.join(timeout=0.2)
            print("\r", end="")
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
                 vad_rms_threshold: float = 0.01,
                 vad_noise_multiplier: float = 3.0,
                 vad_noise_alpha: float = 0.1,
                 vad_hangover_factor: float = 0.6,
                 vad_preroll_sec: float = 0.2,
                 ready_hold_sec: float = 10.0,
                 vad_use_webrtcvad: bool = True,
                 vad_webrtcvad_mode: int = 2,
                 vad_webrtcvad_frame_ms: int = 30):
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
        self._ignore_until = 0.0
        self._last_tts_text = ""
        self._pending_prefix = ""
        self._last_activity_ts = time.time()
        self._force_ready_until = 0.0
        self.ready_hold_sec = ready_hold_sec
        self.context_mode = False
        self.prompt_new = prompt_new
        self.prompt_context = prompt_context
        self.confirm_before_chat = confirm_before_chat
        self.confirm_phrases = confirm_phrases or ("ok", "okay", "ja", "yes")
        self.reject_phrases = reject_phrases or ("nein", "no", "falsch", "abbruch")
        self.confirm_timeout_sec = confirm_timeout_sec
        self._awaiting_confirm = False
        self._pending_confirm_text: Optional[str] = None
        self._pending_confirm_prompt: Optional[str] = None
        self._confirm_deadline: Optional[float] = None
        self.vad_rms_threshold = vad_rms_threshold
        self.vad_noise_multiplier = vad_noise_multiplier
        self.vad_noise_alpha = vad_noise_alpha
        self.vad_hangover_factor = max(0.1, min(vad_hangover_factor, 1.0))
        self.vad_preroll_sec = max(0.0, vad_preroll_sec)
        self._preroll_samples = int(self.samplerate * self.vad_preroll_sec)
        self._preroll_tail = np.zeros(0, dtype=np.int16)
        self.vad_use_webrtcvad = vad_use_webrtcvad
        self.vad_webrtcvad_mode = max(0, min(int(vad_webrtcvad_mode), 3))
        self.vad_webrtcvad_frame_ms = 30 if int(vad_webrtcvad_frame_ms) not in (10, 20, 30) else int(vad_webrtcvad_frame_ms)
        self._webrtcvad = None
        if self.vad_use_webrtcvad:
            try:
                import webrtcvad  # type: ignore
                self._webrtcvad = webrtcvad.Vad(self.vad_webrtcvad_mode)
            except Exception as e:
                if self.debug_logs:
                    self._debug(f"webrtcvad: unavailable ({e})")
                self._webrtcvad = None
        self._noise_floor = 0.0
    
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
        """Voice Activity Detection (VAD)."""
        if self._webrtcvad is not None:
            return self._detect_speech_webrtcvad(audio)
        # Berechne RMS (Root Mean Square) für Signalpegel
        audio_float = audio.astype(np.float32) / 32768.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        base_threshold = self.vad_rms_threshold if self.vad_rms_threshold > 0 else threshold
        # Update noise floor with a slow EMA when below base threshold
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

    def _detect_speech_webrtcvad(self, audio: np.ndarray) -> bool:
        if audio.size == 0:
            return False
        if audio.dtype != np.int16:
            audio = audio.astype(np.int16)
        frame_len = int(self.samplerate * (self.vad_webrtcvad_frame_ms / 1000.0))
        if frame_len <= 0:
            return False
        total_frames = 0
        speech_frames = 0
        data = audio.tobytes()
        bytes_per_frame = frame_len * 2  # int16 mono
        for i in range(0, len(data) - bytes_per_frame + 1, bytes_per_frame):
            frame = data[i:i + bytes_per_frame]
            total_frames += 1
            try:
                if self._webrtcvad.is_speech(frame, self.samplerate):
                    speech_frames += 1
            except Exception:
                continue
        if self.debug_logs:
            self._debug(f"vad: webrtcvad frames={total_frames} speech={speech_frames}")
        return speech_frames > 0
    
    def _record_chunk(self) -> tuple[np.ndarray, np.ndarray]:
        """Nimmt einen Audio-Chunk auf und gibt (raw, processed) zurück."""
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
        
        # Konvertiere zu mono (falls stereo)
        if len(recording.shape) > 1:
            recording = recording[:, 0]
        if self.debug_logs:
            audio_float = recording.astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(audio_float ** 2)))
            peak = float(np.max(np.abs(audio_float))) if audio_float.size else 0.0
            self._debug(
                f"audio: frames={len(recording)} sr={self.samplerate} rms={rms:.6f} peak={peak:.6f}"
            )
            if peak >= 0.98:
                self._debug("audio: clipping detected (peak >= 0.98)")
        
        raw_recording = recording.copy()

        # Audio-Vorverarbeitung für bessere Erkennung
        if self.enable_audio_processing:
            # High-Pass Filter (entfernt tiefe Frequenzen/Rauschen)
            recording = self._apply_highpass_filter(recording, cutoff=80.0)
            
            # Normalisierung
            recording = self._normalize_audio(recording)
        else:
            recording = raw_recording
        
        return raw_recording, recording
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display mit Laufband-Text."""
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

    def _log_input_device(self) -> None:
        if not self.debug_logs:
            return
        try:
            info = sd.query_devices(self.vosk.device_id, "input")
            hostapi = sd.query_hostapis(info.get("hostapi", 0)).get("name", "unknown")
            self._debug(
                "input-device: "
                f"id={self.vosk.device_id} name='{info.get('name')}' "
                f"hostapi='{hostapi}' "
                f"sr={info.get('default_samplerate')} "
                f"max_in={info.get('max_input_channels')}"
            )
        except Exception as e:
            self._debug(f"input-device: error {e}")

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
        return self._history_word_to_index(norm)

    @staticmethod
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
        # Avoid feedback loop: ignore own prompt briefly.
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
                if self.confirm_before_chat and self._request_confirmation(text, self._current_prompt()):
                    pass
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
    
    def _process_chunk(self) -> None:
        """Nimmt einen Chunk auf, transkribiert ihn und aktualisiert das Display."""
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
            raw_audio, audio_data = self._record_chunk()
            chunk_audio = audio_data
            self._debug(f"record_chunk: done len={len(audio_data)}")
            
            if not self.is_running:
                return
            
            # Voice Activity Detection - überspringe leise Chunks
            speech_was_active = self._speech_active
            if not self._detect_speech(raw_audio, threshold=0.005):
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

                if self._awaiting_confirm:
                    if self._handle_confirmation(text):
                        return

                if self._handle_history_command(text):
                    return
                cmd = self._check_commands(text)
                if cmd == "stop":
                    stop_playback()
                    self._set_listening(False, "STOPP erkannt", context_mode=False)
                    self._debug("command: stop")
                    return
                if cmd == "wake":
                    self._set_listening(True, "OK GOOGLE erkannt", context_mode=False)
                    self._debug("command: wake")
                    return
                if cmd == "wake_context":
                    self._set_listening(True, "OK GOOGLE WEITER erkannt", context_mode=True)
                    self._debug("command: wake_context")
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
                                    self._pending_prefix = sentence.text
                                    self._announce_chat_filter_block(reason)
                                    if self.chat_filter_debug:
                                        print(f"ChatGPT-Filter: '{sentence.text}' → blockiert ({reason})")
                        if sent_any:
                            self.current_text = ""
                            self._pending_prefix = ""
                            if self.semantic_processor:
                                self.semantic_processor.reset()
                else:
                    # Standard: Einfache Text-Anzeige (ohne Korrektur)
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    self._update_display(self.current_text)

                    # Fallback: gesamten Text senden (ohne Semantik)
                    if self.chat_assistant and not self.pause_duration:
                        if self._last_chat_text != text:
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
                                self._pending_prefix = text
                                self._announce_chat_filter_block(reason)
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
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self._last_activity_ts = time.time()
        self.context_mode = False

        # Geräteauswahl anzeigen + Fallback
        self.vosk.device_id = select_input_device(self.vosk.device_spec, announce=True)
        self._log_input_device()
        
        if self.oled:
            self.oled.show_listening()

        self._set_listening(False, "Start")
        play_status_listening(device=self.audio_output_device)
        # Signal: Vosk-Modell geladen und bereit für Spracheingabe
        try:
            play_beep_sequence(device=self.audio_output_device, announce=False)
        except Exception as e:
            print(f"Beep-Fehler: {e}")
        
        print("Live-Spracherkennung (Vosk, lokal) gestartet. Strg+C zum Beenden.")
        print("Sprich jetzt...")
        
        try:
            # Kontinuierliche Verarbeitung
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
        """Stoppe die Live-Spracherkennung."""
        self.is_running = False
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self.context_mode = False
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
            # Backward-compatible with older ChatAssistant versions on device
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
    recognizer = LiveVoskRecognition(
        model_path=model_path,
        device=settings.audio_input_device,
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
        confirm_timeout_sec=settings.confirm_timeout_sec,
        enable_audio_processing=settings.enable_audio_processing,
        pause_duration=settings.vosk_pause_duration,
        vad_rms_threshold=settings.vad_rms_threshold,
        vad_noise_multiplier=settings.vad_noise_multiplier,
        vad_noise_alpha=settings.vad_noise_alpha,
        vad_hangover_factor=settings.vad_hangover_factor,
        vad_preroll_sec=settings.vad_preroll_sec,
        vad_use_webrtcvad=settings.vad_use_webrtcvad,
        vad_webrtcvad_mode=settings.vad_webrtcvad_mode,
        vad_webrtcvad_frame_ms=settings.vad_webrtcvad_frame_ms,
        ready_hold_sec=settings.ready_hold_sec,
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(recognizer._on_tts_done)
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_live_vosk_recognition(model_path)
