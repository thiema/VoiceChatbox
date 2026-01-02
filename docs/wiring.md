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


## Push-to-Talk ohne echten Taster (Variante 1: improvisierter Kontakt)

Wenn du keinen Taster hast, kannst du den Push-to-Talk **provisorisch** als "Kontakt" bauen:

### Was du brauchst
- 2× Dupont-Kabel (Male/Female je nach Breakout/Breadboard)
- optional: Krokodilklemmen oder eine Büroklammer als „Brücke“

### So geht’s (empfohlen)
1) Stecke ein Kabel auf **GPIO17** (Pin 11) am Breakout/Breadboard.
2) Stecke ein zweites Kabel auf **GND** (Pin 9 oder irgendein GND-Pin).
3) **PTT auslösen:** Berühre die freien Enden der beiden Kabel kurz **miteinander** (oder verbinde sie mit einer Büroklammer).
   - Verbunden = „Taste gedrückt“
   - Getrennt = „Taste losgelassen“

### Wichtig
- Im Code ist `pull_up=True` aktiv → der GPIO ist im Ruhezustand HIGH und wird beim Kontakt nach GND LOW.
- Achte darauf, **nur GPIO17 mit GND** zu verbinden – nicht mit 5V/3.3V kurzschließen.
- Für stabileren Kontakt: Kleb die Kabelenden auf ein Stück Karton und nutze eine Büroklammer als Schalter.

### Test
Nutze den PTT-Testmodus:
```bash
source .venv/bin/activate
python -m src.main --test-ptt
```
Dann siehst du in der Konsole „PRESSED/RELEASED“ und die grüne LED signalisiert den Druck.

## OLED (0.91" / SSD1306, 4 Pins) anschließen
- **VCC** → 3.3V (Pin 1) *(empfohlen)*
- **GND** → GND (z. B. Pin 6)
- **SDA** → **SDA1** (Pin 3 / GPIO2)
- **SCL** → **SCL1** (Pin 5 / GPIO3)

I2C Scan:
```bash
sudo i2cdetect -y 1
```
Typische Adressen: **0x3C** oder **0x3D**.

Falls leer:
- auch `sudo i2cdetect -y 13` und `sudo i2cdetect -y 14` probieren
- I2C in `raspi-config` aktivieren + reboot

### Treiber-Hinweis (wichtig!)
Viele 0.91" OLEDs sind **SH1106**, selbst wenn „SSD1306“ auf dem PCB steht.
Wenn `--test-oled` nichts zeigt, setze in `.env`:

```
OLED_DRIVER=sh1106
OLED_I2C_BUS=1
OLED_I2C_ADDR=0x3C
```

Dann:
```bash
python -m src.main --test-oled
```
