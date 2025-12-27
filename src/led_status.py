from __future__ import annotations
from enum import Enum
from gpiozero import LED

class Status(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"

class LedStatus:
    """3-LED Statusanzeige (Rot/Gelb/Grün)."""

    def __init__(self, gpio_red: int, gpio_yellow: int, gpio_green: int, enabled: bool = True):
        self.enabled = enabled
        self.red = LED(gpio_red) if enabled else None
        self.yellow = LED(gpio_yellow) if enabled else None
        self.green = LED(gpio_green) if enabled else None
        self.set(Status.IDLE)

    def all_off(self):
        if not self.enabled:
            return
        self.red.off(); self.yellow.off(); self.green.off()

    def set(self, status: Status):
        if not self.enabled:
            return
        self.all_off()
        if status == Status.IDLE:
            return
        if status == Status.LISTENING:
            self.green.on()
        elif status == Status.THINKING:
            self.yellow.on()
        elif status == Status.SPEAKING:
            self.green.on()
        elif status == Status.ERROR:
            self.red.on()

    def blink_error(self, times: int = 3, on_time: float = 0.2, off_time: float = 0.2):
        if not self.enabled:
            return
        from time import sleep
        for _ in range(times):
            self.red.on(); sleep(on_time)
            self.red.off(); sleep(off_time)
