#!/usr/bin/env python3
"""
Taster-Testprogramm für GPIO17 (Pin 11)

Testet den physisch angeschlossenen Taster und zeigt detaillierte Informationen.
"""

from __future__ import annotations
import sys
import time
from datetime import datetime
from typing import Optional

from .config import load_settings
from .gpio_inputs import PushToTalk
from .led_status import LedStatus, Status


class ButtonTester:
    """Umfassender Taster-Test."""
    
    def __init__(self, gpio_pin: int = 17):
        self.gpio_pin = gpio_pin
        self.ptt: Optional[PushToTalk] = None
        self.leds: Optional[LedStatus] = None
        
        # Statistiken
        self.press_count = 0
        self.release_count = 0
        self.total_press_duration = 0.0
        self.last_press_time: Optional[float] = None
        self.last_release_time: Optional[float] = None
        self.current_press_start: Optional[float] = None
        
    def init(self) -> bool:
        """Initialisiere GPIO und LEDs."""
        try:
            settings = load_settings()
            
            if not settings.use_gpio:
                print("❌ FEHLER: USE_GPIO=false in .env")
                print("   Bitte setze USE_GPIO=true in .env")
                return False
            
            # Initialisiere Taster
            print(f"🔌 Initialisiere Taster auf GPIO{self.gpio_pin} (Pin 11)...")
            self.ptt = PushToTalk(self.gpio_pin)
            print("✅ Taster initialisiert")
            
            # Initialisiere LEDs (optional)
            try:
                self.leds = LedStatus(
                    settings.gpio_led_red,
                    settings.gpio_led_yellow,
                    settings.gpio_led_green,
                    enabled=True
                )
                print("✅ LEDs initialisiert")
            except Exception as e:
                print(f"⚠️  LEDs konnten nicht initialisiert werden: {e}")
                print("   Test läuft ohne LED-Feedback")
                self.leds = None
            
            return True
        except Exception as e:
            print(f"❌ FEHLER beim Initialisieren: {e}")
            return False
    
    def test_basic(self) -> None:
        """Basis-Test: Zeige Taster-Status kontinuierlich."""
        print("\n" + "="*60)
        print("BASIS-TEST: Taster-Status")
        print("="*60)
        print(f"GPIO: {self.gpio_pin} (Pin 11)")
        print("Verdrahtung: GPIO17 → Taster → GND")
        print("Pull-Up: Aktiv (intern)")
        print("\nStatus-Anzeige:")
        print("  PRESSED  = Taster gedrückt")
        print("  RELEASED = Taster losgelassen")
        print("\nStrg+C zum Beenden\n")
        
        last_state = None
        try:
            while True:
                current_state = self.ptt.is_pressed
                
                if current_state != last_state:
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    
                    if current_state:
                        self.press_count += 1
                        self.last_press_time = time.time()
                        self.current_press_start = time.time()
                        print(f"[{timestamp}] 🟢 PRESSED  (Drück #{self.press_count})")
                        
                        if self.leds:
                            self.leds.set(Status.SPEAKING)  # Grün
                    else:
                        self.release_count += 1
                        self.last_release_time = time.time()
                        
                        # Berechne Druck-Dauer
                        if self.current_press_start:
                            duration = time.time() - self.current_press_start
                            self.total_press_duration += duration
                            print(f"[{timestamp}] ⚪ RELEASED (Dauer: {duration:.3f}s)")
                        else:
                            print(f"[{timestamp}] ⚪ RELEASED")
                        
                        if self.leds:
                            self.leds.set(Status.IDLE)
                    
                    last_state = current_state
                
                time.sleep(0.01)  # 10ms Polling
                
        except KeyboardInterrupt:
            print("\n\nTest beendet.")
            self._show_statistics()
    
    def test_events(self) -> None:
        """Event-Test: Nutze Callbacks für Drücke."""
        print("\n" + "="*60)
        print("EVENT-TEST: Callbacks")
        print("="*60)
        print("Warte auf Taster-Events...")
        print("Strg+C zum Beenden\n")
        
        def on_press():
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.press_count += 1
            print(f"[{timestamp}] 🟢 EVENT: PRESSED (Drück #{self.press_count})")
            if self.leds:
                self.leds.set(Status.SPEAKING)
        
        def on_release():
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            self.release_count += 1
            print(f"[{timestamp}] ⚪ EVENT: RELEASED (Losgelassen #{self.release_count})")
            if self.leds:
                self.leds.set(Status.IDLE)
        
        try:
            # Nutze gpiozero Callbacks
            self.ptt.button.when_pressed = on_press
            self.ptt.button.when_released = on_release
            
            print("✅ Callbacks registriert. Warte auf Events...\n")
            
            # Warte auf Events
            while True:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n\nTest beendet.")
            self._show_statistics()
    
    def test_wait_for_press(self) -> None:
        """Test: Warte auf Taster-Druck."""
        print("\n" + "="*60)
        print("WAIT-TEST: Blockierendes Warten")
        print("="*60)
        print("Drücke den Taster...")
        
        try:
            while True:
                print("\n⏳ Warte auf Taster-Druck...")
                start_time = time.time()
                
                self.ptt.wait_for_press()
                
                press_time = time.time()
                print(f"✅ Taster gedrückt! (Wartezeit: {press_time - start_time:.3f}s)")
                
                if self.leds:
                    self.leds.set(Status.SPEAKING)
                
                print("⏳ Warte auf Loslassen...")
                self.ptt.button.wait_for_release()
                
                release_time = time.time()
                duration = release_time - press_time
                print(f"✅ Taster losgelassen! (Dauer: {duration:.3f}s)")
                
                if self.leds:
                    self.leds.set(Status.IDLE)
                
                self.press_count += 1
                self.total_press_duration += duration
                
                time.sleep(0.5)  # Kurze Pause
                
        except KeyboardInterrupt:
            print("\n\nTest beendet.")
            self._show_statistics()
    
    def test_rapid_press(self, duration: float = 10.0) -> None:
        """Test: Schnelle Drücke für Stabilitätstest."""
        print("\n" + "="*60)
        print(f"RAPID-PRESS-TEST: {duration} Sekunden")
        print("="*60)
        print("Drücke den Taster so schnell wie möglich!")
        print("Strg+C zum vorzeitigen Beenden\n")
        
        start_time = time.time()
        last_state = None
        
        try:
            while time.time() - start_time < duration:
                current_state = self.ptt.is_pressed
                
                if current_state != last_state:
                    if current_state:
                        self.press_count += 1
                        if self.leds:
                            self.leds.set(Status.SPEAKING)
                    else:
                        self.release_count += 1
                        if self.leds:
                            self.leds.set(Status.IDLE)
                    
                    last_state = current_state
                
                time.sleep(0.01)
            
            elapsed = time.time() - start_time
            print(f"\n✅ Test abgeschlossen ({elapsed:.1f}s)")
            self._show_statistics()
            
        except KeyboardInterrupt:
            print("\n\nTest vorzeitig beendet.")
            self._show_statistics()
    
    def _show_statistics(self) -> None:
        """Zeige Test-Statistiken."""
        print("\n" + "="*60)
        print("STATISTIKEN")
        print("="*60)
        print(f"Anzahl Drücke:        {self.press_count}")
        print(f"Anzahl Loslassungen:  {self.release_count}")
        
        if self.press_count > 0:
            avg_duration = self.total_press_duration / self.press_count
            print(f"Durchschnittliche Dauer: {avg_duration:.3f}s")
            print(f"Gesamte Druck-Zeit:     {self.total_press_duration:.3f}s")
        
        if self.leds:
            self.leds.set(Status.IDLE)
        
        print("="*60)


