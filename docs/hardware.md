# Hardware-Dokumentation

## Zentrale Komponenten

- **Raspberry Pi 5 (8 GB RAM)**
- **Netzteil:** USB‑C, 5V / 5A (offiziell empfohlen)
- **Mikrofon-Array:** ReSpeaker **XMOS XVF3800** (USB, 4‑Mic, DSP)

## Audioausgabe (verwendete Komponenten)

### Soundkarte (DAC)
- **PCMS122 Audio Board** (I2S-DAC HAT)
  - Wird direkt auf die GPIO-Pins des Raspberry Pi aufgesteckt
  - Bietet hochwertige Audio-Ausgabe über I2S-Interface
  - Keine USB-Verbindung nötig

### Verstärker
- **PAM8610** Class-D Stereo-Audio-Verstärker
  - **Leistung:** 10 W pro Kanal (20 W gesamt)
  - **Versorgung:** 8–15 V DC (empfohlen: 12 V)
  - **WICHTIG:** Verstärker **nicht** aus GPIO-Pins speisen!
  - Separate Stromversorgung erforderlich

### Lautsprecher
- **4× Lautsprecherboxen**
  - **Impedanz:** 4 Ω pro Box
  - **Leistung:** 5 W pro Box
  - **Anschluss:** Stereo (2×2 Boxen)
  - **Polarität beachten:** + und - korrekt anschließen

## Breadboard & Kabel

- **SYB‑46** Breadboard (vorhanden)
- **Dupont Jumper Set** (M/M, M/F, F/F)
- **Lautsprecherkabel** (0.5–0.75 mm² empfohlen)
- Optional: **JST‑Kabel** (siehe docs/wiring.md)

## Optionale UI

- **WS2812B NeoPixel** (1× LED oder kleiner Ring) – Status
- **OLED SSD1306** (I2C, 0.96" oder 1.3") – Status/Text
- **Taster** (Momentary NO) – Push‑to‑Talk
