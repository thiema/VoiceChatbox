# GPIO Mapping (Vorschlag)

> Du kannst die Pins natürlich ändern. Wichtig ist: konsistent bleiben.

## Raspberry Pi 40‑Pin Header – verwendete Signale

### Status-LED (WS2812B / NeoPixel)
- **DATA:** GPIO18 (Pin 12)  *(PWM‑fähig, häufig genutzt)*
- **5V:** Pin 2 oder 4
- **GND:** Pin 6

> Empfehlung: Datenleitung über **Level Shifter** (z. B. 74AHCT125) oder zumindest 330Ω in Serie.
> Zusätzlich: 1000µF Elko zwischen 5V/GND nahe am NeoPixel.

### Push-to-Talk Taster (Momentary NO)
- **GPIO:** GPIO17 (Pin 11)
- **GND:** Pin 9
- Software nutzt **internen Pull‑Up** → Taster nach GND schaltet.

### OLED Display (SSD1306, I2C)
- **SDA:** GPIO2 / SDA1 (Pin 3)
- **SCL:** GPIO3 / SCL1 (Pin 5)
- **VCC:** 3.3V (Pin 1)  *(meist ausreichend; manche Module können 5V – 3.3V bevorzugt)*
- **GND:** Pin 6

## Hinweis zu 5V vs 3.3V

- GPIO‑Logik ist **3.3V**.
- NeoPixel läuft meist besser mit **5V** Versorgung; Datenlevel‑Shift empfohlen.
