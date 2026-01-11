# Chunks in der Spracherkennung - Erklärung

Diese Dokumentation erklärt, was "Chunks" in der Spracherkennung bedeuten und welchen Einfluss die `chunk_duration` Einstellung hat.

---

## Was sind Chunks?

Ein **Chunk** ist ein **Audio-Abschnitt** von bestimmter Dauer, der zur Spracherkennung verarbeitet wird.

### Beispiel

```
Kontinuierliche Audio-Aufnahme:
┌─────────────────────────────────────────────────────────┐
│  "Hallo, wie geht es dir heute? Ich hoffe, es geht..."  │
└─────────────────────────────────────────────────────────┘

Aufgeteilt in Chunks (z. B. 2 Sekunden):
┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│ Chunk 1  ││ Chunk 2  ││ Chunk 3  ││ Chunk 4  │
│ "Hallo,  ││ "wie geht││ "es dir  ││ "heute?  │
│ wie"     ││ es dir"  ││ heute?   ││ "Ich"    │
└──────────┘└──────────┘└──────────┘└──────────┘
```

Jeder Chunk wird **einzeln** an das Spracherkennungsmodell gesendet und transkribiert.

---

## Warum Chunks?

### 1. **Speicher-Effizienz**

Statt die gesamte Aufnahme im Speicher zu halten, wird sie in kleine Teile aufgeteilt:

```
❌ Ohne Chunks:
   └─> 60 Sekunden Audio = 1.9 MB RAM (bei 16 kHz, mono)

✅ Mit Chunks (2 Sekunden):
   └─> 2 Sekunden Audio = 64 KB RAM
   └─> Verarbeitung erfolgt sequenziell
```

### 2. **Live-Verarbeitung**

Chunks ermöglichen **kontinuierliche, live Erkennung**:

```
Zeit →
Chunk 1 → [Erkennung] → Text 1
Chunk 2 → [Erkennung] → Text 2
Chunk 3 → [Erkennung] → Text 3
...
```

Der Benutzer sieht die Erkennung **sofort**, nicht erst am Ende.

### 3. **Fehlerbehandlung**

Wenn ein Chunk fehlschlägt, werden die anderen nicht beeinflusst:

```
Chunk 1: ✅ "Hallo, wie"
Chunk 2: ❌ Fehler
Chunk 3: ✅ "geht es dir"
```

---

## Die `chunk_duration` Einstellung

`chunk_duration` bestimmt, wie **lang** jeder Chunk ist (in Sekunden).

### Beispiel-Code

```python
class LiveVoskRecognition:
    def __init__(self, model_path: str, chunk_duration: float = 3.0):
        self.chunk_duration = chunk_duration  # Sekunden pro Chunk
        # ...
    
    def _record_chunk(self):
        frames_to_record = int(self.samplerate * self.chunk_duration)
        # Bei 16000 Hz und 3.0 Sekunden:
        # frames_to_record = 16000 * 3.0 = 48000 Frames
```

---

## Einfluss der `chunk_duration`

### 1. **Erkennungsqualität**

#### Kurze Chunks (1.0-1.5 Sekunden)

```
Chunk: "Hallo"
Erkannt: "Hallo" ✅

Chunk: "wie"
Erkannt: "wie" ✅

Chunk: "geht"
Erkannt: "geht" ✅
```

**Vorteile:**
- ✅ Schnelle Updates
- ✅ Gute für einzelne Wörter

**Nachteile:**
- ❌ Weniger Kontext
- ❌ Wörter können abgeschnitten werden
- ❌ Schlechtere Erkennung bei längeren Sätzen

**Beispiel-Problem:**
```
Chunk 1: "Ich hoffe, es"
Chunk 2: "geht dir gut"
→ "es" und "geht" könnten falsch erkannt werden
```

#### Mittlere Chunks (2.0-3.0 Sekunden) ✅ **Empfohlen**

```
Chunk: "Hallo, wie geht es dir"
Erkannt: "Hallo, wie geht es dir" ✅
```

**Vorteile:**
- ✅ Guter Kompromiss
- ✅ Genug Kontext für gute Erkennung
- ✅ Noch akzeptable Latenz

**Nachteile:**
- ⚠️ Etwas langsamer als kurze Chunks

#### Lange Chunks (4.0-5.0 Sekunden)

```
Chunk: "Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut."
Erkannt: "Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut." ✅✅
```

**Vorteile:**
- ✅ **Beste Erkennungsqualität**
- ✅ Viel Kontext
- ✅ Ganze Sätze werden besser erkannt
- ✅ Weniger Fehler bei Satzgrenzen

**Nachteile:**
- ❌ Langsamere Updates
- ❌ Höhere Latenz (Benutzer wartet länger)
- ❌ Mehr RAM pro Chunk

---

## Vergleich: Chunk-Dauer vs. Erkennungsqualität

### Beispiel-Satz: "Ich hoffe, es geht dir gut heute"

| Chunk-Dauer | Chunks | Erkennung | Qualität |
|-------------|--------|-----------|----------|
| **1.0 s** | 6 Chunks | "Ich hoffe es geht dir gut heute" | ⭐⭐ (Wörter abgeschnitten) |
| **2.0 s** | 3 Chunks | "Ich hoffe, es geht dir gut heute" | ⭐⭐⭐ (Gut) |
| **3.0 s** | 2 Chunks | "Ich hoffe, es geht dir gut heute" | ⭐⭐⭐⭐ (Sehr gut) |
| **5.0 s** | 1 Chunk | "Ich hoffe, es geht dir gut heute" | ⭐⭐⭐⭐⭐ (Optimal) |

