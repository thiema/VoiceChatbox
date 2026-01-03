# Software (Installation, Betrieb, Autostart)

## `.venv` – wo ist das?
`.venv/` wird **auf dem Raspberry Pi** erzeugt, wenn du `scripts/install.sh` ausführst. Es wird nicht mitgeliefert.

## Installation (auf dem Pi)
```bash
bash scripts/install.sh
```

## Konfiguration
```bash
cp .env.example .env
nano .env
```

## LED-Test (vor dem ersten echten Lauf)
```bash
source .venv/bin/activate
python -m src.main --test-leds
```

## Start (normal)
```bash
source .venv/bin/activate
python -m src.main
```

### Modus-Auswahl per Sprache (beim Start)
Nach dem Start fragt die Chatbox per Stimme:
- **Echo**
- **Chatbox**

Du hältst den Taster gedrückt und sagst das gewünschte Wort.

### Echo Modus
- Deine Sprache wird per STT erkannt.
- Die Box spricht den erkannten Text wieder aus (TTS).

### Chatbox Modus
- STT → LLM → TTS (normale Chat-Antwort)

### Optional: Modus per CLI erzwingen
```bash
python -m src.main --mode echo
python -m src.main --mode chatbox
```

## Push-to-Talk ohne echten Taster (Improvisation)
Siehe **docs/wiring.md** (Variante 1: improvisierter Kontakt).

## PTT-Test
```bash
python -m src.main --test-ptt
```

## OLED Test (SSD1306, 4-Pin I2C)
Auf vielen Breakout-Boards steht statt GPIO2/GPIO3 einfach **SDA1** und **SCL1** – das ist dasselbe:
- SDA1 = GPIO2 (Pin 3)
- SCL1 = GPIO3 (Pin 5)

Test:
```bash
source .venv/bin/activate
python -m src.main --test-oled
```

Adresse/Bus erzwingen (falls nötig):
```
OLED_I2C_BUS=1
OLED_I2C_ADDR=0x3C
```

### Wenn dein Display SH1106 ist
Falls auf dem OLED trotz erkannter Adresse (z. B. 0x3C) nichts erscheint, ist es sehr oft **SH1106**.

In `.env`:
```
OLED_DRIVER=sh1106
OLED_I2C_BUS=1
OLED_I2C_ADDR=0x3C
```
Dann:
```bash
python -m src.main --test-oled
```

#### OLED Größe/Rotation erzwingen (falls Display leer bleibt)
Viele 0.91" Displays sind **128x32**. Du kannst Größe/Rotation explizit setzen:

```
OLED_DRIVER=sh1106
OLED_I2C_BUS=1
OLED_I2C_ADDR=0x3C
OLED_WIDTH=128
OLED_HEIGHT=32
OLED_ROTATE=0   # oder 2
```

Dann:
```bash
python -m src.main --test-oled
```
