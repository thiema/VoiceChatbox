l# Vosk Sprachmodell Setup (Deutsch, lokal)

Diese Anleitung erklärt, wie du das lokale Vosk-Sprachmodell für die Spracherkennung einrichtest.

---

## Was ist Vosk?

**Vosk** ist eine Offline-Spracherkennungsbibliothek, die **lokal auf dem Raspberry Pi** läuft. 
- ✅ **Keine Internet-Verbindung nötig**
- ✅ **Keine API-Kosten**
- ✅ **Schnelle Erkennung** (keine Netzwerk-Latenz)
- ✅ **Datenschutz** (Audio bleibt lokal)

---

## 1. Vosk installieren

Vosk wird automatisch mit `requirements.txt` installiert:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Oder manuell:

```bash
pip install vosk
```

---

## 2. Sprachmodell herunterladen

### Verfügbare deutsche Modelle

Vosk bietet verschiedene deutsche Modelle:

| Modell | Größe | Genauigkeit | Empfehlung |
|--------|-------|-------------|------------|
| **vosk-model-de-0.22** | ~45 MB | Gut | ✅ **Empfohlen für Raspberry Pi** |
| **vosk-model-de-0.6-900k** | ~1.8 GB | Sehr gut | Für bessere Genauigkeit |
| **vosk-model-de-0.6** | ~1.8 GB | Sehr gut | Alternative |

### Download

1. **Modell herunterladen:**
   ```bash
   cd /home/marian/Projects/VoiceChatbox
   mkdir -p models
   cd models
   
   # Kleines Modell (empfohlen)
   wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
   wget https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip
   wget https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   
   # Oder großes Modell (bessere Genauigkeit)
   wget https://alphacephei.com/vosk/models/vosk-model-de-0.21.zip
   wget https://alphacephei.com/vosk/models/vosk-model-ru-0.42.zip
   ```

2. **Modell entpacken:**
   ```bash
   unzip vosk-model-de-0.22.zip
   # Sollte Ordner "vosk-model-de-0.22" erstellen
   ```

3. **Struktur prüfen:**
   ```bash
   ls -la vosk-model-de-0.22/
   # Sollte enthalten: am/, conf/, graph/, ivector/, etc.
   ```

---

## 3. Konfiguration

### .env Datei anpassen

Öffne die `.env` Datei:

```bash
nano .env
```

Füge hinzu:

```bash
# Vosk Sprachmodell (lokal, offline)
VOSK_MODEL_PATH=models/vosk-model-de-0.22

# Optional: Standardmäßig Vosk verwenden
USE_VOSK=false  # true = Vosk, false = OpenAI
```

### Empfohlene Defaults für bessere Erkennung

Diese Werte reduzieren Fehldeutungen und vermeiden, dass unvollständige Wörter
an OpenAI gesendet werden:

```bash
# Längere Pause bis Satzende (verhindert Satz-Splits)
LIVE_PAUSE_DURATION=1.2

# Erst ab 3 Wörtern an ChatGPT senden
MIN_CHAT_WORDS=3

# Triviale Wörter als Fragmente blocken
TRIVIAL_WORDS=die,der,das,ein,eine,und,oder,aber,ok,okay,etc,äh,ähm

# Nach TTS kurz sperren, um Echo zu vermeiden
CHAT_IGNORE_AFTER_TTS_SEC=2.0

# Nach Inaktivität automatisch in Pause
AUTO_PAUSE_AFTER_SEC=10
```

**Hinweis:** Der Pfad ist relativ zum Projektverzeichnis oder absolut.

---

## 4. Verwendung

### Live-Spracherkennung mit Vosk

```bash
source .venv/bin/activate
python -m src.main --live-recognition --vosk
```

Oder wenn `USE_VOSK=true` in `.env` gesetzt ist:

```bash
python -m src.main --live-recognition
```

### Direkt mit Vosk-Modul

