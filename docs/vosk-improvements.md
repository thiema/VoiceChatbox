# Vosk Spracherkennung - Verbesserungen

Diese Dokumentation erklärt, wie du die Erkennungsqualität des Vosk-Sprachmodells verbessern kannst.

---

## Problem: Viele Erkennungsfehler

Wenn Vosk viele Fehler macht, gibt es mehrere Verbesserungsmöglichkeiten:

---

## 1. Größeres/besseres Modell verwenden

### Aktuelles Modell prüfen

```bash
ls -lh models/
```

### Empfohlene Modelle (von klein zu groß)

| Modell | Größe | Genauigkeit | Geschwindigkeit | Empfehlung |
|--------|-------|-------------|-----------------|------------|
| **vosk-model-de-0.22** | ~45 MB | ⭐⭐⭐ | ⚡⚡⚡ | Gut für Tests |
| **vosk-model-de-0.6-900k** | ~1.8 GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | ✅ **Beste Genauigkeit** |
| **vosk-model-de-0.6** | ~1.8 GB | ⭐⭐⭐⭐⭐ | ⚡⚡ | Alternative |

### Größeres Modell installieren

```bash
cd models
# Altes Modell löschen (optional)
# rm -rf vosk-model-de-0.22

# Neues Modell herunterladen
wget https://alphacephei.com/vosk/models/vosk-model-de-0.6-900k.zip
unzip vosk-model-de-0.6-900k.zip

# In .env aktualisieren
VOSK_MODEL_PATH=models/vosk-model-de-0.6-900k
```

**Hinweis:** Das größere Modell benötigt mehr RAM und ist langsamer, aber deutlich genauer!

---

## 2. Audio-Vorverarbeitung

Die Implementierung enthält jetzt automatische Audio-Vorverarbeitung:

- ✅ **Normalisierung:** Audio wird auf optimalen Pegel gebracht
- ✅ **High-Pass Filter:** Entfernt tiefe Frequenzen/Rauschen
- ✅ **Voice Activity Detection:** Überspringt leise/leere Chunks

### Aktivieren/Deaktivieren

In `src/speech_recognition_vosk.py`:

```python
recognizer = LiveVoskRecognition(
    model_path=model_path,
    device=settings.audio_input_device,
    enable_audio_processing=True  # True = aktiviert
)
```

---

## 3. Chunk-Dauer optimieren

Längere Chunks = besserer Kontext = bessere Erkennung, aber langsamer.

### Standard-Einstellung

```python
chunk_duration = 2.0  # Sekunden
```

### Empfohlene Werte

- **Kurz (schnell, weniger genau):** `1.5` Sekunden
- **Standard (ausgewogen):** `2.0-3.0` Sekunden ✅
- **Lang (langsam, sehr genau):** `4.0-5.0` Sekunden

### Anpassen

In `src/speech_recognition_vosk.py` oder beim Aufruf:

```python
recognizer = LiveVoskRecognition(
    model_path=model_path,
    device=settings.audio_input_device,
    chunk_duration=3.0  # Längere Chunks = bessere Erkennung
)
```

---

## 4. Mikrofon-Qualität

### Mikrofon prüfen

```bash
# Audio-Geräte auflisten
python -m src.audio_test --list

# Mikrofon-Test mit Pegelanzeige
python -m src.audio_test --mic --device 2
```

### Empfehlungen

- ✅ **Gute Position:** 20-30 cm vom Mund entfernt
- ✅ **Ruhige Umgebung:** Reduziere Hintergrundgeräusche
- ✅ **Richtung:** Sprich direkt ins Mikrofon
- ✅ **Lautstärke:** Sprich klar und deutlich (nicht zu leise/laut)

---

## 5. Sample Rate prüfen

Vosk benötigt **16 kHz** Sample Rate. Die Implementierung setzt dies automatisch, aber prüfe:

```bash
# Prüfe Mikrofon-Sample-Rate
python -m src.audio_test --list
# Sollte 16000 Hz oder höher zeigen
```

---

## 6. Audio-Gain anpassen

### System-Lautstärke

```bash
# ALSA Mixer öffnen
alsamixer

# Oder per Kommando
amixer set Capture 80%  # 0-100%
```

