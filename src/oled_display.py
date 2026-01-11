# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from PIL import Image

from .utils_env import get_env_int, get_env_str

DEFAULT_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

@dataclass(frozen=True)
class OledConfig:
    driver: str
    i2c_bus: int
    i2c_addr: int
    width: int
    height: int
    font_path: str
    font_size: int
    margin_left: int
    margin_top: int
    margin_right: int
    margin_bottom: int
    text_dx: int
    text_dy: int

def load_oled_config() -> OledConfig:
    # Defaults tuned to user's tested SH1106 0.91" panel
    driver = get_env_str("OLED_DRIVER", "sh1106").lower()
    i2c_bus = get_env_int("OLED_I2C_BUS", 1)
    i2c_addr = int(os.getenv("OLED_I2C_ADDR", "0x3C"), 0)

    width = get_env_int("OLED_WIDTH", 128)
    height = get_env_int("OLED_HEIGHT", 32)

    font_path = get_env_str("OLED_FONT_PATH", DEFAULT_FONT_PATH)
    font_size = get_env_int("OLED_FONT_SIZE", 12)

    margin_left = get_env_int("OLED_MARGIN_LEFT", 4)
    margin_top = get_env_int("OLED_MARGIN_TOP", 3)
    margin_right = get_env_int("OLED_MARGIN_RIGHT", 4)
    margin_bottom = get_env_int("OLED_MARGIN_BOTTOM", 4)

    text_dx = get_env_int("OLED_TEXT_DX", 1)
    text_dy = get_env_int("OLED_TEXT_DY", 7)

    return OledConfig(
        driver=driver,
        i2c_bus=i2c_bus,
        i2c_addr=i2c_addr,
        width=width,
        height=height,
        font_path=font_path,
        font_size=font_size,
        margin_left=margin_left,
        margin_top=margin_top,
        margin_right=margin_right,
        margin_bottom=margin_bottom,
        text_dx=text_dx,
        text_dy=text_dy,
    )

class OledDisplay:
    """OLED wrapper (SH1106/SSD1306) with safe-area drawing."""

    def __init__(self, cfg: Optional[OledConfig] = None) -> None:
        self.cfg = cfg or load_oled_config()
        self.device = None
        self.font = None

    def init(self) -> bool:
        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import sh1106, ssd1306
            from PIL import ImageFont

            serial = i2c(port=self.cfg.i2c_bus, address=self.cfg.i2c_addr)
            if self.cfg.driver == "sh1106":
                self.device = sh1106(serial, width=self.cfg.width, height=self.cfg.height)
            else:
                self.device = ssd1306(serial, width=self.cfg.width, height=self.cfg.height)

            self.font = ImageFont.truetype(self.cfg.font_path, self.cfg.font_size)
            self.clear()
            return True
        except Exception:
            self.device = None
            self.font = None
            return False

    def _bounds(self):
        assert self.device is not None
        left = self.cfg.margin_left
        top = self.cfg.margin_top
        right = self.device.width - 1 - self.cfg.margin_right
        bottom = self.device.height - 1 - self.cfg.margin_bottom
        return left, top, right, bottom

    def clear(self) -> None:
        if not self.device:
            return
        from luma.core.render import canvas
        with canvas(self.device) as draw:
            draw.rectangle(self.device.bounding_box, outline="black", fill="black")

    def show_box_and_text(self, text: str) -> None:
        if not self.device or not self.font:
            return
        from luma.core.render import canvas
        left, top, right, bottom = self._bounds()
        text_x = left + self.cfg.text_dx
        text_y = top + self.cfg.text_dy

        with canvas(self.device) as draw:
            draw.rectangle(self.device.bounding_box, outline="black", fill="black")
            draw.rectangle((left, top, right, bottom), outline="white", fill="black")
            draw.text((text_x, text_y), text, font=self.font, fill="white")

    def show_ready(self) -> None:
        self.show_box_and_text("Bereit")

    def show_listening(self) -> None:
        self.show_box_and_text("Höre …")

    def show_thinking(self) -> None:
        self.show_box_and_text("Denke …")

    def show_speaking(self) -> None:
        self.show_box_and_text("Spreche …")

    def show_mode_prompt(self) -> None:
        self.show_box_and_text("Echo/Chatbox?")
    
    def show_scrolling_text(self, text: str, scroll_speed: int = 2) -> None:
        """
        Zeige Text als Laufband (scrollend) auf dem Display.
        
        Args:
            text: Der anzuzeigende Text
            scroll_speed: Pixel pro Update (Standard: 2)
        """
        if not self.device or not self.font:
            return
        
        from luma.core.render import canvas
        from PIL import Image, ImageDraw, ImageFont
        
        left, top, right, bottom = self._bounds()
        text_area_width = right - left + 1
        text_area_height = bottom - top + 1
        
        # Erstelle temporäres Image für Text-Messung
        temp_img = Image.new("1", (text_area_width * 2, text_area_height))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Messe Text-Breite
        bbox = temp_draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        
        # Wenn Text kürzer als Display, einfach anzeigen
        if text_width <= text_area_width:
            self.show_box_and_text(text)
            return
        
        # Erstelle vollständiges Text-Image
        full_text_img = Image.new("1", (text_width + text_area_width, text_area_height), 0)
        full_text_draw = ImageDraw.Draw(full_text_img)
        full_text_draw.text((0, 0), text, font=self.font, fill=1)
        
        # Scrolle durch den Text
        scroll_positions = list(range(0, text_width + text_area_width, scroll_speed))
        
        # Zeige nur die aktuelle Position (kein kontinuierliches Scrolling in dieser Funktion)
        # Für Live-Updates wird die Funktion mehrfach aufgerufen
        current_pos = max(0, len(scroll_positions) - 1)
        if current_pos < len(scroll_positions):
            x_offset = scroll_positions[current_pos]
            cropped = full_text_img.crop((x_offset, 0, x_offset + text_area_width, text_area_height))
            
            with canvas(self.device) as draw:
                draw.rectangle(self.device.bounding_box, outline="black", fill="black")
                draw.rectangle((left, top, right, bottom), outline="white", fill="black")
                # Zeige den aktuellen Ausschnitt
                self.device.display(cropped)
    
    def show_text_scroll(self, text: str) -> None:
        """
        Zeige Text mit automatischem Scrolling (vereinfachte Version).
        Wenn Text zu lang ist, wird er abgeschnitten mit "..." am Ende.
        Für Live-Spracherkennung: zeigt den neuesten Text-Abschnitt.
        """
        if not self.device or not self.font:
            return
        
        from luma.core.render import canvas
        from PIL import ImageDraw
        
        left, top, right, bottom = self._bounds()
        text_area_width = right - left + 1
        text_x = left + self.cfg.text_dx
        text_y = top + self.cfg.text_dy
        
        # Erstelle temporäres Image für Text-Messung
        temp_img = Image.new("1", (text_area_width * 2, bottom - top + 1))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Messe Text-Breite
        bbox = temp_draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        
        # Wenn Text passt, einfach anzeigen
        if text_width <= text_area_width - self.cfg.text_dx * 2:
            self.show_box_and_text(text)
            return
        
        # Text kürzen: Zeige die letzten Zeichen, die auf das Display passen
        # Für Laufband: Zeige den neuesten Teil des Textes
        max_chars = int((text_area_width - self.cfg.text_dx * 2) / (self.cfg.font_size * 0.6))
        if len(text) > max_chars:
            # Zeige die letzten max_chars Zeichen
            display_text = "..." + text[-(max_chars - 3):]
        else:
            display_text = text
        
        self.show_box_and_text(display_text)