```bash
python -m src.speech_recognition_vosk models/vosk-model-de-0.22
```

---

## 5. Vergleich: OpenAI vs. Vosk

| Feature | OpenAI Whisper | Vosk |
|---------|----------------|------|
| **Internet** | ✅ Erforderlich | ❌ Nicht nötig |
| **Kosten** | 💰 API-Kosten | ✅ Kostenlos |
| **Geschwindigkeit** | ⚠️ Netzwerk-Latenz | ✅ Sehr schnell |
| **Genauigkeit** | ✅ Sehr gut | ✅ Gut bis sehr gut |
| **Datenschutz** | ⚠️ Audio wird gesendet | ✅ 100% lokal |
| **Modell-Größe** | - | 45 MB - 1.8 GB |

**Empfehlung:**
- **Vosk** für lokale, schnelle Erkennung ohne Internet
- **OpenAI** für höchste Genauigkeit und wenn Internet verfügbar ist

---

## 6. Troubleshooting

### Problem: Modell nicht gefunden

**Fehlermeldung:**
```
FileNotFoundError: Vosk-Modell nicht gefunden: models/vosk-model-de-0.22
```

**Lösung:**
1. Prüfe, ob der Modell-Ordner existiert:
   ```bash
   ls -la models/vosk-model-de-0.22/
   ```

2. Prüfe den Pfad in `.env`:
   ```bash
   cat .env | grep VOSK_MODEL_PATH
   ```

3. Verwende absoluten Pfad:
   ```bash
   VOSK_MODEL_PATH=/home/marian/Projects/VoiceChatbox/models/vosk-model-de-0.22
   ```

### Problem: Vosk nicht installiert

**Fehlermeldung:**
```
ImportError: Vosk ist nicht installiert
```

**Lösung:**
```bash
source .venv/bin/activate
pip install vosk
```

### Problem: Langsame Erkennung

**Lösung:**
- Verwende das kleinere Modell (`vosk-model-de-0.22`)
- Reduziere `chunk_duration` in `speech_recognition_vosk.py`
- Prüfe CPU-Auslastung: `htop`

### Problem: Schlechte Erkennungsqualität

**Lösung:**
- Verwende das größere Modell (`vosk-model-de-0.6-900k`)
- Prüfe Mikrofon-Qualität
- Stelle sicher, dass Sample-Rate 16000 Hz ist
- Reduziere Hintergrundgeräusche

---

## 7. Modell-Update

Um ein neues Modell zu verwenden:

1. **Neues Modell herunterladen:**
   ```bash
   cd models
   wget https://alphacephei.com/vosk/models/vosk-model-de-0.6-900k.zip
   unzip vosk-model-de-0.6-900k.zip
   ```

2. **.env aktualisieren:**
   ```bash
   VOSK_MODEL_PATH=models/vosk-model-de-0.6-900k
   ```

3. **Neu starten:**
   ```bash
   python -m src.main --live-recognition --vosk
   ```

---

## 8. Performance-Tipps

### Für Raspberry Pi 5 (8 GB)

- ✅ **Kleines Modell** (`vosk-model-de-0.22`) läuft flüssig
- ✅ **Großes Modell** (`vosk-model-de-0.6-900k`) funktioniert, aber langsamer
- ✅ **Chunk-Dauer:** 2 Sekunden ist ein guter Kompromiss

### Optimierung

In `src/speech_recognition_vosk.py`:

```python
self.chunk_duration = 2.0  # Sekunden pro Chunk
# Für schnellere Updates: 1.5
# Für bessere Genauigkeit: 3.0
```

---

## 9. Weitere Informationen

- **Vosk Website:** https://alphacephei.com/vosk/
- **Modelle:** https://alphacephei.com/vosk/models
- **Dokumentation:** https://alphacephei.com/vosk/install

---

**Viel Erfolg mit der lokalen Spracherkennung!** 🎤🔊