def run_button_test():
    """Hauptfunktion für Taster-Test."""
    import sys
    
    # Parse Argumente
    test_mode = "basic"
    if len(sys.argv) > 1:
        test_mode = sys.argv[1].lower()
    
    # GPIO-Pin (kann überschrieben werden)
    gpio_pin = 17
    if len(sys.argv) > 2:
        try:
            gpio_pin = int(sys.argv[2])
        except ValueError:
            print(f"⚠️  Ungültiger GPIO-Pin: {sys.argv[2]}. Verwende Standard: GPIO17")
    
    print("="*60)
    print("TASTER-TESTPROGRAMM")
    print("="*60)
    print(f"GPIO-Pin: {gpio_pin} (Pin 11)")
    print(f"Test-Modus: {test_mode}")
    print("="*60)
    
    # Initialisiere Tester
    tester = ButtonTester(gpio_pin=gpio_pin)
    
    if not tester.init():
        print("\n❌ Initialisierung fehlgeschlagen. Beende Test.")
        sys.exit(1)
    
    # Führe Test aus
    try:
        if test_mode == "basic" or test_mode == "status":
            tester.test_basic()
        elif test_mode == "events" or test_mode == "callback":
            tester.test_events()
        elif test_mode == "wait":
            tester.test_wait_for_press()
        elif test_mode == "rapid":
            tester.test_rapid_press(duration=10.0)
        else:
            print(f"\n❌ Unbekannter Test-Modus: {test_mode}")
            print("\nVerfügbare Modi:")
            print("  basic   - Kontinuierliche Status-Anzeige (Standard)")
            print("  events  - Event-basierte Callbacks")
            print("  wait    - Blockierendes Warten auf Drücke")
            print("  rapid   - Schneller Stabilitätstest (10 Sekunden)")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ FEHLER während des Tests: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run_button_test()
