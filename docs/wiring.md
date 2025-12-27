# Verdrahtung (Übersicht)

Für Pin-Details siehe **docs/gpio-mapping.md**.

## 1) Stromversorgung
- Raspberry Pi 5: USB‑C Netzteil
- Verstärker (z. B. PAM8403): 5V Versorgung (idealerweise separate 5V-Quelle), **gemeinsame Masse** mit Pi

## 2) Audio
- Mikrofon-Array (XVF3800) → USB → Raspberry Pi
- Raspberry Pi → USB-DAC (oder I2S-DAC) → Verstärker → Lautsprecher

## 3) GPIO / Breakout / Breadboard
Du nutzt einen **T‑Typ GPIO Adapter**.

### Schienen
- Pi‑GND → GND-Schiene (blau)

### 3× Status-LEDs
Pro LED:
- GPIO → 330Ω → LED Anode
- LED Kathode → GND

Pins: Rot=GPIO16, Gelb=GPIO20, Grün=GPIO21.

### Push-to-Talk Taster
GPIO17 → Taster → GND (Pull-Up intern)

## 4) JST-Kabel
JST nur nötig, wenn ein Modul JST-Stecker hat. Für LEDs/Taster auf Breadboard: keine JST nötig.
