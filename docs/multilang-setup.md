# Mehrsprachige Spracherkennung (Deutsch + Englisch)

Diese Anleitung erklärt, wie du mehrere Sprachmodelle kombinierst, um sowohl deutsche als auch englische Wörter zu erkennen.

---

## Übersicht

Die mehrsprachige Spracherkennung ermöglicht es, **mehrere Vosk-Modelle parallel** zu verwenden:

- ✅ **Deutsch + Englisch** gleichzeitig
- ✅ **Automatische Spracherkennung** (wählt bestes Ergebnis)
- ✅ **Kombinierte Erkennung** (beide Sprachen zusammen)
- ✅ **Code-Switching** (gemischte Sprache: "Hallo, how are you?")

---

## 1. Sprachmodelle herunterladen

### Deutsch (falls noch nicht vorhanden)

```bash
cd models
wget https://alphacephei.com/vosk/models/vosk-model-de-0.22.zip
unzip vosk-model-de-0.22.zip
```

### Englisch

```bash
cd models
wget https://alphacephei.com/vosk/models/vosk-model-en-us-0.22.zip
unzip vosk-model-en-us-0.22.zip
```

**Alternative englische Modelle:**
- `vosk-model-en-us-0.22` (~45 MB) - Klein, schnell
- `vosk-model-en-us-0.6` (~1.8 GB) - Groß, sehr genau

---

## 2. Konfiguration

### .env Datei anpassen

```bash
nano .env
```

Füge hinzu:

```bash
# Vosk Sprachmodelle
VOSK_MODEL_PATH=models/vosk-model-de-0.22
VOSK_MODEL_PATH_EN=models/vosk-model-en-us-0.22

# Mehrsprachige Erkennung aktivieren
USE_MULTILANG=false  # true = mehrsprachig, false = nur Deutsch
```

---

## 3. Verwendung

### Modus 1: Bestes Ergebnis (empfohlen)

Wählt automatisch das beste Ergebnis aus allen Sprachen:

```bash
python -m src.main --live-recognition --vosk --multilang
```

**Funktionsweise:**
- Beide Modelle (DE + EN) transkribieren parallel
- Das Ergebnis mit dem längsten Text wird gewählt
- Automatische Spracherkennung

**Beispiel:**
```
Sprich: "Hallo, how are you?"
[DE] "Hallo, wie geht es dir"
[EN] "Hallo, how are you"
→ Gewählt: [EN] "Hallo, how are you" (länger, genauer)
```

### Modus 2: Kombiniert

Kombiniert Ergebnisse aller Sprachen:

```bash
python -m src.main --live-recognition --vosk --multilang --combined
```

**Funktionsweise:**
- Beide Modelle transkribieren
- Ergebnisse werden kombiniert
- Nützlich für Code-Switching

**Beispiel:**
```
Sprich: "Hallo, how are you?"
[DE] "Hallo, wie geht es dir"
[EN] "Hallo, how are you"
→ Kombiniert: "Hallo, wie geht es dir Hallo, how are you"
```

### Modus 3: Alle anzeigen

Zeigt Ergebnisse aller Sprachen:

```bash
python -m src.main --live-recognition --vosk --multilang --all
```

**Funktionsweise:**
- Alle Ergebnisse werden angezeigt
- Bestes Ergebnis für Display verwendet

---

## 4. Push-to-Talk mit mehreren Sprachen

```bash
# Bestes Ergebnis
python -m src.main --live-recognition --ptt --vosk --multilang

# Kombiniert
python -m src.main --live-recognition --ptt --vosk --multilang --combined
```

---

## 5. Weitere Sprachen hinzufügen

### Verfügbare Vosk-Modelle

- **Französisch:** `vosk-model-fr-0.22`
- **Spanisch:** `vosk-model-es-0.22`
- **Italienisch:** `vosk-model-it-0.22`
- **Russisch:** `vosk-model-ru-0.22`
- **Chinesisch:** `vosk-model-cn-0.22`
- **Weitere:** https://alphacephei.com/vosk/models

### Beispiel: Deutsch + Englisch + Französisch

1. **Modelle herunterladen:**
```bash
cd models
wget https://alphacephei.com/vosk/models/vosk-model-fr-0.22.zip
unzip vosk-model-fr-0.22.zip
```

2. **.env erweitern:**
```bash
VOSK_MODEL_PATH_DE=models/vosk-model-de-0.22
VOSK_MODEL_PATH_EN=models/vosk-model-en-us-0.22
VOSK_MODEL_PATH_FR=models/vosk-model-fr-0.22
```