### In Python (optional)

Du kannst die Audio-Gain in `_record_chunk()` anpassen:

```python
# Nach Aufnahme, vor Verarbeitung:
audio_data = audio_data * 1.2  # 20% lauter
audio_data = np.clip(audio_data, -32768, 32767)  # Verhindere Clipping
```

---

## 7. Umgebungsbedingungen

### Optimale Bedingungen

- ✅ **Ruhige Umgebung:** Reduziere Hintergrundgeräusche
- ✅ **Gute Akustik:** Vermeide Hall/Echo
- ✅ **Stabile Position:** Mikrofon nicht bewegen während Aufnahme
- ✅ **Klare Aussprache:** Sprich deutlich und nicht zu schnell

### Schlechte Bedingungen vermeiden

- ❌ Hintergrundmusik
- ❌ Mehrere Personen gleichzeitig
- ❌ Echo/Hall (z. B. in großen Räumen)
- ❌ Wind/Luftgeräusche
- ❌ Zu weit vom Mikrofon entfernt

---

## 8. Vergleich: Modell-Größen

### Test mit beiden Modellen

```bash
# Kleines Modell
VOSK_MODEL_PATH=models/vosk-model-de-0.22 python -m src.main --live-recognition --vosk

# Großes Modell
VOSK_MODEL_PATH=models/vosk-model-de-0.6-900k python -m src.main --live-recognition --vosk
```

**Erwartete Verbesserung:** Das große Modell sollte **30-50% weniger Fehler** machen.

---

## 9. Debugging: Was wird erkannt?

### Verbose-Modus aktivieren

In `src/speech_recognition_vosk.py`, Zeile 37:

```python
SetLogLevel(0)  # Statt -1 für mehr Ausgaben
```

### Audio-Dateien speichern (optional)

Füge hinzu in `_process_chunk()`:

```python
# Speichere Audio für Analyse
import soundfile as sf
sf.write(f"debug_audio_{int(time.time())}.wav", audio_data, self.samplerate)
```

Dann kannst du die Dateien analysieren und prüfen, ob die Audio-Qualität gut ist.

---

## 10. Alternative: Whisper lokal

Falls Vosk trotz aller Optimierungen nicht zufriedenstellend ist, kannst du **Whisper lokal** verwenden:

```bash
pip install openai-whisper
```

Whisper ist genauer als Vosk, aber:
- ⚠️ Benötigt mehr RAM (ca. 2-4 GB)
- ⚠️ Langsamer als Vosk
- ✅ Deutlich bessere Genauigkeit

---

## Zusammenfassung: Schnelle Verbesserungen

1. **Größeres Modell verwenden** (vosk-model-de-0.6-900k)
2. **Chunk-Dauer erhöhen** (3.0-4.0 Sekunden)
3. **Audio-Vorverarbeitung aktivieren** (bereits implementiert)
4. **Mikrofon-Position optimieren** (20-30 cm, direkt)
5. **Ruhige Umgebung** (Hintergrundgeräusche reduzieren)

**Erwartete Verbesserung:** 50-70% weniger Fehler bei optimalen Einstellungen.

---

## Troubleshooting

### Problem: Immer noch viele Fehler

**Lösung:**
1. Prüfe Mikrofon-Qualität: `python -m src.audio_test --mic`
2. Teste mit größerem Modell
3. Erhöhe Chunk-Dauer auf 4.0 Sekunden
4. Prüfe Audio-Gain (nicht zu leise/laut)

### Problem: Zu langsam

**Lösung:**
1. Verwende kleineres Modell (vosk-model-de-0.22)
2. Reduziere Chunk-Dauer auf 1.5 Sekunden
3. Deaktiviere Audio-Vorverarbeitung (falls scipy fehlt)

### Problem: Keine Erkennung

**Lösung:**
1. Prüfe Mikrofon-Anschluss
2. Prüfe Audio-Gerät: `python -m src.audio_test --list`
3. Erhöhe VAD-Threshold in `_detect_speech()`
4. Prüfe Sample Rate (muss 16000 Hz sein)

---

**Viel Erfolg bei der Optimierung!** 🎤🔊
