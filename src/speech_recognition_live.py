from __future__ import annotations
import io
import wave
import re
import numpy as np
import sounddevice as sd
import threading
import time
from typing import Callable, Optional
from openai import OpenAI

from .config import load_settings
from .audio_io import (
    _resolve_device_id,
    select_input_device,
    wait_for_playback_end,
    is_playback_active,
    play_beep_sequence,
    play_hangup_tone,
    stop_playback,
)
from .oled_display import OledDisplay
from .sentence_detection import (
    SemanticSpeechRecognition,
    should_send_to_chatgpt,
    chatgpt_filter_decision,
    chatgpt_filter_message,
)
from .chat_assistant import ChatAssistant


class LiveSpeechRecognition:
    """Live Spracherkennung mit Laufband-Anzeige auf OLED-Display."""
    
    def __init__(self, client: OpenAI, model_stt: str, device: Optional[str | int] = None,
                 enable_semantic: bool = True, language: str = "de",
                 pause_duration: float | None = None,
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
                 chat_assistant: Optional[ChatAssistant] = None,
                 confirm_before_chat: bool = False,
                 confirm_phrases: tuple[str, ...] | None = None,
                 reject_phrases: tuple[str, ...] | None = None,
                 confirm_timeout_sec: float = 6.0):
        self.client = client
        self.model_stt = model_stt
        self.device_spec = device
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.chunk_duration = 0.5  # Sekunden pro Chunk
        self.pause_duration = pause_duration if pause_duration is not None else 0.9
        self.silence_threshold = 0.02  # RMS-Schwellwert (0..1)
        self.noise_floor = 0.0
        self.noise_alpha = 0.95
        self.min_speech_sec = 0.6
        self.max_buffer_sec = 20.0
        self.is_running = False
        self.current_text = ""
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self.enable_semantic = enable_semantic
        self.semantic_processor = SemanticSpeechRecognition(language=language) if enable_semantic else None
        self.chat_assistant = chat_assistant
        self._last_chat_text: Optional[str] = None
        self._display_text: str = ""
        self._audio_buffer: list[np.ndarray] = []
        self._silence_sec = 0.0
        self._speech_active = False
        self._speech_sec = 0.0
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
        
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback
    
    def _transcribe_audio(self, wav_bytes: bytes) -> str:
        """Transkribiere Audio-Daten zu Text."""
        import tempfile
        import os
        
        wav_path = None
        try:
            fd, wav_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with open(wav_path, "wb") as f:
                f.write(wav_bytes)
            
            with open(wav_path, "rb") as f_audio:
                stt = self.client.audio.transcriptions.create(
                    model=self.model_stt,
                    file=f_audio
                )
            return (stt.text or "").strip()
        finally:
            if wav_path:
                try:
                    os.remove(wav_path)
                except OSError:
                    pass
    
    def _record_chunk(self) -> np.ndarray:
        """Nimmt einen Audio-Chunk auf und gibt Audio-Frames zurück."""
        channels = 1
        dtype = "int16"
        frames_to_record = int(self.samplerate * self.chunk_duration)
        
        recording = sd.rec(
            frames_to_record,
            samplerate=self.samplerate,
            channels=channels,
            dtype=dtype,
            device=self.device_id
        )
        sd.wait()
        return recording.reshape(-1)

    def _audio_to_wav(self, audio: np.ndarray) -> bytes:
        """Konvertiere Audio-Frames zu WAV-Bytes."""
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.samplerate)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display mit Laufband-Text."""
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
        self._display_text = status_text
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
        self._display_text = ""
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
        self._display_text = ""
        self._pending_prefix = ""
        if self.semantic_processor:
            self.semantic_processor.reset()
        return True

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
    
    def _process_text(self, text: str) -> None:
        """Verarbeite erkannten Text (Anzeige, Semantik, ChatGPT)."""
        if not text:
            return
        self._last_activity_ts = time.time()
        now = time.time()
        if now < self._ignore_until:
            if self.chat_filter_debug:
                print("ChatGPT-Filter: blockiert (nach TTS)")
            self._debug("ignore: after tts")
            return
        norm_text = self._normalize_command_text(text)
        if self._last_tts_text and norm_text:
            if norm_text in self._last_tts_text or self._last_tts_text in norm_text:
                if self.chat_filter_debug:
                    print("ChatGPT-Filter: blockiert (Echo von TTS)")
                self._debug("ignore: tts echo")
                return
        if self._awaiting_confirm and self._confirm_deadline and time.time() > self._confirm_deadline:
            self._cancel_confirmation()
            return
        if self._awaiting_confirm:
            if self._handle_confirmation(text):
                return
        # Prüfe, ob Text bereits vorhanden ist (verhindert Doppel-Ausgabe)
        if self.current_text and text.lower() in self.current_text.lower():
            return

        text = re.sub(r'\s+', ' ', text).strip()

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
            self._debug(f"pending_prefix merged: '{text}'")

        if self.semantic_processor:
            temp_text = self.current_text + " " + text if self.current_text else text
            result = self.semantic_processor.process_text(temp_text)

            corrected_text = result.get('corrected_text', temp_text)
            self.current_text = corrected_text

            corrections = result.get('corrections', [])
            if corrections:
                print(f"🔧 {len(corrections)} Korrektur(en) angewendet")

            context = result.get('context')
            if context and context.domain:
                print(f"📋 Kontext: {context.domain} (Themen: {', '.join(context.topics)})")

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

            last_sentence = None
            if result.get("new_sentences"):
                last_sentence = result["new_sentences"][-1].text
            elif result.get("incomplete_sentence"):
                last_sentence = result["incomplete_sentence"]
            elif result.get("complete_sentences"):
                last_sentence = result["complete_sentences"][-1].text

            self._display_text = last_sentence or text
            self._update_display(self._display_text)

            if self.chat_assistant:
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
                                self.chat_assistant.handle_text(sentence.text, system_prompt_override=self._current_prompt())
                                sent_any = True
                        else:
                            self._pending_prefix = sentence.text
                            self._announce_chat_filter_block(reason)
                            if self.chat_filter_debug:
                                print(f"ChatGPT-Filter: '{sentence.text}' → blockiert ({reason})")
                if sent_any:
                    self.current_text = ""
                    self._display_text = ""
                    self._pending_prefix = ""
                    if self.semantic_processor:
                        self.semantic_processor.reset()
        else:
            self.current_text = text
            self._display_text = text
            self._update_display(self._display_text)

            if self.chat_assistant:
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
                            self.chat_assistant.handle_text(text, system_prompt_override=self._current_prompt())
                            self.current_text = ""
                            self._display_text = ""
                            self._pending_prefix = ""
                    else:
                        self._pending_prefix = text
                        self._announce_chat_filter_block(reason)
                        if self.chat_filter_debug:
                            print(f"ChatGPT-Filter: '{text}' → blockiert ({reason})")

        if self.text_callback:
            self.text_callback(self._display_text)

        print(f"Erkannt: {text}")
        print(f"Anzeige: {self._display_text}")

    def _process_chunk(self) -> None:
        """Nimmt einen Chunk auf, erkennt Ende der Aussage, transkribiert und aktualisiert das Display."""
        try:
            # Während Ausgabe nichts aufnehmen
            wait_for_playback_end()
            if self._awaiting_confirm and self._confirm_deadline and time.time() > self._confirm_deadline:
                self._cancel_confirmation()
                return
            self._debug("record_chunk: start")
            audio = self._record_chunk()
            self._debug(f"record_chunk: done len={len(audio)}")

            # Falls währenddessen Ausgabe startet, Chunk verwerfen
            if is_playback_active():
                self._audio_buffer.clear()
                self._silence_sec = 0.0
                self._speech_active = False
                self._speech_sec = 0.0
                self._debug("playback active: drop chunk")
                return
            
            if not self.is_running:
                return

            # RMS für einfache Sprachaktivität
            rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)) / 32768.0) if audio.size else 0.0
            if not self._speech_active:
                # Rauschpegel lernen (EMA)
                if self.noise_floor == 0.0:
                    self.noise_floor = rms
                else:
                    self.noise_floor = (self.noise_alpha * self.noise_floor) + ((1 - self.noise_alpha) * rms)
            dynamic_threshold = max(self.silence_threshold, self.noise_floor * 3.0)
            is_speech = rms > dynamic_threshold

            if is_speech:
                self._audio_buffer.append(audio)
                self._silence_sec = 0.0
                self._speech_active = True
                self._speech_sec += self.chunk_duration
                total_sec = (sum(len(a) for a in self._audio_buffer) / self.samplerate)
                if total_sec >= self.max_buffer_sec:
                    wav_bytes = self._audio_to_wav(np.concatenate(self._audio_buffer))
                    self._audio_buffer.clear()
                    self._speech_active = False
                    self._speech_sec = 0.0
                    self._debug("max_buffer reached: transcribe")
                    text = self._transcribe_audio(wav_bytes)
                    self._process_text(text)
                return

            if not self._speech_active:
                self._debug("vad: no speech")
                return

            # Stille nach Sprache erkennen
            self._silence_sec += self.chunk_duration
            if self._silence_sec >= self.pause_duration and self._audio_buffer:
                total_sec = (sum(len(a) for a in self._audio_buffer) / self.samplerate)
                if total_sec < self.min_speech_sec:
                    # Zu kurz -> verwerfen (verhindert Rauschen/Artefakte)
                    self._audio_buffer.clear()
                    self._speech_active = False
                    self._silence_sec = 0.0
                    self._speech_sec = 0.0
                    self._debug("speech too short: drop")
                    return
                wav_bytes = self._audio_to_wav(np.concatenate(self._audio_buffer))
                self._audio_buffer.clear()
                self._speech_active = False
                self._silence_sec = 0.0
                self._speech_sec = 0.0
                self._debug("silence: transcribe")
                text = self._transcribe_audio(wav_bytes)
                self._process_text(text)
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
        
        if self.oled:
            self.oled.show_listening()

        self._set_listening(False, "Start")
        
        # Geräteauswahl anzeigen + Fallback
        self.device_id = select_input_device(self.device_spec, announce=True)

        print("Live-Spracherkennung gestartet. Strg+C zum Beenden.")
        print("Sprich jetzt...")
        
        try:
            # Prüfe, ob das Eingabegerät verfügbar ist
            try:
                sd.check_input_settings(
                    device=self.device_id,
                    samplerate=self.samplerate,
                    channels=1,
                    dtype="int16"
                )
            except sd.PortAudioError as e:
                print(f"Audio-Fehler: {e}")
                return

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
        self._audio_buffer.clear()
        self._silence_sec = 0.0
        self._speech_active = False
        self._speech_sec = 0.0
        self._display_text = ""
        self.listening_active = False
        self._paused_notice = False
        self._status_text = None
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_live_recognition(enable_chatgpt: bool = False):
    """Hauptfunktion für Live-Spracherkennung."""
    import sys
    
    settings = load_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    
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
    
    # ChatGPT-Assistent (optional)
    chat_assistant = None
    if enable_chatgpt:
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

    # Live-Spracherkennung starten
    recognizer = LiveSpeechRecognition(
        client=client,
        model_stt=settings.model_stt,
        device=settings.audio_input_device,
        pause_duration=settings.live_pause_duration,
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
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(recognizer._on_tts_done)
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    run_live_recognition()

