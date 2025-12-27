from __future__ import annotations
import time
from enum import Enum

try:
    from rpi_ws281x import PixelStrip, Color
except Exception:
    PixelStrip = None
    Color = None

class Status(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"

class NeoPixelStatus:
    def __init__(self, gpio_pin: int, count: int = 1, brightness: int = 40, enabled: bool = True):
        self.gpio_pin = gpio_pin
        self.count = count
        self.brightness = brightness
        self.enabled = enabled
        self.strip = None

    def start(self):
        if not self.enabled or PixelStrip is None:
            return
        try:
            self.strip = PixelStrip(self.count, self.gpio_pin, 800000, 10, False, self.brightness, 0)
            self.strip.begin()
            self.set(Status.IDLE)
        except Exception as e:
            self.strip = None
            print(f"[WARN] NeoPixel deaktiviert (Init fehlgeschlagen): {e}")

    def _set_all(self, color):
        if not self.strip:
            return
        for i in range(self.count):
            self.strip.setPixelColor(i, color)
        self.strip.show()

    def set(self, status: Status):
        if not self.strip or Color is None:
            return
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
        if not self.strip or Color is None:
            return
        for _ in range(times):
            self._set_all(Color(40, 0, 0))
            time.sleep(0.2)
            self._set_all(Color(0, 0, 0))
            time.sleep(0.2)
