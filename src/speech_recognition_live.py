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
from .audio_io import _resolve_device_id, select_input_device, wait_for_playback_end, is_playback_active
from .oled_display import OledDisplay
from .sentence_detection import SemanticSpeechRecognition, should_send_to_chatgpt
from .chat_assistant import ChatAssistant


class LiveSpeechRecognition:
    """Live Spracherkennung mit Laufband-Anzeige auf OLED-Display."""
    
    def __init__(self, client: OpenAI, model_stt: str, device: Optional[str | int] = None,
                 enable_semantic: bool = True, language: str = "de",
                 pause_duration: float | None = None,
                 wake_phrases: tuple[str, ...] | None = None,
                 stop_phrases: tuple[str, ...] | None = None,
                 min_chat_words: int = 2,
                 trivial_words: list[str] | None = None,
                 chat_assistant: Optional[ChatAssistant] = None):
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
        self.stop_phrases = stop_phrases or ("stopp", "stop")
        self.min_chat_words = min_chat_words
        self.trivial_words = set(trivial_words or [])
        
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

    def _set_listening(self, active: bool, reason: str) -> None:
        status_text = "BEREIT" if active else "PAUSE"
        if self.listening_active == active and self._status_text == status_text:
            return
        self.listening_active = active
        self._paused_notice = not active
        self._status_text = status_text
        self._display_text = status_text
        self._update_display(status_text)
        print(f"STATUS: {status_text} ({reason})")

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
    
    def _process_text(self, text: str) -> None:
        """Verarbeite erkannten Text (Anzeige, Semantik, ChatGPT)."""
        if not text:
            return
        # Prüfe, ob Text bereits vorhanden ist (verhindert Doppel-Ausgabe)
        if self.current_text and text.lower() in self.current_text.lower():
            return

        text = re.sub(r'\s+', ' ', text).strip()

        cmd = self._check_commands(text)
        if cmd == "stop":
            self._set_listening(False, "STOPP erkannt")
            return
        if cmd == "wake":
            self._set_listening(True, "OK GOOGLE erkannt")
            return

        if not self.listening_active:
            self._set_listening(False, "Warte auf Wake")
            return

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
                for sentence in result.get("new_sentences", []):
                    if sentence and sentence.text:
                        if should_send_to_chatgpt(sentence.text, self.min_chat_words, self.trivial_words):
                            self.chat_assistant.handle_text(sentence.text)
        else:
            self.current_text = text
            self._display_text = text
            self._update_display(self._display_text)

            if self.chat_assistant:
                if self._last_chat_text != text and should_send_to_chatgpt(text, self.min_chat_words, self.trivial_words):
                    self._last_chat_text = text
                    self.chat_assistant.handle_text(text)

        if self.text_callback:
            self.text_callback(self._display_text)

        print(f"Erkannt: {text}")
        print(f"Anzeige: {self._display_text}")

    def _process_chunk(self) -> None:
        """Nimmt einen Chunk auf, erkennt Ende der Aussage, transkribiert und aktualisiert das Display."""
        try:
            # Während Ausgabe nichts aufnehmen
            wait_for_playback_end()
            audio = self._record_chunk()

            # Falls währenddessen Ausgabe startet, Chunk verwerfen
            if is_playback_active():
                self._audio_buffer.clear()
                self._silence_sec = 0.0
                self._speech_active = False
                self._speech_sec = 0.0
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
                    text = self._transcribe_audio(wav_bytes)
                    self._process_text(text)
                return

            if not self._speech_active:
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
                    return
                wav_bytes = self._audio_to_wav(np.concatenate(self._audio_buffer))
                self._audio_buffer.clear()
                self._speech_active = False
                self._silence_sec = 0.0
                self._speech_sec = 0.0
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
        chat_assistant = ChatAssistant(
            client=client,
            model_chat=settings.model_chat,
            model_tts=settings.model_tts,
            tts_voice=settings.tts_voice,
            audio_output_device=settings.audio_output_device,
        )

    # Live-Spracherkennung starten
    recognizer = LiveSpeechRecognition(
        client=client,
        model_stt=settings.model_stt,
        device=settings.audio_input_device,
        pause_duration=settings.live_pause_duration,
        wake_phrases=tuple(settings.wake_phrases),
        stop_phrases=tuple(settings.stop_phrases),
        min_chat_words=settings.min_chat_words,
        trivial_words=settings.trivial_words,
        chat_assistant=chat_assistant,
    )

    if chat_assistant and hasattr(chat_assistant, "set_on_tts_done"):
        chat_assistant.set_on_tts_done(lambda: recognizer._set_listening(False, "TTS fertig"))
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    run_live_recognition()

