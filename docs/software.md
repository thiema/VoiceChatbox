# Software (Installation, Betrieb, Autostart)

## Wichtige Klarstellung: Wo entsteht `.venv`?

- Das Verzeichnis **`.venv/` wird nicht mitgeliefert** und gehört typischerweise **nicht** ins Git-Repo.
- `.venv/` entsteht **auf dem Zielsystem (deinem Raspberry Pi / deiner Chatbox)**, sobald du `scripts/install.sh` ausführst.

Warum? Eine virtuelle Umgebung enthält binäre Pakete und Pfade, die vom System abhängen (CPU/OS/Python-Version).

---

## Empfohlene Basis

**Empfehlung:** Raspberry Pi OS (64-bit) für Pi 5.  
Auf generischem Debian (z. B. Debian 13 „trixie“) kann GPIO/NeoPixel deutlich mehr Handarbeit erfordern.

---

## 1) Installation (auf dem Zielsystem)

Auf dem Raspberry Pi:

```bash
cd raspi-ai-chatbox-de
bash scripts/install.sh
```

Das Skript legt **`.venv/`** an und installiert alle Python-Abhängigkeiten.

---

## 2) OpenAI API Key konfigurieren

```bash
cp .env.example .env
nano .env
```

Setze mindestens:
- `OPENAI_API_KEY=...`

---

## 3) Starten (manuell)

```bash
source .venv/bin/activate
python -m src.main
```

---

## 4) GPIO/NeoPixel bei Problemen deaktivieren

Wenn du auf einem Nicht-Pi testest oder GPIO noch nicht eingerichtet ist:

```
USE_GPIO=false
```

Wenn NeoPixel Probleme macht:

```
USE_NEOPIXEL=false
```

---

## 5) Autostart (systemd)

```bash
sudo cp scripts/chatbox.service /etc/systemd/system/chatbox.service
sudo systemctl daemon-reload
sudo systemctl enable --now chatbox.service
journalctl -u chatbox.service -f
```
