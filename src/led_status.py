from __future__ import annotations
import time
from enum import Enum

class Status(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"

class NeoPixelStatus:
    """NeoPixel Status LED (WS2812).

    Hinweis:
    - `rpi_ws281x` kann auf Pi 5 / neuem Kernel / Debian-Varianten *nicht unterstützt* sein
      und sogar beim Programmende segfaulten.
    - Darum importieren wir `rpi_ws281x` **lazy** erst, wenn NeoPixel wirklich aktiviert ist.
    """

    def __init__(self, gpio_pin: int, count: int = 1, brightness: int = 40, enabled: bool = True):
        self.gpio_pin = gpio_pin
        self.count = count
        self.brightness = brightness
        self.enabled = enabled
        self.strip = None
        self._Color = None

    def start(self):
        if not self.enabled:
            return

        try:
            from rpi_ws281x import PixelStrip, Color  # type: ignore
            self._Color = Color
        except Exception as e:
            print(f"[WARN] NeoPixel deaktiviert (Import fehlgeschlagen): {e}")
            self.enabled = False
            return

        try:
            self.strip = PixelStrip(self.count, self.gpio_pin, 800000, 10, False, self.brightness, 0)
            self.strip.begin()
            self.set(Status.IDLE)
        except Exception as e:
            self.strip = None
            print(f"[WARN] NeoPixel deaktiviert (Init fehlgeschlagen): {e}")
            self.enabled = False

    def _set_all(self, color):
        if not self.strip:
            return
        for i in range(self.count):
            self.strip.setPixelColor(i, color)
        self.strip.show()

    def set(self, status: Status):
        if not self.strip or self._Color is None:
            return

        Color = self._Color
        if status == Status.IDLE:
            self._set_all(Color(0, 0, 0))
        elif status == Status.LISTENING:
            self._set_all(Color(0, 0, 40))
        elif status == Status.THINKING:
            self._set_all(Color(40, 20, 0))
        elif status == Status.SPEAKING:
            self._set_all(Color(0, 40, 0))
        elif status == Status.ERROR:
            self._set_all(Color(40, 0, 0))

    def blink_error(self, times: int = 3):
        if not self.strip or self._Color is None:
            return
        Color = self._Color
        for _ in range(times):
            self._set_all(Color(40, 0, 0))
            time.sleep(0.2)
            self._set_all(Color(0, 0, 0))
            time.sleep(0.2)
