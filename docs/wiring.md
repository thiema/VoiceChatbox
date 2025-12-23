# Verdrahtung (Übersicht)

Diese Datei beschreibt die Verdrahtung **konzeptionell**. Für Pin‑Details siehe **gpio-mapping.md**.

## 1) Stromversorgung

- Raspberry Pi 5: über USB‑C Netzteil
- Verstärker:
  - bei PAM8403: **5V** Versorgung (idealerweise separate 5V‑Quelle 2–3A bei hoher Lautstärke)
  - GND muss mit Pi‑GND verbunden sein (**gemeinsame Masse**)

## 2) Audio

### Mikrofon
- XVF3800 → per **USB** an Raspberry Pi

### Lautsprecher-Ausgabe (Empfehlung)
- Raspberry Pi → **USB‑DAC** (oder I2S‑DAC) → Line‑Out → Verstärker (PAM8403) → Lautsprecher

Alternative (sehr einfach):
- Raspberry Pi → **aktive Lautsprecher** (USB oder 3.5mm vom DAC)

## 3) GPIO / Breadboard (SYB‑46)

Du hast ein SYB‑46 mit:
- je einer X‑ und Y‑Schiene oben/unten
- 5 Reihenblöcke A‑E und F‑J

**Vorschlag:**
- Nutze die obere rote Schiene als +3.3V (oder +5V wenn nötig)
- Nutze die obere blaue Schiene als GND
- Spiegel das unten ggf. (z. B. für Amp‑GND / LED‑GND)

### Typische Verbindungen
- Pi GND → GND‑Schiene
- Pi 3.3V → +3.3V‑Schiene (für OLED, Taster Pull‑up, Logik)
- NeoPixel:
  - Datenpin → GPIO
  - VCC → 5V (NeoPixel bevorzugt 5V)
  - GND → GND
  - **Level‑Shift empfohlen** (3.3V → 5V) für zuverlässige NeoPixel‑Daten

## 4) JST‑Kabel – wann brauchst du sie?

Das hängt vom jeweiligen Modul ab:

- **NeoPixel/LED‑Strips** haben oft **JST‑SM 3‑Pin**
- Manche Verstärker‑Boards nutzen **JST‑PH/XH 2‑Pin** für Strom oder Speaker

Wenn deine Module **nur Schraubklemmen** oder **Dupont‑Header** haben, brauchst du keine JST‑Kabel.

Empfehlung: Lege dir bereit:
- **JST‑SM 3‑Pin (female/male)** für NeoPixel‑Module/Strips
- **JST‑PH 2‑Pin** oder **JST‑XH 2‑Pin** (je nach Board) für kleine Stromverbindungen
