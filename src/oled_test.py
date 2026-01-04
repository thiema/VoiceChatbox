from __future__ import annotations

from .oled_display import OledDisplay, load_oled_config

def run_oled_test() -> None:
    cfg = load_oled_config()
    oled = OledDisplay(cfg)
    ok = oled.init()

    print("OLED Test:")
    print(f"  ok={ok}")
    print(f"  driver={cfg.driver} bus={cfg.i2c_bus} addr=0x{cfg.i2c_addr:02X} size={cfg.width}x{cfg.height}")
    print(f"  margins L{cfg.margin_left} T{cfg.margin_top} R{cfg.margin_right} B{cfg.margin_bottom}")
    print(f"  font={cfg.font_path} size={cfg.font_size} text_dx={cfg.text_dx} text_dy={cfg.text_dy}")

    if not ok:
        print("  -> OLED init fehlgeschlagen. Prüfe: i2cdetect -y 1 (0x3C).")
        return

    oled.show_box_and_text("Höre …")
    print("  -> Auf dem OLED sollte ein Innenrahmen + 'SH1106 OK' sichtbar sein.")
