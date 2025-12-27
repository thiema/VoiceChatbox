# Troubleshooting

## LED geht nicht
- LED-Pinout prüfen: langes Bein (Anode) Richtung GPIO/Widerstand, kurzes Bein (Kathode) Richtung GND.
- Widerstand 220–330Ω in Serie.
- Pins: Rot=GPIO16, Gelb=GPIO20, Grün=GPIO21.
- Test:
  ```bash
  python -m src.main --test-leds
  ```

## GPIO funktioniert nicht
- Prüfe Gruppen: `groups` → `gpio` sollte enthalten sein.
- In `.env` setzen:
  `GPIOZERO_PIN_FACTORY=lgpio`
- Requirements neu installieren:
  ```bash
  pip install -r requirements.txt
  ```
