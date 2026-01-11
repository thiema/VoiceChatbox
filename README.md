# Raspberry Pi KI-Chatbox (Sprachassistent)

DIY-Sprachassistent / KI-Chatbox auf Basis eines **Raspberry Pi 5 (8 GB)** mit **ReSpeaker XVF3800 4‑Mic Array (USB)**.
Das System arbeitet sprachbasiert (Sprache rein, Sprache raus) und nutzt Cloud‑KI‑Dienste (z. B. OpenAI/ChatGPT).
Ein externer Monitor ist nicht erforderlich.

> Dieses Repo ist bewusst **dokumentations‑ und praxisorientiert**: erst Hardware + Verdrahtung + Betrieb, dann Code.

---

## Features (Zielbild)

- Push‑to‑Talk per Taster (kein Wake‑Word nötig)
- Sprachaufnahme → Speech‑to‑Text (Cloud, z. B. Whisper via OpenAI)
- Chat‑Antwort (Cloud‑LLM, z. B. OpenAI Chat Completions)
- Sprachausgabe (TTS, Cloud – OpenAI TTS)
- Statusanzeige per **RGB‑LED (WS2812/NeoPixel)** und optional **OLED (I2C)**

---

## Projektstruktur

```
raspi-ai-chatbox-de/
├── README.md
├── requirements.txt
├── .env.example
├── src/
│   ├── main.py
│   ├── audio_io.py
│   ├── audio_test.py
│   ├── led_status.py
│   ├── gpio_inputs.py
│   └── config.py
├── docs/
│   ├── hardware.md
│   ├── wiring.md
│   ├── software.md
│   ├── gpio-mapping.md
│   └── troubleshooting.md
└── scripts/
    ├── install.sh
    └── chatbox.service
```

---

## Schnellstart (kurz)

1. **Raspberry Pi OS (64‑bit) installieren**
2. Repo klonen
3. Installation:
   ```bash
   cd raspi-ai-chatbox-de
   bash scripts/install.sh
   ```
4. Konfiguration:
   ```bash
   cp .env.example .env
   nano .env
   ```
5. Starten:
   ```bash
   source .venv/bin/activate
   python -m src.main
   ```

**Live-Spracherkennung mit Laufband-Anzeige:**
```bash
# Mit Whisper (OpenAI API, Standard)
python -m src.main --live-recognition

# Mit Vosk (lokal, offline)
python -m src.main --live-recognition --vosk
```

Siehe **docs/whisper-setup.md** für Whisper-Setup (OpenAI API).
Siehe **docs/vosk-setup.md** für Vosk-Setup (lokal, offline).

Für Autostart siehe **docs/software.md**.

---

## Dokumentation

- **docs/hardware.md** – Hardwareliste & Hinweise
- **docs/wiring.md** – Verdrahtungsübersicht
- **docs/gpio-mapping.md** – GPIO‑Belegung (Taster, LED, OLED)
- **docs/software.md** – Installation, Audio‑Setup, Autostart (systemd)
- **docs/audio-setup.md** – **Audio-Setup & Test-Anleitung** (Mikrofon & Lautsprecher)
- **docs/pcm5122-pinout.md** – **PCM5122 GPIO Pinout & Anschluss** (grafische Darstellung)
- **docs/whisper-setup.md** – **Whisper-Setup (OpenAI API)** – Spracherkennung mit Whisper
- **docs/vosk-setup.md** – **Vosk-Setup (lokal, offline)** – Lokale Spracherkennung
- **docs/troubleshooting.md** – typische Fehler & Lösungen

---

## Sicherheit / Betriebshinweise

- Verstärker **nicht** aus GPIO‑Pins speisen.
- Alle Module müssen eine **gemeinsame Masse (GND)** haben.
- Erst mit niedriger Lautstärke testen, Mikrofon & Lautsprecher räumlich trennen (Echo).

---

## Lizenz

MIT (kannst du bei Bedarf ergänzen).
