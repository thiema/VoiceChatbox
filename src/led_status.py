from __future__ import annotations
import time
from enum import Enum

try:
    from rpi_ws281x import PixelStrip, Color
except Exception:  # allows running on non-RPi
    PixelStrip = None
    Color = None

class Status(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"

class NeoPixelStatus:
    def __init__(self, gpio_pin: int, count: int = 1, brightness: int = 40):
        self.gpio_pin = gpio_pin
        self.count = count
        self.brightness = brightness
        self.strip = None

    def start(self):
        if PixelStrip is None:
            return
        # LED strip configuration:
        # freq_hz=800000, dma=10, invert=False, channel=0
        self.strip = PixelStrip(self.count, self.gpio_pin, 800000, 10, False, self.brightness, 0)
        self.strip.begin()
        self.set(Status.IDLE)

    def _set_all(self, color):
        if not self.strip:
            return
        for i in range(self.count):
            self.strip.setPixelColor(i, color)
        self.strip.show()

    def set(self, status: Status):
        if Color is None:
            return
        # Avoid specifying exact colors in docs—here we keep simple defaults.
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
        if Color is None:
            return
        for _ in range(times):
            self._set_all(Color(40, 0, 0))
            time.sleep(0.2)
            self._set_all(Color(0, 0, 0))
            time.sleep(0.2)
