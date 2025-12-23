# Hardware-Dokumentation

## Zentrale Komponenten

- **Raspberry Pi 5 (8 GB RAM)**
- **Netzteil:** USB‑C, 5V / 5A (offiziell empfohlen)
- **Mikrofon-Array:** ReSpeaker **XMOS XVF3800** (USB, 4‑Mic, DSP)
- **Audioausgabe** (eine der Optionen):
  - **Option A (einfach & gut):** USB‑DAC (oder I2S‑DAC) + kleiner Class‑D Verstärker + passiver Lautsprecher
  - **Option B (einfachster Aufbau):** aktive USB/3.5mm Lautsprecher (kein Verstärker nötig)

## Empfehlung: Audio (passiv)

### DAC
- **USB‑DAC** (Plug&Play) *oder* **I2S‑DAC HAT (PCM5122/PCM5102)**

### Verstärker
- **PAM8403** (5V, 2×3W) – reicht für Sprach‑TTS in Wohnräumen

### Lautsprecher
- **2"–3" Full‑Range**, z. B. Visaton FRS‑5 (8Ω) oder vergleichbar
- Alternativ: 4Ω Mini‑Speaker (benötigt passende Amp‑Auslegung, tendenziell mehr Strom)

## Breadboard & Kabel

- **SYB‑46** Breadboard (vorhanden)
- **Dupont Jumper Set** (M/M, M/F, F/F)
- **Lautsprecherkabel** (0.5–0.75 mm² empfohlen)
- Optional: **JST‑Kabel** (siehe docs/wiring.md)

## Optionale UI

- **WS2812B NeoPixel** (1× LED oder kleiner Ring) – Status
- **OLED SSD1306** (I2C, 0.96" oder 1.3") – Status/Text
- **Taster** (Momentary NO) – Push‑to‑Talk
