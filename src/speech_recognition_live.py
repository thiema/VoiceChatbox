from __future__ import annotations
import io
import wave
import numpy as np
import sounddevice as sd
import threading
import time
from typing import Callable, Optional
from openai import OpenAI

from .config import load_settings
from .audio_io import _resolve_device_id
from .oled_display import OledDisplay
from .sentence_detection import SemanticSpeechRecognition


class LiveSpeechRecognition:
    """Live Spracherkennung mit Laufband-Anzeige auf OLED-Display."""
    
    def __init__(self, client: OpenAI, model_stt: str, device: Optional[str | int] = None,
                 enable_semantic: bool = True, language: str = "de"):
        self.client = client
        self.model_stt = model_stt
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
        self.chunk_duration = 2.0  # Sekunden pro Chunk
        self.is_running = False
        self.current_text = ""
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self.enable_semantic = enable_semantic
        self.semantic_processor = SemanticSpeechRecognition(language=language) if enable_semantic else None
        
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
    
    def _record_chunk(self) -> bytes:
        """Nimmt einen Audio-Chunk auf und gibt WAV-Bytes zurück."""
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
        
        # Konvertiere zu WAV
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.samplerate)
            wf.writeframes(recording.tobytes())
        return buf.getvalue()
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display mit Laufband-Text."""
        if self.oled and self.oled.device:
            self.oled.show_text_scroll(text)
    
    def _process_chunk(self) -> None:
        """Nimmt einen Chunk auf, transkribiert ihn und aktualisiert das Display."""
        try:
            # Audio aufnehmen
            wav_bytes = self._record_chunk()
            
            if not self.is_running:
                return
            
            # Transkribieren
            text = self._transcribe_audio(wav_bytes)
            
            if text:
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
                else:
                    # Standard: Einfache Text-Anzeige (ohne Korrektur)
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    self._update_display(self.current_text)
                
                # Callback aufrufen
                if self.text_callback:
                    self.text_callback(self.current_text)
                
                print(f"Erkannt: {text}")
                print(f"Gesamt: {self.current_text}")
        except Exception as e:
            print(f"Fehler bei Verarbeitung: {e}")
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte die Live-Spracherkennung."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        
        if self.oled:
            self.oled.show_listening()
        
        print("Live-Spracherkennung gestartet. Strg+C zum Beenden.")
        print("Sprich jetzt...")
        
        try:
            # Initialisiere Audio-Stream
            with sd.InputStream(
                device=self.device_id,
                samplerate=self.samplerate,
                channels=1,
                dtype="int16"
            ):
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
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_live_recognition():
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
    
    # Live-Spracherkennung starten
    recognizer = LiveSpeechRecognition(
        client=client,
        model_stt=settings.model_stt,
        device=settings.audio_input_device
    )
    
    recognizer.start(oled=oled)


if __name__ == "__main__":
    run_live_recognition()

