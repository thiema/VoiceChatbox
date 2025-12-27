# GPIO Mapping (empfohlen) – 3 Status-LEDs + Push-to-Talk

Du nutzt einen **T‑Typ GPIO Adapter (40‑Pin)** auf ein Breakout/Breadboard (SYB‑46).
Hier ist ein Vorschlag, der mit **normalen LEDs** funktioniert (keine NeoPixel).

## Status-LEDs (3× LED)

- **ROT** = Fehler
- **GELB** = „Denken“ (STT/Chat läuft)
- **GRÜN** = „Sprechen“ / „Bereit“

### Pins (BCM / physisch)
- **ROT:** GPIO16 (Pin 36)
- **GELB:** GPIO20 (Pin 38)
- **GRÜN:** GPIO21 (Pin 40)

### Verdrahtung pro LED
- GPIO → **220Ω–330Ω Widerstand** → LED **Anode** (langes Bein)
- LED **Kathode** (kurzes Bein) → **GND-Schiene**

## Push-to-Talk Taster (Momentary NO)
- **GPIO:** GPIO17 (Pin 11)
- **GND:** Pin 9 (oder beliebiger GND)

Software nutzt **internen Pull-Up** → Taster nach GND schaltet.

## Breadboard Schienen (SYB-46)
- Obere blaue Schiene: **GND**
- Obere rote Schiene: **3.3V** (optional)

## Hinweis
- LEDs immer mit Widerstand betreiben.


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
