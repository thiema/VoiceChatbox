from __future__ import annotations
from gpiozero import Button

class PushToTalk:
    """Push-to-talk button wired to GND with internal pull-up."""
    def __init__(self, gpio_pin: int):
        # pull_up=True means released -> 1, pressed -> 0 (to GND)
        self.button = Button(gpio_pin, pull_up=True, bounce_time=0.03)

    def wait_for_press(self):
        self.button.wait_for_press()

    def wait_for_release(self):
        self.button.wait_for_release()

    @property
    def is_pressed(self) -> bool:
        return self.button.is_pressed
