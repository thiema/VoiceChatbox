from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Literal

Driver = Literal["sh1106", "ssd1306"]

@dataclass
class OledProbeResult:
    ok: bool
    bus: int | None = None
    address: int | None = None
    driver: Driver | None = None
    message: str = ""

def _try_init(bus: int, address: int, driver: Driver):
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306, sh1106
    serial = i2c(port=bus, address=address)
    return sh1106(serial) if driver == "sh1106" else ssd1306(serial)

def _draw_ok(device, title: str, subtitle: str):
    from luma.core.render import canvas
    with canvas(device) as draw:
        draw.text((0, 0), title)
        draw.text((0, 16), subtitle)

def probe_oled(
    buses: Iterable[int] = (1, 13, 14),
    addresses: Iterable[int] = (0x3C, 0x3D),
    drivers: Iterable[Driver] = ("sh1106", "ssd1306"),
) -> OledProbeResult:
    """Probiere Bus/Adresse/Driver.

    Viele 0.91" OLEDs sind **SH1106**, auch wenn auf dem Board 'SSD1306' steht.
    """
    env_bus = os.getenv("OLED_I2C_BUS")
    env_addr = os.getenv("OLED_I2C_ADDR")
    env_drv = (os.getenv("OLED_DRIVER") or "").strip().lower()

    cand: list[tuple[int, int, Driver]] = []

    def add(b: int, a: int, d: Driver):
        t = (b, a, d)
        if t not in cand:
            cand.append(t)

    # env-first
    if env_bus:
        try:
            b = int(env_bus)
            addrs = [int(env_addr, 0)] if env_addr else list(addresses)
            drvs: list[Driver] = [env_drv] if env_drv in ("sh1106", "ssd1306") else list(drivers)  # type: ignore
            for a in addrs:
                for d in drvs:
                    add(b, a, d)
        except Exception:
            pass

    for b in buses:
        for a in addresses:
            for d in drivers:
                add(b, a, d)

    last_err = ""
    for b, a, d in cand:
        try:
            dev = _try_init(b, a, d)
            _draw_ok(dev, "OLED OK", f"{d.upper()} bus {b} addr 0x{a:02X}")
            return OledProbeResult(True, b, a, d, "OLED initialisiert und Text angezeigt.")
        except Exception as e:
            last_err = f"{d} bus {b} addr 0x{a:02X}: {e}"

    return OledProbeResult(False, None, None, None, "OLED nicht gefunden. Letzter Fehler: " + last_err)

def run_oled_test():
    res = probe_oled()
    print("OLED Test:")
    print(f"  ok={res.ok}")
    if res.ok:
        print(f"  driver={res.driver}  bus={res.bus}  address=0x{res.address:02X}")
        print("  -> Auf dem OLED sollte 'OLED OK' stehen.")
    else:
        print("  -> Keine Ausgabe möglich.")
        print("  Hinweise:")
        print("   - VCC an 3.3V (Pin 1) (empfohlen)")
        print("   - GND an GND (z. B. Pin 6)")
        print("   - SDA1 (Pin 3) und SCL1 (Pin 5)")
        print("   - i2cdetect -y 1 sollte typischerweise 0x3C zeigen")
        print("   - Viele Displays sind SH1106 -> setze OLED_DRIVER=sh1106")