---

## Praktische Empfehlungen

### Für Live-Spracherkennung (Laufband)

```python
# Schnell, aber weniger genau
chunk_duration = 1.5  # Sekunden

# Ausgewogen (empfohlen)
chunk_duration = 2.0  # Sekunden ✅

# Langsam, aber sehr genau
chunk_duration = 3.0  # Sekunden
```

### Für Push-to-Talk (komplette Aufnahme)

Bei Push-to-Talk wird die **gesamte Aufnahme** als ein Chunk verarbeitet:

```python
# Komplette Aufnahme (z. B. 5 Sekunden)
wav_bytes = record_while_pressed(lambda: ptt.is_pressed)
text = transcribe(wav_bytes)  # Ein großer Chunk
```

Hier ist `chunk_duration` nicht relevant, da die gesamte Aufnahme verarbeitet wird.

---

## Technische Details

### Berechnung

```python
# Audio-Aufnahme
samplerate = 16000  # Hz (Samples pro Sekunde)
chunk_duration = 3.0  # Sekunden

# Anzahl der Frames pro Chunk
frames_per_chunk = samplerate * chunk_duration
# = 16000 * 3.0 = 48000 Frames

# Größe in Bytes (int16 = 2 Bytes pro Sample)
bytes_per_chunk = frames_per_chunk * 2
# = 48000 * 2 = 96000 Bytes = ~94 KB
```

### Verarbeitungszeit

```python
# Geschätzte Verarbeitungszeit pro Chunk (Vosk)
chunk_duration = 2.0  # Sekunden Audio
processing_time = 0.5  # Sekunden (Vosk-Erkennung)
total_time = 2.0 + 0.5 = 2.5 Sekunden pro Chunk

# Bei 3.0 Sekunden:
chunk_duration = 3.0
processing_time = 0.7  # Etwas länger wegen mehr Daten
total_time = 3.0 + 0.7 = 3.7 Sekunden pro Chunk
```

---

## Optimierung: Was ist die beste Einstellung?

### Abhängig von:

1. **Verwendungszweck:**
   - **Live-Laufband:** 2.0-3.0 Sekunden ✅
   - **Push-to-Talk:** Nicht relevant (komplette Aufnahme)

2. **Hardware:**
   - **Raspberry Pi 5:** Kann 3.0-4.0 Sekunden handhaben
   - **Langsamere Hardware:** 2.0 Sekunden

3. **Modell-Größe:**
   - **Kleines Modell (vosk-model-de-0.22):** 2.0-3.0 Sekunden
   - **Großes Modell (vosk-model-de-0.6-900k):** 3.0-4.0 Sekunden

4. **Gewünschte Qualität:**
   - **Schnell:** 1.5-2.0 Sekunden
   - **Ausgewogen:** 2.0-3.0 Sekunden ✅
   - **Beste Qualität:** 3.0-5.0 Sekunden

---

## Beispiel: Unterschiedliche Einstellungen

### Szenario: "Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut."

#### chunk_duration = 1.5 Sekunden

```
Chunk 1: "Hallo, wie geht"
Chunk 2: "es dir heute? Ich"
Chunk 3: "hoffe, es geht dir"
Chunk 4: "gut."

Ergebnis:
"Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut."
→ Mögliche Fehler bei Satzgrenzen
```

#### chunk_duration = 3.0 Sekunden

```
Chunk 1: "Hallo, wie geht es dir heute? Ich"
Chunk 2: "hoffe, es geht dir gut."

Ergebnis:
"Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut."
→ Bessere Erkennung, mehr Kontext
```

#### chunk_duration = 5.0 Sekunden

```
Chunk 1: "Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut."

Ergebnis:
"Hallo, wie geht es dir heute? Ich hoffe, es geht dir gut."
→ Beste Erkennung, aber langsam
```

---

## Zusammenfassung

| Aspekt | Kurze Chunks (1.5s) | Mittlere Chunks (2-3s) | Lange Chunks (4-5s) |
|--------|---------------------|------------------------|---------------------|
| **Geschwindigkeit** | ⚡⚡⚡ Schnell | ⚡⚡ Mittel | ⚡ Langsam |
| **Erkennungsqualität** | ⭐⭐ Gut | ⭐⭐⭐ Sehr gut | ⭐⭐⭐⭐⭐ Optimal |
| **Latenz** | Niedrig | Mittel | Hoch |
| **RAM-Verbrauch** | Niedrig | Mittel | Hoch |
| **Empfehlung** | Für schnelle Updates | ✅ **Standard** | Für beste Qualität |

**Goldene Regel:** 
- **2.0-3.0 Sekunden** ist ein guter Kompromiss für die meisten Anwendungen
- Für **beste Qualität**: 3.0-4.0 Sekunden
- Für **schnelle Updates**: 1.5-2.0 Sekunden

---

**Tipp:** Teste verschiedene Einstellungen und finde den Sweet Spot für deine Anwendung! 🎤
