from __future__ import annotations
import io
import wave
import json
import queue
import re
import time
import threading
from collections import deque
import numpy as np
import sounddevice as sd
from typing import Callable, Optional
from pathlib import Path

try:
    from scipy.signal import resample_poly
except ImportError:  # pragma: no cover
    resample_poly = None  # type: ignore

from .audio_io import (
    _resolve_device_id,
    select_input_device,
    is_playback_active,
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
    
    def create_stream_recognizer(self):
        """Create a KaldiRecognizer for one utterance (caller owns lifetime)."""
        from vosk import KaldiRecognizer

        rec = KaldiRecognizer(self.recognizer, self.samplerate)
        rec.SetWords(False)
        return rec

    def feed_stream(
        self,
        rec,
        audio_data: np.ndarray,
        want_partial: bool = True,
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Feed int16 mono 16 kHz audio into an open recognizer.

        Returns:
            (accepted_text, partial_text) — accepted_text when AcceptWaveform
            returns True; partial_text from PartialResult only if want_partial.
        """
        if audio_data is None or audio_data.size == 0:
            return None, None
        if audio_data.dtype != np.int16:
            audio_data = audio_data.astype(np.int16)
        audio_bytes = audio_data.tobytes()
        accepted_parts: list[str] = []
        partial: Optional[str] = None
        try:
            # One AcceptWaveform call per feed for small realtime frames
            if rec.AcceptWaveform(audio_bytes):
                result = json.loads(rec.Result())
                if result.get("text"):
                    accepted_parts.append(result["text"])
            elif want_partial:
                try:
                    partial_result = json.loads(rec.PartialResult())
                    partial = (partial_result.get("partial") or "").strip() or None
                except Exception:
                    pass
        except Exception as e:
            print(f"Fehler bei Vosk feed_stream: {e}")
            return None, None
        accepted = re.sub(r"\s+", " ", " ".join(accepted_parts)).strip() or None
        return accepted, partial

    def finalize_stream(self, rec) -> str:
        """Flush recognizer and return remaining text."""
        try:
            final_result = json.loads(rec.FinalResult())
            text = (final_result.get("text") or "").strip()
            return re.sub(r"\s+", " ", text)
        except Exception as e:
            print(f"Fehler bei Vosk finalize_stream: {e}")
            return ""

    def transcribe_audio_stream(self, audio_data: np.ndarray) -> str:
        """
        Transkribiere Audio-Daten direkt aus numpy-Array (eine Äußerung).

        Args:
            audio_data: numpy-Array mit Audio-Daten (int16, mono, 16kHz)

        Returns:
            Erkannten Text
        """
        try:
            rec = self.create_stream_recognizer()
            accepted, _partial = self.feed_stream(rec, audio_data)
            final = self.finalize_stream(rec)
            parts = [p for p in (accepted, final) if p]
            return re.sub(r"\s+", " ", " ".join(parts)).strip()
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
                 vad_preroll_sec: float = 0.30,
                 ready_hold_sec: float = 10.0,
                 vad_use_webrtcvad: bool = True,
                 vad_webrtcvad_mode: int = 1,
                 vad_webrtcvad_frame_ms: int = 30,
                 vad_speech_ratio: float = 0.2):
        """
        Initialisiere Live-Vosk-Spracherkennung.
        
        Args:
            model_path: Pfad zum Vosk-Modell
            device: Audio-Eingabegerät
            chunk_duration: Legacy; live path uses 30 ms VAD frames (kept for API compat)
            enable_audio_processing: HPF + RMS-AGC aktivieren
            enable_semantic: Semantische Satzerkennung aktivieren
            language: Sprache für semantische Analyse
        """
        self.debug_logs = debug_logs
        self.audio_output_device = audio_output_device
        self.vosk = VoskSpeechRecognition(model_path, device, debug=debug_logs)
        self.samplerate = 16000
        self.chunk_duration = chunk_duration  # legacy; streaming uses frame_ms blocks
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
        self._preroll_buf: deque[np.ndarray] = deque()
        self._preroll_len = 0
        self.vad_use_webrtcvad = vad_use_webrtcvad
        self.vad_webrtcvad_mode = max(0, min(int(vad_webrtcvad_mode), 3))
        self.vad_webrtcvad_frame_ms = 30 if int(vad_webrtcvad_frame_ms) not in (10, 20, 30) else int(vad_webrtcvad_frame_ms)
        self.vad_speech_ratio = max(0.05, min(float(vad_speech_ratio), 0.9))
        self._webrtcvad = None
        if self.vad_use_webrtcvad:
            from .webrtcvad_loader import load_webrtcvad

            self._webrtcvad, vad_err = load_webrtcvad(self.vad_webrtcvad_mode)
            if self._webrtcvad is None:
                hint = ""
                if vad_err and "pkg_resources" in (vad_err or ""):
                    hint = (
                        " — setuptools>=82 removed pkg_resources; "
                        "update src/webrtcvad_loader.py or: pip install 'setuptools<82'"
                    )
                elif vad_err and "webrtcvad" in (vad_err or ""):
                    hint = " — fix: pip install webrtcvad"
                print(f"webrtcvad: unavailable ({vad_err}){hint}. Falling back to RMS VAD.")
                if self.debug_logs:
                    self._debug(f"webrtcvad: unavailable ({vad_err}){hint}")
            elif self.debug_logs:
                src = getattr(self._webrtcvad, "_pkg_resources_source", "?")
                self._debug(f"webrtcvad: ready mode={self.vad_webrtcvad_mode} pkg_resources={src}")
        self._noise_floor = 0.0
        # Continuous capture / utterance streaming state
        self._audio_q: queue.Queue | None = None
        self._capture_sr = self.samplerate
        self._input_stream = None
        self._utt_rec = None
        self._utt_accepted: list[str] = []
        self._utt_samples = 0
        self._min_utt_sec = 0.35
        self._agc_target_rms = 10 ** (-18.0 / 20.0)  # -18 dBFS
        self._agc_max_gain = 10 ** (15.0 / 20.0)  # +15 dB cap
        # Don't boost near-silence / noise floor (prevents hiss amplification)
        self._agc_min_rms = max(0.004, float(vad_rms_threshold) * 0.5)
        self._last_partial = ""
        self._debug_last_ts: dict[str, float] = {}
        self._max_utt_sec = 8.0
        self._partial_interval_sec = 0.35
        self._last_partial_ts = 0.0
        self._overflow_count = 0
        self._hpf_b = None
        self._hpf_a = None
        self._hpf_zi = None
        try:
            from scipy import signal as _sig
            nyq = self.samplerate / 2.0
            self._hpf_b, self._hpf_a = _sig.butter(2, 80.0 / nyq, btype="high", analog=False)
            self._hpf_zi = _sig.lfilter_zi(self._hpf_b, self._hpf_a)
        except Exception:
            self._hpf_b = self._hpf_a = self._hpf_zi = None
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback

    def _debug_throttle(self, key: str, msg: str, interval_sec: float = 1.0) -> None:
        """Rate-limit high-frequency debug lines (VAD/AGC per frame)."""
        if not self.debug_logs:
            return
        now = time.time()
        last = self._debug_last_ts.get(key, 0.0)
        if (now - last) < interval_sec:
            return
        self._debug_last_ts[key] = now
        self._debug(msg)
    
    def _normalize_audio(self, audio: np.ndarray) -> np.ndarray:
        """RMS-Ziel-AGC mit Gain-Cap (kein Peak-Normalize)."""
        if audio.size == 0:
            return audio
        audio_float = audio.astype(np.float32) / 32768.0
        audio_float = audio_float - np.mean(audio_float)
        rms = float(np.sqrt(np.mean(audio_float ** 2)))
        if rms < 1e-6:
            return audio
        # Skip AGC on noise/silence — max-gain on hiss hurts Vosk
        if rms < self._agc_min_rms:
            self._debug_throttle(
                "agc_skip",
                f"agc: skip rms={rms:.6f} < min={self._agc_min_rms:.6f}",
                2.0,
            )
            return (np.clip(audio_float, -1.0, 1.0) * 32767.0).astype(np.int16)
        gain = min(self._agc_target_rms / rms, self._agc_max_gain)
        audio_float = np.clip(audio_float * gain, -1.0, 1.0)
        if gain > 1.01:
            self._debug_throttle("agc", f"agc: rms={rms:.6f} gain={gain:.2f}x", 1.0)
        return (audio_float * 32767.0).astype(np.int16)
    
    def _apply_highpass_filter(self, audio: np.ndarray, cutoff: float = 80.0) -> np.ndarray:
        """Streaming high-pass (lfilter). Avoid filtfilt — too slow for 30 ms frames."""
        if self._hpf_b is None or audio.size == 0:
            return audio
        try:
            from scipy import signal
            audio_float = audio.astype(np.float32) / 32768.0
            zi = self._hpf_zi * float(audio_float[0]) if self._hpf_zi is not None else None
            filtered, zo = signal.lfilter(self._hpf_b, self._hpf_a, audio_float, zi=zi)
            self._hpf_zi = zo
            return (np.clip(filtered, -1.0, 1.0) * 32767.0).astype(np.int16)
        except Exception:
            return audio
    
    def _detect_speech(self, audio: np.ndarray, threshold: float = 0.01) -> bool:
        """Voice Activity Detection (VAD)."""
        if self._webrtcvad is not None:
            return self._detect_speech_webrtcvad(audio)
        # Berechne RMS (Root Mean Square) für Signalpegel
        audio_float = audio.astype(np.float32) / 32768.0
        rms = float(np.sqrt(np.mean(audio_float ** 2)))
        base_threshold = self.vad_rms_threshold if self.vad_rms_threshold > 0 else threshold
        # Update noise floor with a slow EMA when below base threshold
        if self.vad_noise_alpha > 0 and rms < base_threshold:
            if self._noise_floor <= 0:
                self._noise_floor = rms
            else:
                self._noise_floor = (1.0 - self.vad_noise_alpha) * self._noise_floor + self.vad_noise_alpha * rms
        effective_threshold = max(base_threshold, self._noise_floor * self.vad_noise_multiplier)
        if self._speech_active:
            # Hangover may lower the gate, but never into the noise floor
            lowered = effective_threshold * self.vad_hangover_factor
            noise_floor = max(self._noise_floor, 1e-6)
            effective_threshold = max(
                lowered,
                noise_floor * 1.5,
                base_threshold * 0.5,
            )
        is_speech = rms > effective_threshold
        self._debug_throttle(
            "vad_rms",
            f"vad: rms={rms:.6f} base={base_threshold:.6f} "
            f"noise={self._noise_floor:.6f} mult={self.vad_noise_multiplier:.2f} "
            f"hangover={self.vad_hangover_factor:.2f} th={effective_threshold:.6f} "
            f"speech={is_speech}",
            1.0,
        )
        return is_speech

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
        if total_frames == 0:
            return False
        ratio = speech_frames / total_frames
        threshold = self.vad_speech_ratio
        if self._speech_active:
            threshold = max(0.05, threshold * self.vad_hangover_factor)
        is_speech = ratio >= threshold
        self._debug_throttle(
            "vad_webrtc",
            f"vad: webrtcvad frames={total_frames} speech={speech_frames} "
            f"ratio={ratio:.2f} th={threshold:.2f} active={self._speech_active} "
            f"speech={is_speech}",
            1.0,
        )
        return is_speech
    
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
    
    def _handle_recognized_text(self, text: str) -> None:
        """Process a finalized utterance transcript (wake/chat/OLED)."""
        text = re.sub(r"\s+", " ", (text or "")).strip()
        if not text:
            return
        self._last_activity_ts = time.time()

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

        if self.current_text and text.lower() in self.current_text.lower():
            return

        if self.semantic_processor:
            temp_text = self.current_text + " " + text if self.current_text else text
            result = self.semantic_processor.process_text(temp_text)
            corrected_text = result.get("corrected_text", temp_text)
            self.current_text = corrected_text

            corrections = result.get("corrections", [])
            if corrections:
                print(f"🔧 {len(corrections)} Korrektur(en) angewendet")

            context = result.get("context")
            if context and context.domain:
                print(f"📋 Kontext: {context.domain} (Themen: {', '.join(context.topics)})")

            for info in result["semantic_info"]:
                sentence = info["sentence"]
                analysis = info["analysis"]
                sentence_type = info["type"]
                type_emoji = {
                    "question": "❓",
                    "imperative": "❗",
                    "exclamation": "❗",
                    "statement": "💬",
                }
                emoji = type_emoji.get(sentence_type, "💬")
                print(f"{emoji} [{sentence_type.upper()}] {sentence.text}")
                if analysis["sentiment"] != "neutral":
                    print(f"   Sentiment: {analysis['sentiment']}")

            display_text = self.semantic_processor.get_display_text(max_sentences=2)
            if display_text:
                self._update_display(display_text)
            else:
                self._update_display(self.current_text)

            # With utterance EOS, send current text when pause_duration is used
            if self.chat_assistant and not self.pause_duration:
                sent_any = False
                for sentence in result.get("new_sentences", []):
                    if sentence and sentence.text:
                        allowed, reason = chatgpt_filter_decision(
                            sentence.text, self.min_chat_words, self.trivial_words
                        )
                        if allowed:
                            if self.debug_logs:
                                print(
                                    f"[DEBUG] prompt=NEW"
                                    if not self.context_mode
                                    else "[DEBUG] prompt=KONTEXT"
                                )
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
            elif self.chat_assistant and self.pause_duration:
                # Finalize via pause path using accumulated current_text
                self._silence_sec = self.pause_duration
                self._finalize_current_text()
        else:
            if self.current_text:
                self.current_text += " " + text
            else:
                self.current_text = text
            self._update_display(self.current_text)

            if self.chat_assistant and not self.pause_duration:
                if self._last_chat_text != text:
                    allowed, reason = chatgpt_filter_decision(
                        text, self.min_chat_words, self.trivial_words
                    )
                    if allowed:
                        self._last_chat_text = text
                        if self.debug_logs:
                            print(
                                f"[DEBUG] prompt=NEW"
                                if not self.context_mode
                                else "[DEBUG] prompt=KONTEXT"
                            )
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
            elif self.chat_assistant and self.pause_duration:
                self._silence_sec = self.pause_duration
                self._finalize_current_text()

        if self.text_callback:
            self.text_callback(self.current_text)

        print(f"Erkannt: {text}")
        print(f"Gesamt: {self.current_text}")

    def _resolve_capture_samplerate(self) -> int:
        """Prefer 16 kHz; fall back to device default (resample later)."""
        device_id = self.vosk.device_id
        for sr in (self.samplerate, 48000, 44100):
            try:
                sd.check_input_settings(
                    device=device_id, samplerate=sr, channels=1, dtype="int16"
                )
                return sr
            except Exception:
                continue
        try:
            info = sd.query_devices(device_id, "input")
            return int(info.get("default_samplerate") or self.samplerate)
        except Exception:
            return self.samplerate

    def _audio_callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        if status:
            # input overflow = main loop too slow; count + throttle log
            self._overflow_count += 1
            self._debug_throttle(
                "stream_status",
                f"stream status: {status} (overflows={self._overflow_count})",
                2.0,
            )
        if self._audio_q is None:
            return
        try:
            mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            self._audio_q.put_nowait(mono)
        except queue.Full:
            # Drop oldest to stay near realtime
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                pass
            try:
                mono = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
                self._audio_q.put_nowait(mono)
            except queue.Full:
                pass

    def _to_asr_rate(self, audio: np.ndarray) -> np.ndarray:
        if self._capture_sr == self.samplerate or audio.size == 0:
            return audio.astype(np.int16, copy=False)
        # Fast integer decimation for common 48k→16k / 44.1≈16k paths
        if self._capture_sr == 48000 and self.samplerate == 16000:
            return np.asarray(audio[::3], dtype=np.int16)
        if self._capture_sr == 44100 and self.samplerate == 16000:
            # ~2.756x; use stride-2 then light poly if available
            stepped = audio[::2]
            if resample_poly is None:
                return np.asarray(stepped[::1], dtype=np.int16)[: int(len(audio) * 16000 / 44100)]
            return resample_poly(stepped, 16000, 22050).astype(np.int16)
        if resample_poly is None:
            ratio = self.samplerate / float(self._capture_sr)
            idx = (np.arange(int(len(audio) * ratio)) / ratio).astype(np.int64)
            idx = np.clip(idx, 0, len(audio) - 1)
            return audio[idx].astype(np.int16)
        return resample_poly(audio, self.samplerate, self._capture_sr).astype(np.int16)

    def _drop_audio_backlog(self, keep_blocks: int = 8) -> int:
        """Drop queued mic blocks so we stay near realtime. Returns dropped count."""
        if self._audio_q is None:
            return 0
        dropped = 0
        # Leave keep_blocks (~keep_blocks * 30ms) for continuity
        while self._audio_q.qsize() > keep_blocks:
            try:
                self._audio_q.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            self._debug_throttle(
                "backlog",
                f"audio: dropped {dropped} backlog blocks (keep={keep_blocks})",
                1.0,
            )
        return dropped

    def _push_preroll(self, frame: np.ndarray) -> None:
        if self._preroll_samples <= 0:
            return
        self._preroll_buf.append(frame.copy())
        self._preroll_len += len(frame)
        while self._preroll_len > self._preroll_samples and self._preroll_buf:
            old = self._preroll_buf.popleft()
            self._preroll_len -= len(old)
            if self._preroll_len < self._preroll_samples and old.size:
                # keep tail if we overshot
                need = self._preroll_samples - self._preroll_len
                if need > 0 and need < len(old):
                    keep = old[-need:]
                    self._preroll_buf.appendleft(keep)
                    self._preroll_len += len(keep)

    def _preroll_concat(self) -> np.ndarray:
        if not self._preroll_buf:
            return np.zeros(0, dtype=np.int16)
        return np.concatenate(list(self._preroll_buf))

    def _begin_utterance(self, first_frame: np.ndarray) -> None:
        self._utt_rec = self.vosk.create_stream_recognizer()
        self._utt_accepted = []
        self._utt_samples = 0
        self._silence_sec = 0.0
        self._speech_active = True
        self._last_partial = ""
        self._last_partial_ts = 0.0
        # Reset streaming HPF state per utterance
        if self._hpf_b is not None:
            try:
                from scipy import signal as _sig
                self._hpf_zi = _sig.lfilter_zi(self._hpf_b, self._hpf_a)
            except Exception:
                pass
        preroll = self._preroll_concat()
        if preroll.size:
            self._feed_utt(preroll)
            self._debug(f"vad: preroll {len(preroll)} samples")
        self._feed_utt(first_frame)

    def _feed_utt(self, frame: np.ndarray) -> None:
        if self._utt_rec is None or frame.size == 0:
            return
        audio = frame
        if self.enable_audio_processing:
            audio = self._apply_highpass_filter(audio, cutoff=80.0)
            audio = self._normalize_audio(audio)
        now = time.time()
        want_partial = (now - self._last_partial_ts) >= self._partial_interval_sec
        accepted, partial = self.vosk.feed_stream(
            self._utt_rec, audio, want_partial=want_partial
        )
        self._utt_samples += len(frame)
        if accepted:
            self._utt_accepted.append(accepted)
        if want_partial and partial and partial != self._last_partial:
            self._last_partial = partial
            self._last_partial_ts = now
            display = " ".join(self._utt_accepted + [partial]).strip()
            if display:
                self._update_display(display)

    def _end_utterance(self) -> None:
        if self._utt_rec is None:
            self._speech_active = False
            self._silence_sec = 0.0
            return
        final = self.vosk.finalize_stream(self._utt_rec)
        parts = [p for p in (self._utt_accepted + ([final] if final else [])) if p]
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        utt_sec = self._utt_samples / float(self.samplerate)
        self._debug(f"utt: end sec={utt_sec:.2f} text='{text}'")
        self._utt_rec = None
        self._utt_accepted = []
        self._utt_samples = 0
        self._speech_active = False
        self._silence_sec = 0.0
        self._last_partial = ""
        if utt_sec < self._min_utt_sec:
            self._debug("utt: skipped (too short)")
            return
        if text:
            self._handle_recognized_text(text)

    def _drain_audio_queue(self) -> None:
        if self._audio_q is None:
            return
        while True:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                break

    def _process_frame(self, raw_frame: np.ndarray) -> None:
        """VAD + one KaldiRecognizer per utterance on continuous frames."""
        if self._awaiting_confirm and self._confirm_deadline and time.time() > self._confirm_deadline:
            self._cancel_confirmation()

        frame_sec = len(raw_frame) / float(self.samplerate)
        is_speech = self._detect_speech(raw_frame, threshold=0.005)

        if not is_speech:
            self._push_preroll(raw_frame)
            if self._speech_active and self._utt_rec is not None:
                pause = self.pause_duration if self.pause_duration else 1.2
                self._silence_sec += frame_sec
                # Feed trailing silence without heavy OLED partials
                self._feed_utt(raw_frame)
                utt_sec = self._utt_samples / float(self.samplerate)
                if self._silence_sec >= pause or utt_sec >= self._max_utt_sec:
                    if utt_sec >= self._max_utt_sec:
                        self._debug(f"utt: force-end after {utt_sec:.1f}s")
                    self._end_utterance()
            return

        self._silence_sec = 0.0
        if not self._speech_active or self._utt_rec is None:
            self._begin_utterance(raw_frame)
        else:
            self._feed_utt(raw_frame)
            utt_sec = self._utt_samples / float(self.samplerate)
            if utt_sec >= self._max_utt_sec:
                self._debug(f"utt: force-end after {utt_sec:.1f}s")
                self._end_utterance()
                return
        self._push_preroll(raw_frame)

    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte die Live-Spracherkennung (continuous InputStream)."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        self._last_activity_ts = time.time()
        self.context_mode = False
        self._utt_rec = None
        self._utt_accepted = []
        self._utt_samples = 0
        self._speech_active = False
        self._silence_sec = 0.0
        self._preroll_buf.clear()
        self._preroll_len = 0

        self.vosk.device_id = select_input_device(self.vosk.device_spec, announce=True)
        self._log_input_device()
        self._capture_sr = self._resolve_capture_samplerate()
        self._debug(f"capture_sr={self._capture_sr} asr_sr={self.samplerate}")

        if self.oled:
            self.oled.show_listening()

        self._set_listening(False, "Start")
        play_status_listening(device=self.audio_output_device)
        try:
            play_beep_sequence(device=self.audio_output_device, announce=False)
        except Exception as e:
            print(f"Beep-Fehler: {e}")

        print("Live-Spracherkennung (Vosk, lokal, streaming) gestartet. Strg+C zum Beenden.")
        print("Sprich jetzt...")

        blocksize = max(1, int(self._capture_sr * (self.vad_webrtcvad_frame_ms / 1000.0)))
        self._audio_q = queue.Queue(maxsize=40)
        try:
            self._input_stream = sd.InputStream(
                samplerate=self._capture_sr,
                channels=1,
                dtype="int16",
                device=self.vosk.device_id,
                blocksize=blocksize,
                callback=self._audio_callback,
            )
            self._input_stream.start()
        except Exception as e:
            print(f"InputStream-Fehler ({e}); Fallback auf Chunk-Aufnahme.")
            self._input_stream = None

        try:
            while self.is_running:
                if self.listening_active and self.auto_pause_after_sec > 0:
                    if self._force_ready_until and time.time() < self._force_ready_until:
                        pass
                    elif (time.time() - self._last_activity_ts) >= self.auto_pause_after_sec:
                        self._set_listening(False, "Inaktivität")

                # Discard mic audio while TTS/playback is active
                if is_playback_active():
                    self._drain_audio_queue()
                    if self._utt_rec is not None:
                        self._end_utterance()
                    time.sleep(0.05)
                    continue

                if self._input_stream is None:
                    # Fallback: short blocking record (still utterance-aware)
                    frames = int(self.samplerate * (self.vad_webrtcvad_frame_ms / 1000.0))
                    raw = record_audio_chunk(
                        frames,
                        samplerate=self.samplerate,
                        device_id=self.vosk.device_id,
                        channels=1,
                        dtype="int16",
                    )
                    if len(raw.shape) > 1:
                        raw = raw[:, 0]
                    self._process_frame(raw.astype(np.int16))
                    continue

                # Stay near realtime: if behind, drop old blocks (prevents 40s+ stuck utts)
                if self._utt_rec is None:
                    self._drop_audio_backlog(keep_blocks=6)
                else:
                    # During utterance keep a bit more context, but never > ~0.6s backlog
                    self._drop_audio_backlog(keep_blocks=20)
                    qsz = self._audio_q.qsize() if self._audio_q else 0
                    if qsz > 40:
                        # Hopelessly behind — end utterance and resync
                        self._debug(f"audio: resync (qsize={qsz}), ending utterance")
                        self._end_utterance()
                        self._drain_audio_queue()
                        continue

                try:
                    block = self._audio_q.get(timeout=0.2)
                except queue.Empty:
                    continue
                asr = self._to_asr_rate(np.asarray(block, dtype=np.int16))
                # Split into ASR-rate VAD frames
                frame_len = int(self.samplerate * (self.vad_webrtcvad_frame_ms / 1000.0))
                if frame_len <= 0:
                    continue
                for i in range(0, len(asr) - frame_len + 1, frame_len):
                    self._process_frame(asr[i : i + frame_len])
                rem = len(asr) % frame_len
                if rem and rem >= frame_len // 2:
                    # Ignore tiny remainder to avoid extra Vosk calls
                    self._process_frame(asr[-rem:])
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
        if self._utt_rec is not None:
            try:
                self._end_utterance()
            except Exception:
                self._utt_rec = None
        if self._input_stream is not None:
            try:
                self._input_stream.stop()
                self._input_stream.close()
            except Exception:
                pass
            self._input_stream = None
        self._audio_q = None
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
        vad_speech_ratio=settings.vad_speech_ratio,
        ready_hold_sec=settings.ready_hold_sec,
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(recognizer._on_tts_done)
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    model_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_live_vosk_recognition(model_path)
