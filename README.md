# 🧠 Voice AI Chatbox (Raspberry Pi 5)

Eine **standalone KI-Chatbox** für den Heimgebrauch auf Basis eines **Raspberry Pi 5**,  
mit **Spracheingabe**, **Sprachausgabe**, **Statusanzeige** und **Anbindung an Cloud-KI (z. B. ChatGPT)** –  
**ohne externen Monitor**.

---

## 📌 Projektziele

- Sprachbasierte Interaktion („Smart-Speaker-ähnlich“)
- Kein Display erforderlich (nur LEDs / optional OLED)
- Einfache Bedienung (Push-to-Talk / Wake-Word)
- Modulare, erweiterbare Architektur
- Fokus auf **Verständlichkeit, Stabilität, Bastelbarkeit**

---

## 🗂 Projektstruktur

```text
voice-ai-chatbox/
├── README.md
├── docs/
│   ├── wiring.md
│   ├── gpio-map.md
│   └── hardware.md
├── hardware/
│   ├── bom.md
│   └── enclosure.md
├── software/
│   ├── install.sh
│   ├── config.yaml
│   └── requirements.txt
├── src/
│   ├── main.py
│   ├── audio/
│   │   ├── stt.py
│   │   └── tts.py
│   ├── ai/
│   │   └── chat_backend.py
│   └── ui/
│       └── status_led.py
└── LICENSE

