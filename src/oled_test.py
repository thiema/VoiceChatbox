from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable

@dataclass
class OledProbeResult:
    ok: bool
    bus: int | None = None
    address: int | None = None
    message: str = ""

def _try_init(bus: int, address: int):
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306
    serial = i2c(port=bus, address=address)
    return ssd1306(serial)

def _draw_ok(device, title: str, subtitle: str):
    from luma.core.render import canvas
    with canvas(device) as draw:
        draw.text((0, 0), title)
        draw.text((0, 16), subtitle)

def probe_oled(buses: Iterable[int] = (1, 13, 14), addresses: Iterable[int] = (0x3C, 0x3D)) -> OledProbeResult:
    env_bus = os.getenv("OLED_I2C_BUS")
    env_addr = os.getenv("OLED_I2C_ADDR")

    candidates: list[tuple[int, int]] = []
    if env_bus:
        try:
            b = int(env_bus)
            if env_addr:
                a = int(env_addr, 0)
                candidates.append((b, a))
            else:
                for a in addresses:
                    candidates.append((b, a))
        except ValueError:
            pass

    for b in buses:
        for a in addresses:
            if (b, a) not in candidates:
                candidates.append((b, a))

    last_err = ""
    for b, a in candidates:
        try:
            dev = _try_init(b, a)
            _draw_ok(dev, "OLED OK", f"I2C bus {b} addr 0x{a:02X}")
            return OledProbeResult(True, b, a, "OLED initialisiert und Text angezeigt.")
        except Exception as e:
            last_err = str(e)

    return OledProbeResult(False, None, None, "OLED nicht gefunden. Letzter Fehler: " + last_err)

def run_oled_test():
    res = probe_oled()
    print("OLED Test:")
    print(f"  ok={res.ok}")
    if res.ok:
        print(f"  bus={res.bus}  address=0x{res.address:02X}")
        print("  -> Auf dem OLED sollte 'OLED OK' stehen.")
    else:
        print("  -> Keine Antwort via I2C erkannt.")
        print("  Hinweise:")
        print("   - VCC an 3.3V (Pin 1) oder 5V (Pin 2/4) je nach Modul")
        print("   - GND an GND (z. B. Pin 6)")
        print("   - SDA1 (Pin 3) und SCL1 (Pin 5) sind korrekt (GPIO2/GPIO3)")
        print("   - I2C in raspi-config aktivieren, danach reboot")
        print("   - i2cdetect auf bus 1/13/14 probieren")
        print("   - Adresse 0x3D statt 0x3C möglich")
