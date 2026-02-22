# Whisper Sprachmodell Setup (OpenAI API, Cloud) + whisper.cpp (lokal)

Diese Anleitung erklärt, wie du OpenAI Whisper für die Spracherkennung einrichtest und konfigurierst.

---

## Was ist Whisper?

**Whisper** ist ein hochmodernes Spracherkennungssystem von OpenAI, das über die OpenAI API verfügbar ist.
- ✅ **Sehr hohe Genauigkeit** (besonders für Deutsch)
- ✅ **Unterstützt viele Sprachen** automatisch
- ✅ **Robust gegen Hintergrundgeräusche**
- ⚠️ **Internet-Verbindung erforderlich**
- ⚠️ **API-Kosten** (je nach Modell und Nutzung)
- ⚠️ **Netzwerk-Latenz** (Audio wird an OpenAI gesendet)

---

## Alternative: whisper.cpp (lokal, offline)

**whisper.cpp** ist eine lokale C++‑Implementierung von Whisper:
- ✅ **Kein Internet nötig**
- ✅ **Keine API‑Kosten**
- ⚠️ **Mehr CPU‑Last**
- ⚠️ **Modell muss lokal geladen werden**

### 1. Installation von whisper.cpp

```bash
# Repo klonen
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp

# Build
make -j
```

### 2. Modell herunterladen (ggml)

```bash
mkdir -p models
cd models
./download-ggml-model.sh base
```

### 3. Konfiguration in .env

```bash
# whisper.cpp aktivieren
USE_WHISPER_CPP=true

# Pfad zum Binary
WHISPER_CPP_BIN=/home/marian/whisper.cpp/main

# Pfad zum Modell
WHISPER_CPP_MODEL=/home/marian/whisper.cpp/models/ggml-base.bin

# Optional: Sprache (z.B. de, en) – leer = auto
WHISPER_CPP_LANGUAGE=de

# Threads
WHISPER_CPP_THREADS=4

# Optional: Extra-Args (z.B. "-p 1")
WHISPER_CPP_EXTRA_ARGS=
```

---

## 1. OpenAI API Key einrichten

### API Key erhalten

1. **Registriere dich bei OpenAI:**
   - Gehe zu https://platform.openai.com/
   - Erstelle ein Konto oder melde dich an

2. **API Key erstellen:**
   - Gehe zu https://platform.openai.com/api-keys
   - Klicke auf "Create new secret key"
   - Kopiere den Key (wird nur einmal angezeigt!)

3. **Guthaben hinzufügen:**
   - Gehe zu https://platform.openai.com/account/billing
   - Füge Guthaben hinzu (mindestens $5 empfohlen)

### API Key konfigurieren

Öffne die `.env` Datei:

```bash
nano .env
```

Füge hinzu:

```bash
# OpenAI API Key (erforderlich)
OPENAI_API_KEY=sk-...dein-api-key-hier...

# Whisper Modell (Standard: gpt-4o-mini-transcribe)
OPENAI_MODEL_STT=gpt-4o-mini-transcribe
```

**Wichtig:** Der API Key muss mit `sk-` beginnen.

---

## 2. Verfügbare Whisper-Modelle

OpenAI bietet verschiedene Whisper-Modelle mit unterschiedlichen Eigenschaften:

| Modell | Geschwindigkeit | Genauigkeit | Kosten (pro Minute) | Empfehlung |
|--------|----------------|-------------|---------------------|------------|
| **whisper-1** | Schnell | Sehr gut | $0.006 | ✅ **Empfohlen** |
| **gpt-4o-mini-transcribe** | Sehr schnell | Sehr gut | $0.15 | Für Echtzeit-Anwendungen |
| **gpt-4o-transcribe** | Schnell | Ausgezeichnet | $0.60 | Für höchste Genauigkeit |

### Modell auswählen

In der `.env` Datei:

```bash
# Standard (empfohlen für beste Balance)
OPENAI_MODEL_STT=whisper-1

# Oder für schnellere Antworten (kostet mehr)
OPENAI_MODEL_STT=gpt-4o-mini-transcribe

# Oder für höchste Genauigkeit (kostet am meisten)
OPENAI_MODEL_STT=gpt-4o-transcribe
```

