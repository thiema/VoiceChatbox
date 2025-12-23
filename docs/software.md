# Software (Installation, Betrieb, Autostart)

## Ziel

- Raspberry Pi OS (64‑bit)
- Python 3.11+
- Audio: USB‑Mic (XVF3800) + USB‑DAC oder I2S‑DAC
- Cloud: OpenAI API (STT, Chat, TTS)

---

## 1) Installation (automatisch)

Im Projekt liegt ein Install-Skript:

```bash
cd raspi-ai-chatbox-de
bash scripts/install.sh
```

Was das Skript macht:
- Systempakete installieren (Audio/Build‑Tools)
- Python venv anlegen
- Requirements installieren
- Beispiel‑.env erzeugen (falls nicht vorhanden)
- Optional: systemd Service installieren

---

## 2) OpenAI API Key konfigurieren

```bash
cp .env.example .env
nano .env
```

Setze mindestens:
- `OPENAI_API_KEY=...`

Optional:
- `OPENAI_MODEL_CHAT=...`
- `OPENAI_MODEL_STT=...`
- `OPENAI_MODEL_TTS=...`

---

## 3) Audio-Geräte prüfen

Liste Geräte:
```bash
arecord -l
aplay -l
```

Teste Mic:
```bash
arecord -D default -f S16_LE -r 16000 -c1 test.wav -d 3
```

Teste Ausgabe:
```bash
speaker-test -t wav
```

---

## 4) Starten (manuell)

```bash
source .venv/bin/activate
python -m src.main
```

---

## 5) Autostart (systemd)

Installieren (vom Script erledigbar):
```bash
sudo cp scripts/chatbox.service /etc/systemd/system/chatbox.service
sudo systemctl daemon-reload
sudo systemctl enable --now chatbox.service
```

Logs:
```bash
journalctl -u chatbox.service -f
```

---

## 6) Bedienung

- **Taster gedrückt halten** → Aufnahme läuft
- **Taster loslassen** → Upload STT → Chat → TTS → Ausgabe
- Status wird per LED/OLED angezeigt

---

## 7) Hinweise

- Für bestes Ergebnis: Lautsprecher nicht direkt neben das Mic‑Array.
- Beginne mit niedriger Lautstärke.
