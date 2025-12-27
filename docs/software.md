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