**Hinweis:** Die Modellnamen können sich ändern. Aktuelle Modelle findest du in der [OpenAI Dokumentation](https://platform.openai.com/docs/guides/speech-to-text).

---

## 3. Installation

Die benötigten Pakete werden automatisch mit `requirements.txt` installiert:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Das Projekt nutzt die `openai` Python-Bibliothek, die bereits in `requirements.txt` enthalten ist.

---

## 4. Verwendung

### Normalbetrieb (Push-to-Talk)

Whisper wird automatisch verwendet, wenn kein `--vosk` Flag gesetzt ist:

```bash
source .venv/bin/activate
python -m src.main
```

### Live-Spracherkennung mit Laufband-Anzeige

```bash
# Mit Whisper (OpenAI API, Standard)
python -m src.main --live-recognition

# Mit whisper.cpp (lokal)
USE_WHISPER_CPP=true python -m src.main --live-recognition
```

Die Live-Erkennung zeigt den erkannten Text kontinuierlich auf dem OLED-Display an.

### Modus-Auswahl

Beim Start kannst du zwischen zwei Modi wählen:

1. **Echo Modus:**
   - Deine Sprache wird per Whisper erkannt
   - Die Box spricht den erkannten Text wieder aus (TTS)

2. **Chatbox Modus:**
   - STT (Whisper) → LLM → TTS (normale Chat-Antwort)

### Modus per CLI erzwingen

```bash
python -m src.main --mode echo
python -m src.main --mode chatbox
```

---

## 5. Konfiguration

### Vollständige `.env` Beispiel-Konfiguration

```bash
# OpenAI API Key (erforderlich)
OPENAI_API_KEY=sk-...dein-api-key-hier...

# Whisper Modell (Speech-to-Text)
OPENAI_MODEL_STT=whisper-1

# Chat Modell (für Chatbox-Modus)
OPENAI_MODEL_CHAT=gpt-4o-mini

# TTS Modell (Text-to-Speech)
OPENAI_MODEL_TTS=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy

# Optional: Vosk als Alternative (siehe vosk-setup.md)
USE_VOSK=false  # true = Vosk, false = Whisper (OpenAI)
VOSK_MODEL_PATH=models/vosk-model-de-0.22
```

### TTS Stimmen

Verfügbare Stimmen für `OPENAI_TTS_VOICE`:
- `alloy` (Standard)
- `echo`
- `fable`
- `onyx`
- `nova`
- `shimmer`

---

## 6. Vergleich: Whisper vs. Vosk

| Feature | OpenAI Whisper | Vosk |
|---------|----------------|------|
| **Internet** | ✅ Erforderlich | ❌ Nicht nötig |
| **Kosten** | 💰 API-Kosten (~$0.006/Min) | ✅ Kostenlos |
| **Geschwindigkeit** | ⚠️ Netzwerk-Latenz (~1-3s) | ✅ Sehr schnell (<0.5s) |
| **Genauigkeit** | ✅ Sehr gut bis ausgezeichnet | ✅ Gut bis sehr gut |
| **Datenschutz** | ⚠️ Audio wird an OpenAI gesendet | ✅ 100% lokal |
| **Sprachen** | ✅ Viele Sprachen automatisch | ✅ Viele Sprachen (Modell-abhängig) |
| **Hintergrundgeräusche** | ✅ Sehr robust | ⚠️ Abhängig vom Modell |
| **Modell-Größe** | - | 45 MB - 1.8 GB |

**Empfehlung:**
- **Whisper** für höchste Genauigkeit und wenn Internet verfügbar ist
- **Vosk** für lokale, schnelle Erkennung ohne Internet und ohne API-Kosten

---

## 7. Kostenkontrolle

### Kosten pro Minute Audio

- **whisper-1:** ~$0.006 pro Minute
- **gpt-4o-mini-transcribe:** ~$0.15 pro Minute
- **gpt-4o-transcribe:** ~$0.60 pro Minute

### Beispiel-Kosten

Bei durchschnittlich 2 Minuten Audio pro Tag:
- **whisper-1:** ~$0.36 pro Monat
- **gpt-4o-mini-transcribe:** ~$9 pro Monat
- **gpt-4o-transcribe:** ~$36 pro Monat

### Kostenüberwachung

1. **OpenAI Dashboard:**
   - Gehe zu https://platform.openai.com/usage
   - Sieh dir deine API-Nutzung an

2. **Guthaben-Limits setzen:**
   - Gehe zu https://platform.openai.com/account/billing/limits
   - Setze ein monatliches Limit

---

## 8. Troubleshooting

### Problem: API Key ungültig

**Fehlermeldung:**
```
RuntimeError: OPENAI_API_KEY fehlt. Bitte in .env setzen.
```
oder
```
openai.AuthenticationError: Invalid API key
```

**Lösung:**
1. Prüfe, ob der API Key in `.env` gesetzt ist:
   ```bash
   cat .env | grep OPENAI_API_KEY
   ```

2. Prüfe, ob der Key mit `sk-` beginnt

3. Prüfe, ob noch Guthaben vorhanden ist:
   - https://platform.openai.com/account/billing

4. Erstelle einen neuen API Key falls nötig

### Problem: Keine Internet-Verbindung

**Fehlermeldung:**
```
openai.APIConnectionError: Connection error
```

**Lösung:**
1. Prüfe Internet-Verbindung:
   ```bash
   ping -c 3 api.openai.com
   ```

2. Falls kein Internet verfügbar, verwende Vosk:
   ```bash
   python -m src.main --live-recognition --vosk
   ```

### Problem: Modell nicht gefunden

**Fehlermeldung:**
```
openai.BadRequestError: Invalid model
```

**Lösung:**
1. Prüfe, ob das Modell in `.env` korrekt geschrieben ist:
   ```bash
   cat .env | grep OPENAI_MODEL_STT
   ```

2. Verwende einen gültigen Modellnamen:
   - `whisper-1` (empfohlen)
   - `gpt-4o-mini-transcribe`
   - `gpt-4o-transcribe`

3. Prüfe die [aktuelle Dokumentation](https://platform.openai.com/docs/guides/speech-to-text) für verfügbare Modelle

### Problem: Langsame Erkennung

**Lösung:**
- Die Latenz hängt von der Internet-Verbindung ab
- Typisch: 1-3 Sekunden pro Audio-Chunk
- Für schnellere Erkennung: Verwende Vosk (lokal, offline)

### Problem: Schlechte Erkennungsqualität

**Lösung:**
- Verwende ein besseres Modell (`gpt-4o-transcribe`)
- Prüfe Mikrofon-Qualität
- Stelle sicher, dass Sample-Rate 16000 Hz ist
- Reduziere Hintergrundgeräusche
- Sprich klarer und lauter

---

## 9. Wechsel zwischen Whisper und Vosk

### Whisper verwenden (Standard)

```bash
# In .env
USE_VOSK=false

# Oder beim Start
python -m src.main --live-recognition
```

### Vosk verwenden (lokal, offline)

```bash
# In .env
USE_VOSK=true
VOSK_MODEL_PATH=models/vosk-model-de-0.22

# Oder beim Start
python -m src.main --live-recognition --vosk
```

---

## 10. Performance-Tipps

### Für Raspberry Pi 5 (8 GB)

- ✅ **Whisper API** funktioniert gut, benötigt aber stabile Internet-Verbindung
- ✅ **Latenz:** Typisch 1-3 Sekunden pro Erkennung
- ✅ **Chunk-Dauer:** 2 Sekunden ist ein guter Kompromiss

### Optimierung

In `src/speech_recognition_live.py`:

```python
self.chunk_duration = 2.0  # Sekunden pro Chunk
# Für schnellere Updates: 1.5
# Für bessere Genauigkeit: 3.0
```

---

## 11. Weitere Informationen

- **OpenAI Dokumentation:** https://platform.openai.com/docs/guides/speech-to-text
- **Whisper Paper:** https://arxiv.org/abs/2212.04356
- **API Preise:** https://openai.com/api/pricing/
- **API Status:** https://status.openai.com/

---

## 12. Sicherheit & Datenschutz

### Wichtige Hinweise

- ⚠️ **Audio-Daten werden an OpenAI gesendet**
- ⚠️ **OpenAI speichert Audio-Daten gemäß ihrer Datenschutzrichtlinie**
- ⚠️ **Für sensible Daten: Verwende Vosk (lokal, offline)**

### Datenschutz-Optionen

1. **Whisper API mit Daten-Retention deaktivieren:**
   - In der API-Anfrage: `user` Parameter verwenden (nicht in diesem Projekt implementiert)
   - Siehe OpenAI Dokumentation für Details

2. **Vosk verwenden:**
   - 100% lokal, keine Daten werden gesendet
   - Siehe `docs/vosk-setup.md`

---

**Viel Erfolg mit Whisper!** 🎤🔊
