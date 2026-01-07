# Verdrahtung (Übersicht)

Für Pin-Details siehe **docs/gpio-mapping.md**.

## 1) Stromversorgung
- **Raspberry Pi 5:** USB‑C Netzteil (5V / 5A)
- **PCMS122 Audio Board:** Wird über GPIO-Pins versorgt (keine separate Versorgung nötig)
- **PAM8610 Verstärker:** **8–15 V DC** (empfohlen: 12 V), **separate Stromversorgung erforderlich**
  - **WICHTIG:** Verstärker **nicht** aus GPIO-Pins speisen!
  - **Gemeinsame Masse (GND)** mit Raspberry Pi verbinden

## 2) Audio

### 2.1 Mikrofon-Array
- **ReSpeaker XVF3800** → USB → Raspberry Pi

### 2.2 Audioausgabe

#### PCMS122 Audio Board
- **Aufstecken:** Direkt auf GPIO-Pins des Raspberry Pi (Pin 1 zu Pin 1)
- **Versorgung:** Über GPIO-Pins (keine separate Stromversorgung)
- **Audio-Ausgang:** Line-Out Links (L) und Rechts (R)

#### PAM8610 Verstärker
- **Stromversorgung:**
  - **VCC:** 8–15 V DC (empfohlen: 12 V) → Externe 12V-Quelle
  - **GND:** → Raspberry Pi GND (gemeinsame Masse)
  - **WICHTIG:** NICHT aus GPIO-Pins speisen!
- **Audio-Eingang:**
  - **L-In:** → PCMS122 Line-Out L
  - **R-In:** → PCMS122 Line-Out R
  - **GND:** → PCMS122 GND (gemeinsame Masse)
- **Audio-Ausgang:**
  - **L+ / L-:** → Lautsprecher Links
  - **R+ / R-:** → Lautsprecher Rechts

#### Lautsprecher (4× 4 Ω / 5 W)
- **Empfohlene Konfiguration:** 1 Box pro Kanal (4 Ω)
  - **Links:** 1 Box (4 Ω) an PAM8610 L+ / L-
  - **Rechts:** 1 Box (4 Ω) an PAM8610 R+ / R-
- **Alternative:** 2 Boxen pro Kanal in Reihe (8 Ω)
  - **Links:** 2 Boxen in Reihe (8 Ω) an PAM8610 L+ / L-
  - **Rechts:** 2 Boxen in Reihe (8 Ω) an PAM8610 R+ / R-
- **WICHTIG:** Polarität (+/-) beachten!

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

#### OLED Größe/Rotation erzwingen (falls Display leer bleibt)
Viele 0.91" Displays sind **128x32**. Du kannst Größe/Rotation explizit setzen:

```
OLED_DRIVER=sh1106
OLED_I2C_BUS=1
OLED_I2C_ADDR=0x3C
OLED_WIDTH=128
OLED_HEIGHT=32
OLED_ROTATE=0   # oder 2
```

Dann:
```bash
python -m src.main --test-oled
```

## OLED (finale Einstellung fuer dein Panel)
Dein 0.91" OLED ist faktisch **SH1106** und clippt am Rand. Darum nutzt das Projekt eine **Safe-Area**.

Empfohlene `.env` Werte:
```
OLED_DRIVER=sh1106
OLED_I2C_BUS=1
OLED_I2C_ADDR=0x3C
OLED_WIDTH=128
OLED_HEIGHT=32
OLED_FONT_SIZE=12
OLED_MARGIN_LEFT=4
OLED_MARGIN_TOP=3
OLED_MARGIN_RIGHT=4
OLED_MARGIN_BOTTOM=4
OLED_TEXT_DX=1
OLED_TEXT_DY=7
```

Test:
```bash
python -m src.main --test-oled
```

Im Normalbetrieb zeigt das OLED Status (wenn aktiv):
- Bereit
- Höre …
- Denke …
- Spreche …

## Umlaute auf dem OLED
Das Projekt nutzt eine TrueType-Schrift (DejaVuSans-Bold), die deutsche Umlaute unterstützt.
Wenn du statt „Höre …“ nur Kästchen siehst, prüfe:
- `OLED_FONT_PATH` zeigt auf eine TTF mit Umlaut-Support (Default ist ok)
- `OLED_FONT_SIZE=12` (zu große Fonts können abgeschnitten wirken)
