from __future__ import annotations
import io
import wave
import numpy as np
import sounddevice as sd
import time
from typing import Callable, Optional
from openai import OpenAI

from .config import load_settings
from .audio_io import record_while_pressed, _resolve_device_id
from .oled_display import OledDisplay
from .gpio_inputs import PushToTalk
from .led_status import LedStatus, Status
from .sentence_detection import SemanticSpeechRecognition


class PTTLiveRecognition:
    """Push-to-Talk Live-Spracherkennung mit Laufband-Anzeige."""
    
    def __init__(self, client: OpenAI, model_stt: str, ptt: PushToTalk, 
                 leds: Optional[LedStatus] = None, device: Optional[str | int] = None,
                 enable_semantic: bool = True, language: str = "de"):
        self.client = client
        self.model_stt = model_stt
        self.ptt = ptt
        self.leds = leds
        self.device_id = _resolve_device_id(device)
        self.samplerate = 16000
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
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display mit Laufband-Text."""
        if self.oled and self.oled.device:
            self.oled.show_text_scroll(text)
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte Push-to-Talk Live-Spracherkennung."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        
        if self.oled:
            self.oled.show_ready()
        
        if self.leds:
            self.leds.set(Status.IDLE)
        
        print("="*60)
        print("Push-to-Talk Live-Spracherkennung")
        print("="*60)
        print("Drücke und halte den Taster gedrückt zum Sprechen.")
        print("Der erkannte Text wird auf dem Display angezeigt.")
        print("Strg+C zum Beenden.")
        print("="*60)
        print()
        
        try:
            while self.is_running:
                # Warte auf Taster-Druck
                self.ptt.wait_for_press()
                
                if not self.is_running:
                    break
                
                # Status anzeigen
                if self.leds:
                    self.leds.set(Status.LISTENING)
                if self.oled:
                    self.oled.show_listening()
                
                print("🎤 Aufnahme läuft... (Taster gedrückt halten)")
                
                # Aufnahme während Taster gedrückt
                wav_bytes = record_while_pressed(
                    lambda: self.ptt.is_pressed,
                    samplerate=self.samplerate,
                    device=self.device_id
                )
                
                if not self.is_running:
                    break
                
                # Status: Denken
                if self.leds:
                    self.leds.set(Status.THINKING)
                if self.oled:
                    self.oled.show_thinking()
                
                print("🤔 Transkribiere...")
                
                # Transkribieren
                text = self._transcribe_audio(wav_bytes)
                
                if text:
                    # Text aktualisieren
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    
                    # Semantische Satzerkennung (falls aktiviert)
                    if hasattr(self, 'semantic_processor') and self.semantic_processor:
                        result = self.semantic_processor.process_text(self.current_text)
                        
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
                    
                    print(f"✅ Erkannt: {text}")
                    print(f"📝 Gesamt: {self.current_text}")
                    print()
                else:
                    print("⚠️  Kein Text erkannt")
                    print()
                
                # Status: Bereit
                if self.leds:
                    self.leds.set(Status.IDLE)
                if self.oled:
                    self.oled.show_ready()
                
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stoppe die Spracherkennung."""
        self.is_running = False
        if self.leds:
            self.leds.set(Status.IDLE)
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


