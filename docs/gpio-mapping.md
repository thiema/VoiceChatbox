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