3. **Code anpassen:**
In `src/speech_recognition_multilang.py`, Funktion `run_multilang_vosk_recognition()`:

```python
# Französisch hinzufügen
fr_path = os.getenv("VOSK_MODEL_PATH_FR", "models/vosk-model-fr-0.22")
if fr_path:
    model_paths["fr"] = fr_path
```

---

## 6. Performance

### RAM-Verbrauch

| Anzahl Modelle | RAM (kleine Modelle) | RAM (große Modelle) |
|----------------|----------------------|---------------------|
| 1 Modell       | ~100 MB              | ~2 GB               |
| 2 Modelle      | ~200 MB              | ~4 GB               |
| 3 Modelle      | ~300 MB              | ~6 GB               |

**Empfehlung für Raspberry Pi 5 (8 GB):**
- ✅ 2-3 kleine Modelle (0.22)
- ⚠️ 1-2 große Modelle (0.6)
- ❌ Nicht mehr als 2 große Modelle

### Geschwindigkeit

- **1 Modell:** 100% (Referenz)
- **2 Modelle:** ~180% (etwas langsamer, da parallel)
- **3 Modelle:** ~250% (deutlich langsamer)

**Tipp:** Verwende kleine Modelle (0.22) für bessere Performance.

---

## 7. Vergleich: Modi

| Modus | Verwendung | Vorteil | Nachteil |
|-------|------------|---------|----------|
| **best** | Standard | Automatische Spracherkennung | Nur eine Sprache |
| **combined** | Code-Switching | Beide Sprachen | Doppelte Wörter möglich |
| **all** | Debugging | Alle Ergebnisse sichtbar | Langsam, viel Output |

**Empfehlung:** `best` für normale Nutzung, `combined` für gemischte Sprache.

---

## 8. Beispiel-Szenarien

### Szenario 1: Deutsche und englische Wörter

**Eingabe:** "Hallo, how are you? Ich bin gut."

**Modus "best":**
```
[DE] "Hallo, wie geht es dir? Ich bin gut"
[EN] "Hallo, how are you? I am good"
→ Gewählt: [EN] (länger)
```

**Modus "combined":**
```
→ "Hallo, wie geht es dir? Ich bin gut Hallo, how are you? I am good"
```

### Szenario 2: Code-Switching

**Eingabe:** "Das ist ein test"

**Modus "best":**
```
[DE] "Das ist ein Test"
[EN] "That is a test"
→ Gewählt: [DE] (passt besser)
```

---

## 9. Troubleshooting

### Problem: Modell nicht gefunden

**Fehlermeldung:**
```
⚠️  Warnung: Modell für en nicht gefunden: models/vosk-model-en-us-0.22
```

**Lösung:**
1. Prüfe Modell-Pfad in `.env`
2. Prüfe, ob Modell existiert: `ls -la models/vosk-model-en-us-0.22/`
3. Verwende absoluten Pfad: `VOSK_MODEL_PATH_EN=/home/user/models/vosk-model-en-us-0.22`

### Problem: Zu langsam

**Lösung:**
- Verwende kleinere Modelle (0.22 statt 0.6)
- Reduziere Anzahl der Modelle
- Erhöhe `chunk_duration` (weniger häufige Transkription)

### Problem: Falsche Sprache erkannt

**Lösung:**
- Prüfe, ob beide Modelle korrekt geladen wurden
- Verwende Modus `--all` um alle Ergebnisse zu sehen
- Stelle sicher, dass beide Modelle die richtige Sprache haben

---

## 10. Erweiterte Konfiguration

### Nur bestimmte Sprachen verwenden

In Code anpassen:

```python
# Nur Deutsch und Englisch
recognizer = LiveMultiLanguageVoskRecognition(
    model_paths={"de": "models/vosk-model-de-0.22", "en": "models/vosk-model-en-us-0.22"},
    mode="best"
)
```

### Gewichtete Auswahl

Du kannst die Auswahl-Logik in `transcribe_audio_best()` anpassen:

```python
# Statt längstem Text, verwende Confidence-Score (falls verfügbar)
# Oder bevorzuge bestimmte Sprache
```

---

## Zusammenfassung

**Schnellstart:**
1. Modelle herunterladen (DE + EN)
2. `.env` konfigurieren
3. `python -m src.main --live-recognition --vosk --multilang`

**Vorteile:**
- ✅ Automatische Spracherkennung
- ✅ Unterstützt Code-Switching
- ✅ Flexibel erweiterbar

**Nachteile:**
- ⚠️ Höherer RAM-Verbrauch
- ⚠️ Etwas langsamer

---

**Viel Erfolg mit der mehrsprachigen Erkennung!** 🌍🎤
