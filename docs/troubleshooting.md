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