class PTTLiveVoskRecognition:
    """Push-to-Talk Live-Spracherkennung mit Vosk (lokal)."""
    
    def __init__(self, vosk_recognizer, ptt: PushToTalk, 
                 leds: Optional[LedStatus] = None,
                 enable_semantic: bool = True, language: str = "de"):
        from .speech_recognition_vosk import VoskSpeechRecognition
        self.vosk = vosk_recognizer
        self.ptt = ptt
        self.leds = leds
        self.samplerate = 16000
        self.is_running = False
        self.current_text = ""
        self.oled: Optional[OledDisplay] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self.enable_semantic = enable_semantic
        self.semantic_processor = SemanticSpeechRecognition(language=language) if enable_semantic else None
    
    def set_text_callback(self, callback: Callable[[str], None]) -> None:
        """Setze Callback-Funktion, die bei neuem Text aufgerufen wird."""
        self.text_callback = callback
    
    def _update_display(self, text: str) -> None:
        """Aktualisiere OLED-Display mit Laufband-Text."""
        if self.oled and self.oled.device:
            self.oled.show_text_scroll(text)
    
    def start(self, oled: Optional[OledDisplay] = None) -> None:
        """Starte Push-to-Talk Live-Spracherkennung mit Vosk."""
        self.oled = oled
        self.is_running = True
        self.current_text = ""
        
        if self.oled:
            self.oled.show_ready()
        
        if self.leds:
            self.leds.set(Status.IDLE)
        
        print("="*60)
        print("Push-to-Talk Live-Spracherkennung (Vosk, lokal)")
        print("="*60)
        print("Drücke und halte den Taster gedrückt zum Sprechen.")
        print("Der erkannte Text wird auf dem Display angezeigt.")
        print("Strg+C zum Beenden.")
        print("="*60)
        print()
        
        try:
            while self.is_running:
                # Warte auf Taster-Druck
                self.ptt.wait_for_press()
                
                if not self.is_running:
                    break
                
                # Status anzeigen
                if self.leds:
                    self.leds.set(Status.LISTENING)
                if self.oled:
                    self.oled.show_listening()
                
                print("🎤 Aufnahme läuft... (Taster gedrückt halten)")
                
                # Aufnahme während Taster gedrückt
                wav_bytes = record_while_pressed(
                    lambda: self.ptt.is_pressed,
                    samplerate=self.samplerate,
                    device=self.vosk.device_id
                )
                
                if not self.is_running:
                    break
                
                # Status: Denken
                if self.leds:
                    self.leds.set(Status.THINKING)
                if self.oled:
                    self.oled.show_thinking()
                
                print("🤔 Transkribiere (lokal)...")
                
                # Transkribieren mit Vosk
                text = self.vosk.transcribe_audio(wav_bytes)
                
                if text:
                    # Text aktualisieren
                    if self.current_text:
                        self.current_text += " " + text
                    else:
                        self.current_text = text
                    
                    # Semantische Satzerkennung (falls aktiviert)
                    if hasattr(self, 'semantic_processor') and self.semantic_processor:
                        result = self.semantic_processor.process_text(self.current_text)
                        
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
                    
                    print(f"✅ Erkannt: {text}")
                    print(f"📝 Gesamt: {self.current_text}")
                    print()
                else:
                    print("⚠️  Kein Text erkannt")
                    print()
                
                # Status: Bereit
                if self.leds:
                    self.leds.set(Status.IDLE)
                if self.oled:
                    self.oled.show_ready()
                
        except KeyboardInterrupt:
            print("\nBeendet.")
        finally:
            self.stop()
    
    def stop(self) -> None:
        """Stoppe die Spracherkennung."""
        self.is_running = False
        if self.leds:
            self.leds.set(Status.IDLE)
        if self.oled:
            self.oled.clear()
        print("Spracherkennung gestoppt.")


