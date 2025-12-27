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

## PTT reagiert nicht / löst zufällig aus
- Prüfe, dass ein Ende wirklich auf **GPIO17** steckt und das andere auf **GND**.
- Ohne Pull-up würde der Pin „floaten“ – hier ist Pull-up aktiv, daher sollte es stabil sein.
- Bei schlechtem Kontakt (Kabel nur leicht berührt) kann Prellen auftreten → halte den Kontakt sauber.
- Teste mit:
  ```bash
  python -m src.main --test-ptt
  ```
