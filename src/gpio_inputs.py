from __future__ import annotations
import os
from gpiozero import Button, Device

def _configure_pin_factory():
    factory = os.getenv("GPIOZERO_PIN_FACTORY")
    if not factory:
        return
    factory = factory.strip().lower()
    if factory == "lgpio":
        from gpiozero.pins.lgpio import LGPIOFactory
        Device.pin_factory = LGPIOFactory()
    elif factory in ("rpigpio", "rpi"):
        from gpiozero.pins.rpigpio import RPiGPIOFactory
        Device.pin_factory = RPiGPIOFactory()
    elif factory == "pigpio":
        from gpiozero.pins.pigpio import PiGPIOFactory
        Device.pin_factory = PiGPIOFactory()

class PushToTalk:
    """Push-to-talk button wired to GND with internal pull-up."""
    def __init__(self, gpio_pin: int):
        _configure_pin_factory()
        self.button = Button(gpio_pin, pull_up=True, bounce_time=0.03)

    def wait_for_press(self):
        self.button.wait_for_press()

    @property
    def is_pressed(self) -> bool:
        return self.button.is_pressed