def run_ptt_live_recognition(use_vosk: bool = False):
    """Hauptfunktion für Push-to-Talk Live-Spracherkennung."""
    import os
    
    settings = load_settings()
    
    if not settings.use_gpio:
        print("❌ USE_GPIO=false – Push-to-Talk benötigt GPIO.")
        print("   Bitte USE_GPIO=true in .env setzen.")
        return
    
    # GPIO initialisieren
    ptt = PushToTalk(settings.gpio_ptt)
    leds = LedStatus(
        settings.gpio_led_red,
        settings.gpio_led_yellow,
        settings.gpio_led_green,
        enabled=True
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
    
    if use_vosk:
        # Prüfe, ob mehrsprachig verwendet werden soll
        use_multilang = os.getenv("USE_MULTILANG", "").lower() in ("1", "true", "yes")
        
        if use_multilang:
            # Mehrsprachige Vosk-Erkennung
            from .speech_recognition_multilang import MultiLanguageVoskRecognition
            
            model_paths = {}
            if settings.vosk_model_path:
                model_paths["de"] = settings.vosk_model_path
            if settings.vosk_model_path_en:
                model_paths["en"] = settings.vosk_model_path_en
            
            if not model_paths:
                print("❌ Keine Modell-Pfade konfiguriert für mehrsprachige Erkennung!")
                return
            
            multilang_vosk = MultiLanguageVoskRecognition(model_paths, device=settings.audio_input_device)
            
            # Erstelle Wrapper für PTT
            class PTTMultiLangVoskRecognition:
                def __init__(self, multilang_vosk, ptt, leds):
                    self.multilang_vosk = multilang_vosk
                    self.ptt = ptt
                    self.leds = leds
                    self.samplerate = 16000
                    self.is_running = False
                    self.current_text = ""
                    self.oled = None
                    self.mode = "best"
                
                def start(self, oled=None):
                    self.oled = oled
                    self.is_running = True
                    self.current_text = ""
                    
                    if self.oled:
                        self.oled.show_ready()
                    if self.leds:
                        self.leds.set(Status.IDLE)
                    
                    print("="*60)
                    print("Push-to-Talk Mehrsprachige Spracherkennung (Vosk)")
                    print("="*60)
                    print(f"Sprachen: {', '.join(self.multilang_vosk.models.keys())}")
                    print("Drücke und halte den Taster gedrückt zum Sprechen.")
                    print("Strg+C zum Beenden.")
                    print("="*60)
                    print()
                    
                    try:
                        while self.is_running:
                            self.ptt.wait_for_press()
                            
                            if not self.is_running:
                                break
                            
                            if self.leds:
                                self.leds.set(Status.LISTENING)
                            if self.oled:
                                self.oled.show_listening()
                            
                            print("🎤 Aufnahme läuft...")
                            
                            from .audio_io import record_while_pressed
                            wav_bytes = record_while_pressed(
                                lambda: self.ptt.is_pressed,
                                samplerate=self.samplerate,
                                device=self.multilang_vosk.device_id
                            )
                            
                            if not self.is_running:
                                break
                            
                            if self.leds:
                                self.leds.set(Status.THINKING)
                            if self.oled:
                                self.oled.show_thinking()
                            
                            print("🤔 Transkribiere (mehrsprachig)...")
                            
                            lang, text = self.multilang_vosk.transcribe_audio_best(wav_bytes)
                            
                            if text:
                                if self.current_text:
                                    self.current_text += " " + text
                                else:
                                    self.current_text = text
                                
                                if self.oled:
                                    self.oled.show_text_scroll(self.current_text)
                                
                                print(f"✅ [{lang.upper()}] {text}")
                                print(f"📝 Gesamt: {self.current_text}")
                                print()
                            
                            if self.leds:
                                self.leds.set(Status.IDLE)
                            if self.oled:
                                self.oled.show_ready()
                                
                    except KeyboardInterrupt:
                        print("\nBeendet.")
                    finally:
                        self.stop()
                
                def stop(self):
                    self.is_running = False
                    if self.leds:
                        self.leds.set(Status.IDLE)
                    if self.oled:
                        self.oled.clear()
            
            recognizer = PTTMultiLangVoskRecognition(multilang_vosk, ptt, leds)
            recognizer.start(oled=oled)
        else:
            # Einsprachige Vosk-Erkennung
            from .speech_recognition_vosk import VoskSpeechRecognition
            
            model_path = settings.vosk_model_path or os.getenv("VOSK_MODEL_PATH", "models/vosk-model-de-0.22")
            vosk = VoskSpeechRecognition(model_path, device=settings.audio_input_device)
            
            recognizer = PTTLiveVoskRecognition(vosk, ptt, leds)
            recognizer.start(oled=oled)
    else:
        # OpenAI (Cloud)
        client = OpenAI(api_key=settings.openai_api_key)
        
        recognizer = PTTLiveRecognition(
            client=client,
            model_stt=settings.model_stt,
            ptt=ptt,
            leds=leds,
            device=settings.audio_input_device
        )
        recognizer.start(oled=oled)


if __name__ == "__main__":
    import sys
    use_vosk = "--vosk" in sys.argv
    run_ptt_live_recognition(use_vosk=use_vosk)
