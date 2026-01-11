# Intelligente mehrsprachige Spracherkennung

Diese Dokumentation erklärt die intelligente mehrsprachige Spracherkennung, die Deutsch als Hauptsprache verwendet und Englisch nur für bestimmte ergänzende Wörter.

---

## Übersicht

Die intelligente mehrsprachige Spracherkennung löst zwei Hauptprobleme:

- ✅ **Doppelte Ausgabe verhindern:** Verhindert, dass erkannte Texte mehrfach ausgegeben werden
- ✅ **Intelligente Sprachkombination:** Deutsch primär, Englisch nur für bestimmte Wörter

---

## Funktionsweise

### 1. Doppelte Ausgabe verhindern

Das System prüft, ob ein neu erkannter Text bereits im aktuellen Text enthalten ist:

```python
# Prüfe, ob Text bereits am Ende des current_text steht
if current_lower.endswith(text_lower) or text_lower in current_lower[-len(text_lower)*2:]:
    # Überspringe, wenn bereits vorhanden
    return
```

**Beispiel:**
```
Chunk 1: "das ist ein"
current_text: "das ist ein"

Chunk 2: "das ist ein"  # Wird übersprungen (bereits vorhanden)
Chunk 3: "Text"         # Wird hinzugefügt
current_text: "das ist ein Text"
```

### 2. Intelligente Sprachkombination

**Strategie:**
1. **Deutsch als Hauptsprache:** Alle Transkriptionen werden primär mit dem deutschen Modell durchgeführt
2. **Englisch nur für bestimmte Wörter:** Das englische Modell wird nur verwendet, um bestimmte Wörter zu ergänzen/korrigieren
3. **Kontext-bewusst:** Semantische Analyse und Kontext-Erkennung basieren auf Deutsch

**Englische Wörter, die ergänzt werden:**
- Technik: `internet`, `computer`, `raspberry`, `pi`, `python`, `linux`, `wifi`, `software`, `hardware`, etc.
- Allgemein: `cool`, `okay`, `ok`, `yes`, `no`, `hello`, `hi`, `thanks`, `please`
- Medien: `youtube`, `facebook`, `twitter`, `instagram`, `whatsapp`, etc.
- Cloud: `aws`, `azure`, `google`, `microsoft`, `apple`, `amazon`, etc.

**Beispiel:**
```
Eingabe: "Der Raspberry Pi funktioniert nicht"
Deutsch: "Der raspberi pi funktioniert nicht"
Englisch: "the raspberry pi does not work"

Ergebnis: "Der Raspberry Pi funktioniert nicht"
         (Deutsch als Basis, "Raspberry Pi" aus Englisch korrigiert)
```

---

## Verwendung

### Aktivieren

```bash
# Intelligente mehrsprachige Erkennung
python -m src.main --live-recognition --vosk --smart-multilang
```

### Konfiguration

In `.env`:

```bash
# Deutsches Modell (erforderlich)
VOSK_MODEL_PATH=models/vosk-model-de-0.22

# Englisches Modell (optional, für Ergänzungen)
VOSK_MODEL_PATH_EN=models/vosk-model-en-us-0.22
```

### Vergleich mit Standard-Mehrsprachig

**Standard (`--multilang`):**
- Beide Modelle transkribieren parallel
- Wählt bestes Ergebnis oder kombiniert beide
- Kann zu gemischten Ergebnissen führen

**Intelligent (`--smart-multilang`):**
- Deutsch als Hauptsprache
- Englisch nur für bestimmte Wörter
- Bessere Konsistenz und Kontext-Erkennung

---

## Beispiel-Szenarien

### Szenario 1: Technische Begriffe

**Eingabe (gesprochen):**
```
"Der Raspberry Pi funktioniert nicht. Das Python Programm hat einen Fehler."
```

**Verarbeitung:**
```
Deutsch: "Der raspberi pi funktioniert nicht. Das piton programm hat einen fehler."
Englisch: "the raspberry pi does not work. the python program has an error."

Ergebnis: "Der Raspberry Pi funktioniert nicht. Das Python Programm hat einen Fehler."
```

### Szenario 2: Gemischte Sprache

**Eingabe (gesprochen):**
```
"Hallo, das ist cool. Der Computer funktioniert."
```

**Verarbeitung:**
```
Deutsch: "Hallo, das ist kuhl. Der computer funktioniert."
Englisch: "hello, that is cool. the computer works."

Ergebnis: "Hallo, das ist cool. Der Computer funktioniert."
         (Deutsch als Basis, "cool" und "Computer" aus Englisch korrigiert)
```

### Szenario 3: Doppelte Ausgabe verhindern

**Ohne Duplikat-Schutz:**
```
Chunk 1: "das ist ein"
Ausgabe: "das ist ein"

Chunk 2: "das ist ein"  # Wird nochmal hinzugefügt
Ausgabe: "das ist ein das ist ein"  ❌
```

**Mit Duplikat-Schutz:**
```
Chunk 1: "das ist ein"
Ausgabe: "das ist ein"

Chunk 2: "das ist ein"  # Wird erkannt und übersprungen
Ausgabe: "das ist ein"  ✅

Chunk 3: "Text"
Ausgabe: "das ist ein Text"  ✅
```

---

## Erweiterte Funktionen

### Englische Wörter hinzufügen

In `smart_multilang.py`:

```python
self.english_words.add('neues_wort')
```

### Ähnlichkeits-Schwellenwerte anpassen

```python
# In _merge_texts Methode
similarity = self._word_similarity(word_de, word_en)
if similarity > 0.7:  # Standard: 0.7
    # Korrigiere
```

---

## Performance

Die intelligente mehrsprachige Erkennung ist **etwas langsamer** als einfache Erkennung:

- **Deutsches Modell:** ~50-100ms pro Chunk
- **Englisches Modell:** ~50-100ms pro Chunk (optional)
- **Text-Merging:** < 5ms
- **Gesamt:** ~100-200ms pro Chunk (mit beiden Modellen)

**Tipp:** Wenn nur deutsche Erkennung benötigt wird, kann das englische Modell weggelassen werden.

---

## Troubleshooting

### Problem: Doppelte Ausgabe tritt weiterhin auf

**Lösung:**
- Prüfe, ob Chunk-Dauer zu kurz ist (erhöhe `chunk_duration`)
- Prüfe, ob Text-Erkennung zu ähnlich ist (Anpassung der Duplikat-Erkennung)

### Problem: Englische Wörter werden nicht korrigiert

**Lösung:**
- Prüfe, ob englisches Modell geladen wurde
- Füge Wort zur `english_words` Liste hinzu
- Prüfe Ähnlichkeits-Schwellenwerte

### Problem: Falsche Korrekturen

**Lösung:**
- Erhöhe Ähnlichkeits-Schwellenwerte (z.B. 0.8 statt 0.7)
- Prüfe, ob Wort wirklich in `english_words` Liste steht
- Deaktiviere englische Ergänzungen für bestimmte Wörter

---

## Zusammenfassung

**Vorteile:**
- ✅ Verhindert doppelte Ausgabe
- ✅ Deutsch als Hauptsprache für Kontext und Semantik
- ✅ Englisch nur für bestimmte Wörter
- ✅ Bessere Konsistenz

**Verwendung:**
```bash
python -m src.main --live-recognition --vosk --smart-multilang
```

---

**Die intelligente mehrsprachige Spracherkennung bietet die beste Balance zwischen Genauigkeit und Konsistenz!** 🎯✨
