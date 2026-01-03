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
    width: int | None = None
    height: int | None = None
    rotate: int | None = None
    message: str = ""

def _try_init(bus: int, address: int, driver: Driver, width: int, height: int, rotate: int):
    from luma.core.interface.serial import i2c
    from luma.oled.device import ssd1306, sh1106
    serial = i2c(port=bus, address=address)
    if driver == "sh1106":
        return sh1106(serial, width=width, height=height, rotate=rotate)
    return ssd1306(serial, width=width, height=height, rotate=rotate)

def _draw_ok(device, title: str, subtitle: str):
    from luma.core.render import canvas
    with canvas(device) as draw:
        draw.text((0, 0), title)
        draw.text((0, 16), subtitle)

def probe_oled(
    buses: Iterable[int] = (1, 13, 14),
    addresses: Iterable[int] = (0x3C, 0x3D),
    drivers: Iterable[Driver] = ("sh1106", "ssd1306"),
    sizes: Iterable[tuple[int, int]] = ((128, 32), (128, 64)),
    rotates: Iterable[int] = (0, 2),
    verbose: bool = True,
) -> OledProbeResult:
    env_bus = os.getenv("OLED_I2C_BUS")
    env_addr = os.getenv("OLED_I2C_ADDR")
    env_drv = (os.getenv("OLED_DRIVER") or "").strip().lower()
    env_w = os.getenv("OLED_WIDTH")
    env_h = os.getenv("OLED_HEIGHT")
    env_rot = os.getenv("OLED_ROTATE")

    cand: list[tuple[int, int, Driver, int, int, int]] = []

    def add(b: int, a: int, d: Driver, w: int, h: int, r: int):
        t = (b, a, d, w, h, r)
        if t not in cand:
            cand.append(t)

    # env-first
    if env_bus:
        try:
            b = int(env_bus)
            addrs = [int(env_addr, 0)] if env_addr else list(addresses)
            if env_drv in ("sh1106", "ssd1306"):
                drvs: list[Driver] = [env_drv]  # type: ignore
            else:
                drvs = list(drivers)
            if env_w and env_h:
                szs = [(int(env_w), int(env_h))]
            else:
                szs = list(sizes)
            rots = [int(env_rot)] if env_rot else list(rotates)
            for a in addrs:
                for d in drvs:
                    for (w, h) in szs:
                        for r in rots:
                            add(b, a, d, w, h, r)
        except Exception:
            pass

    for b in buses:
        for a in addresses:
            for d in drivers:
                for (w, h) in sizes:
                    for r in rotates:
                        add(b, a, d, w, h, r)

    last_err = ""
    for b, a, d, w, h, r in cand:
        try:
            if verbose:
                print(f"[OLED] Try {d} bus={b} addr=0x{a:02X} size={w}x{h} rot={r}")
            dev = _try_init(b, a, d, w, h, r)
            _draw_ok(dev, "OLED OK", f"{d.upper()} {w}x{h} rot{r}")
            return OledProbeResult(True, b, a, d, w, h, r, "OLED initialisiert und Text angezeigt.")
        except Exception as e:
            last_err = f"{d} bus {b} addr 0x{a:02X} {w}x{h} rot{r}: {e}"

    return OledProbeResult(False, None, None, None, None, None, None, "OLED nicht gefunden. Letzter Fehler: " + last_err)

def i2c_raw_ping(bus: int, address: int) -> bool:
    try:
        from smbus2 import SMBus
        with SMBus(bus) as b:
            b.write_quick(address)
        return True
    except Exception:
        return False

def run_oled_test():
    res = probe_oled(verbose=True)
    print("OLED Test Ergebnis:")
    print(f"  ok={res.ok}")
    if res.ok:
        print(f"  driver={res.driver}  bus={res.bus}  addr=0x{res.address:02X}  size={res.width}x{res.height}  rot={res.rotate}")
        print("  -> Auf dem OLED sollte 'OLED OK' stehen.")
        return

    bus = int(os.getenv("OLED_I2C_BUS", "1"))
    addr = int(os.getenv("OLED_I2C_ADDR", "0x3C"), 0)
    print("")
    print("Extra Diagnose:")
    print(f"  i2c_raw_ping(bus={bus}, addr=0x{addr:02X}) = {i2c_raw_ping(bus, addr)}")
    print("")
    print("Empfohlener Fix für 0.91\" SH1106 128x32:")
    print("  In .env setzen:")
    print("    OLED_DRIVER=sh1106")
    print("    OLED_I2C_BUS=1")
    print("    OLED_I2C_ADDR=0x3C")
    print("    OLED_WIDTH=128")
    print("    OLED_HEIGHT=32")
    print("    OLED_ROTATE=0   (oder 2)")
