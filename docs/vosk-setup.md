# Vosk Sprachmodell Setup (Deutsch, lokal)

Diese Anleitung erklärt, wie du das lokale Vosk-Sprachmodell für die Spracherkennung einrichtest.

---

## Was ist Vosk?

**Vosk** ist eine Offline-Spracherkennungsbibliothek, die **lokal auf dem Raspberry Pi** läuft. 
- ✅ **Keine Internet-Verbindung nötig**
- ✅ **Keine API-Kosten**
- ✅ **Schnelle Erkennung** (keine Netzwerk-Latenz)
- ✅ **Datenschutz** (Audio bleibt lokal)

### Architektur (Live, lokal)

Mic → continuous `InputStream` → VAD (WebRTC-Anteil + Preroll/Hangover) →
ein `KaldiRecognizer` pro Äußerung → `FinalResult` → OLED/Chat.

Audio-Vorverarbeitung: High-Pass (~80 Hz) + RMS-Ziel-AGC mit Gain-Cap
(kein Peak-Normalize). VAD läuft auf **rohem** Audio.

Für Deutsch: **DE-only** (`USE_MULTILANG=false`, `USE_SMART_MULTILANG=false`).
Multilang-Heuristiken („längster Text“) verschlechtern oft die DE-Erkennung.


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
| **vosk-model-de-0.22** | ~45 MB | Gut | OK für schwächere Pis / wenig RAM |
| **vosk-model-de-0.6-900k** | ~1.8 GB | Sehr gut | ✅ **Empfohlen für Pi 5** (beste lokale DE-Genauigkeit) |
| **vosk-model-de-0.6** | ~1.8 GB | Sehr gut | Alternative |

### Download

1. **Modell herunterladen:**
   ```bash
   cd /home/marian/Projects/VoiceChatbox
   mkdir -p models
   cd models
   
   # Standard DE (kompatibel mit VOSK_MODEL_PATH Default)
   wget https://alphacephei.com/vosk/models/vosk-model-de-0.22.zip
   
   # Empfohlen für Pi 5 / bessere Genauigkeit (~1.8 GB)
   wget https://alphacephei.com/vosk/models/vosk-model-de-0.6-900k.zip
   
   # Optional EN (nur wenn Multilang wirklich nötig)
   wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
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
# Vosk Sprachmodell (lokal, offline) — DE-only für beste Qualität
VOSK_MODEL_PATH=models/vosk-model-de-0.22
# Pi 5 mit genug RAM:
# VOSK_MODEL_PATH=models/vosk-model-de-0.6-900k

# Multilang/Smart-Multilang für DE-first Qualität aus lassen
USE_MULTILANG=false
USE_SMART_MULTILANG=false

# Optional: Standardmäßig Vosk verwenden
USE_VOSK=true  # true = Vosk lokal, false = OpenAI STT
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

### VAD-Parameter (Sprachbeginn/-mitte/-ende verbessern)

Die VAD-Parameter steuern, wann Audio als Sprache erkannt wird. Damit lassen
sich fehlende Wörter am Anfang, in der Mitte oder am Ende reduzieren.

```bash
# Grundempfindlichkeit (RMS). Niedriger = empfindlicher.
VAD_RMS_THRESHOLD=0.01

# Dynamische Schwelle relativ zur Geräuschkulisse.
VAD_NOISE_MULTIPLIER=3.0

# Wie schnell sich der Noise-Floor anpasst (0..1).
VAD_NOISE_ALPHA=0.1

# "Nachlauf": macht VAD am Satzende toleranter.
VAD_HANGOVER_FACTOR=0.6

# Vorlauf-Puffer in Sekunden, um Satzanfänge nicht zu verlieren.
VAD_PREROLL_SEC=0.30

# WebRTC VAD (robuster gegen Rauschen)
VAD_USE_WEBRTCVAD=true
# Aggressiveness: 0 (locker) .. 3 (streng); 1 = weicher für gesprochene Sprache
VAD_WEBRTCVAD_MODE=1
# Frame-Länge in ms (10/20/30)
VAD_WEBRTCVAD_FRAME_MS=30
# Mindestanteil Speech-Frames pro Block (statt „irgendein Frame“)
VAD_SPEECH_RATIO=0.2

# HPF + RMS-AGC (Gain-Cap). Zum A/B-Test auf false setzen.
ENABLE_AUDIO_PROCESSING=true
```

**Tuning-Tipps:**
- Fehlende Satzanfänge → `VAD_PREROLL_SEC` erhöhen (0.30–0.40).
- Zu viel Müll bei Stille → `VAD_SPEECH_RATIO` erhöhen (0.25–0.35).
- Weiche Sprache wird abgeschnitten → `VAD_WEBRTCVAD_MODE=0` oder `1`.
- Fehlende Wörter in der Mitte (RMS-Pfad) → `VAD_RMS_THRESHOLD` leicht senken (0.008).
- Zu frühes Satzende → `VAD_HANGOVER_FACTOR` senken (0.45–0.55) bzw. `VOSK_PAUSE_DURATION` erhöhen.
- Mic prüfen: `AUDIO_INPUT_DEVICE` exakt setzen; `DEBUG_LOGS=true` zeigt RMS/Peak/VAD.
- ReSpeaker: Capture-Pegel so einstellen, dass Clipping und extremes AGC unnötig sind.

### Live-Streaming / Pause

Die Live-Vosk-Pipeline nutzt durchgehende Aufnahme (`InputStream`) und **einen
KaldiRecognizer pro Äußerung** (kein Batch pro 3-s-Chunk mehr).

```bash
# Legacy/Compat (Streaming nutzt VAD-Frames ~30 ms)
VOSK_CHUNK_DURATION=3.0

# Stille-Dauer bis Äußerungsende (Sekunden)
VOSK_PAUSE_DURATION=1.2
```

### Status: BEREIT nach Antwort halten

```bash
# Nach Antwort/Verwerfen für X Sekunden im Modus BEREIT bleiben
READY_HOLD_SEC=10.0
```

### Audio: Lautsprecher im Idle stummschalten

```bash
# Wenn keine Ausgabe läuft, System-Lautstärke auf 0 setzen
MUTE_OUTPUT_WHEN_IDLE=true

# Standard-Lautstärke bei Ausgabe (in Prozent)
OUTPUT_VOLUME_PERCENT=60

# Mixer-Control (Linux amixer), z.B. "Master" oder "PCM"
OUTPUT_VOLUME_CONTROL=Master
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
