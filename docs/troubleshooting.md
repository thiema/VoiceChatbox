# Troubleshooting

## Kein Ton bei der Ausgabe
- Prüfe `aplay -l` und ob dein DAC/Device erkannt wird
- Stelle in `.env` das gewünschte Output‑Device ein (oder nutze default)
- Teste mit `speaker-test`

## Mikrofon wird nicht erkannt
- Prüfe USB: `lsusb`
- Prüfe `arecord -l`
- Anderen USB‑Port probieren (Pi 5: bevorzugt USB‑A 3.0 Port)

## NeoPixel flackert / bleibt dunkel
- NeoPixel braucht oft 5V + Level‑Shift für DATA
- Gemeinsame Masse sicherstellen
- 330Ω in Serie zur Datenleitung + 1000µF Elko an 5V/GND nahe LED

## OpenAI Fehler (401/429)
- API‑Key prüfen
- Rate limits / Guthaben / Projekt‑Berechtigungen prüfen

## Programm endet mit „Speicherzugriffsfehler“ (Segmentation fault)
Das ist typischerweise ein nativer Treiber/Library-Crash (kein Python-Traceback), häufig ausgelöst durch **rpi_ws281x**
(NeoPixel/WS2812) auf Pi 5 / neuem Kernel / Debian-Varianten.

**Workaround (empfohlen):**
1) In `.env` NeoPixel deaktivieren:
```
USE_NEOPIXEL=false
```
2) In dieser Repo-Version wird `rpi_ws281x` nur noch **lazy** importiert, wenn NeoPixel aktiv ist.

Optional (wenn du NeoPixel später willst):
- Nutze einen **Level-Shifter** (74AHCT125) und saubere 5V Versorgung.
- Prüfe alternative Treiber (SPI-basierte WS2812-Interfaces) oder aktuelle Pi-5-kompatible Forks.
