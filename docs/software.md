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
