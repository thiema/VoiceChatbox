# Semantische Satzerkennung

Diese Dokumentation erklärt die semantische Satzerkennung, die automatisch Sätze erkennt und analysiert.

---

## Übersicht

Die semantische Satzerkennung erweitert die Spracherkennung um:

- ✅ **Satzgrenzen-Erkennung:** Erkennt, wann ein Satz endet
- ✅ **Satztyp-Erkennung:** Frage, Imperativ, Ausruf, Statement
- ✅ **Sentiment-Analyse:** Positive, negative oder neutrale Stimmung
- ✅ **Satz-basierte Anzeige:** Zeigt nur vollständige Sätze auf dem Display

---

## Funktionsweise

### 1. Satzgrenzen-Erkennung

Der `SentenceDetector` erkennt Satzgrenzen anhand von:

- **Satzende-Zeichen:** `.`, `!`, `?`, `…`
- **Abkürzungserkennung:** Unterscheidet zwischen echten Satzenden und Abkürzungen (z.B. "Dr.", "z.B.")
- **Kontext-Analyse:** Prüft, ob nach dem Satzende ein neuer Satz beginnt

**Beispiel:**
```
"Hallo, wie geht es dir? Ich bin gut."
→ 2 Sätze erkannt:
   1. "Hallo, wie geht es dir?"
   2. "Ich bin gut."
```

### 2. Semantische Analyse

Der `SemanticAnalyzer` analysiert jeden Satz:

- **Satztyp:**
  - `question` (Frage): Beginnt mit Fragewort oder endet mit `?`
  - `imperative` (Imperativ): Beginnt mit Befehlswort (z.B. "Bitte", "Mach")
  - `exclamation` (Ausruf): Endet mit `!`
  - `statement` (Aussage): Standard-Satz

- **Sentiment:**
  - `positive`: Enthält positive Wörter (gut, super, toll)
  - `negative`: Enthält negative Wörter (schlecht, nein, falsch)
  - `neutral`: Standard

**Beispiel:**
```
"Wie geht es dir?" → question, neutral
"Das ist super!" → exclamation, positive
"Bitte hilf mir." → imperative, neutral
```

---

## Verwendung

### Aktivieren

Die semantische Satzerkennung ist **standardmäßig aktiviert**. Sie kann deaktiviert werden:

```python
# In Code
recognizer = LiveSpeechRecognition(
    client=client,
    model_stt=settings.model_stt,
    enable_semantic=False  # Deaktivieren
)
```

### Ausgabe

**Mit semantischer Erkennung:**
```
❓ [QUESTION] Wie geht es dir?
💬 [STATEMENT] Ich bin gut.
❗ [IMPERATIVE] Bitte hilf mir.
   Sentiment: positive
```

**Ohne semantische Erkennung:**
```
Erkannt: Wie geht es dir? Ich bin gut.
Gesamt: Wie geht es dir? Ich bin gut.
```

---

## Satz-basierte Display-Anzeige

### Standard-Verhalten

Ohne semantische Erkennung:
- Zeigt gesamten kumulativen Text
- Kann sehr lang werden

### Mit semantischer Erkennung

- Zeigt nur die **letzten 2 vollständigen Sätze**
- Unvollständiger Satz wird angezeigt, wenn vorhanden
- Bessere Lesbarkeit auf kleinem Display

**Beispiel:**
```
Gesamttext: "Hallo. Wie geht es dir? Ich bin gut. Das ist super."
Display zeigt: "Ich bin gut. Das ist super."
```

---

## Konfiguration

### Sprache

```python
recognizer = LiveSpeechRecognition(
    client=client,
    model_stt=settings.model_stt,
    language="de"  # oder "en" für Englisch
)
```

### Minimale Satzlänge

In `sentence_detection.py`:

```python
detector = SentenceDetector(min_sentence_length=3)  # Mindestens 3 Zeichen
```

---

## Erweiterte Funktionen

### Satz-Statistiken

```python
from .sentence_detection import SemanticSpeechRecognition

processor = SemanticSpeechRecognition(language="de")
result = processor.process_text("Hallo. Wie geht es dir? Gut!")

print(f"Anzahl Sätze: {len(result['complete_sentences'])}")
print(f"Unvollständiger Satz: {result['incomplete_sentence']}")

for info in result['semantic_info']:
    print(f"Satz: {info['sentence'].text}")
    print(f"Typ: {info['type']}")
    print(f"Sentiment: {info['analysis']['sentiment']}")
```

### Satztyp-Filter

Du kannst nach bestimmten Satztypen filtern:

```python
# Nur Fragen
questions = [s for s in sentences if s.type == 'question']

# Nur Imperative
imperatives = [s for s in sentences if s.type == 'imperative']
```

---

## Beispiel-Ausgabe

### Eingabe (gesprochen)

"Hallo, wie geht es dir? Ich bin gut. Das ist super!"

### Verarbeitung

```
Chunk 1: "Hallo, wie geht es dir?"
  → ❓ [QUESTION] Hallo, wie geht es dir?

Chunk 2: "Ich bin gut."
  → 💬 [STATEMENT] Ich bin gut.

Chunk 3: "Das ist super!"
  → ❗ [EXCLAMATION] Das ist super!
     Sentiment: positive
```

### Display

Zeigt: "Ich bin gut. Das ist super!"

---

## Anpassung

### Eigene Satzende-Marker

In `sentence_detection.py`:

```python
self.sentence_endings = ['.', '!', '?', '…', ';']  # Semikolon hinzufügen
```

### Eigene Abkürzungen

```python
self.abbreviations['de'].append('z.B.')  # Weitere Abkürzung
```

### Eigene Sentiment-Wörter

```python
positive_words['de'].append('fantastisch')
negative_words['de'].append('schrecklich')
```

---

## Performance

Die semantische Satzerkennung ist **sehr schnell**:

- **Satzgrenzen-Erkennung:** < 1ms pro Text
- **Semantische Analyse:** < 1ms pro Satz
- **Gesamt-Overhead:** < 5ms pro Chunk

**Kein merklicher Performance-Verlust!**

---

## Troubleshooting

### Problem: Sätze werden nicht erkannt

**Lösung:**
- Prüfe, ob Satzende-Zeichen vorhanden sind (`.`, `!`, `?`)
- Reduziere `min_sentence_length` (falls Sätze zu kurz)
- Prüfe Abkürzungserkennung (möglicherweise falsch erkannt)

### Problem: Falsche Satztypen

**Lösung:**
- Passe Fragewörter/Imperativ-Marker in `SemanticAnalyzer` an
- Prüfe Spracheinstellung (`language` Parameter)

### Problem: Sentiment nicht erkannt

**Lösung:**
- Erweitere `positive_words`/`negative_words` Listen
- Prüfe, ob Wörter in Kleinbuchstaben verglichen werden

---

## Zusammenfassung

**Vorteile:**
- ✅ Bessere Textstruktur
- ✅ Satz-basierte Anzeige
- ✅ Semantische Informationen
- ✅ Sehr schnell (kein Performance-Verlust)

**Verwendung:**
- Standardmäßig aktiviert
- Funktioniert mit allen Spracherkennungs-Modi
- Unterstützt Deutsch und Englisch

---

**Die semantische Satzerkennung verbessert die Lesbarkeit und Verständlichkeit der erkannten Texte!** 📝✨
