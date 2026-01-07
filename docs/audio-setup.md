# Audio-Setup & Test-Anleitung

Diese Anleitung hilft dir beim Anschließen und Testen des Mikrofon-Arrays (ReSpeaker XVF3800) und der Audioausgabe (Soundkarte, Verstärker, Lautsprecher).

---

## 1. Hardware-Anschluss

### 1.1 Mikrofon-Array (ReSpeaker XVF3800)

1. **USB-Anschluss**
   - Stecke das ReSpeaker XVF3800 Mikrofon-Array in einen **USB-Port** des Raspberry Pi 5
   - Empfohlen: USB 3.0 Port (blaue Buchse) für bessere Performance
   - Das Gerät sollte automatisch erkannt werden

2. **Stromversorgung**
   - Das XVF3800 wird über USB versorgt
   - Keine zusätzliche Stromversorgung nötig

3. **Verifikation**
   ```bash
   # Prüfe, ob das Gerät erkannt wurde
   lsusb | grep -i xmos
   # Oder allgemein nach USB-Audio-Geräten
   lsusb | grep -i audio
   ```

### 1.2 Audioausgabe (Option A: USB-DAC + Verstärker + Lautsprecher)

#### USB-DAC
1. **USB-DAC anschließen**
   - Stecke den USB-DAC in einen USB-Port des Raspberry Pi
   - Warte einige Sekunden, bis das Gerät erkannt wurde

2. **Verifikation**
   ```bash
   # Prüfe USB-Geräte
   lsusb | grep -i audio
   ```

#### Verstärker (z. B. PAM8403)
1. **Stromversorgung**
   - **WICHTIG:** Verstärker **nicht** aus GPIO-Pins speisen!
   - Nutze eine separate 5V-Quelle (z. B. USB-Netzteil oder Powerbank)
   - **Gemeinsame Masse (GND)** mit Raspberry Pi verbinden

2. **Audio-Verbindung**
   - USB-DAC Line-Out → Verstärker Audio-In
   - Verstärker Audio-Out → Lautsprecher

3. **Verdrahtung**
   ```
   USB-DAC (Line-Out) → Verstärker (Audio-In)
   Verstärker (Audio-Out) → Lautsprecher (+ und -)
   Verstärker (GND) → Raspberry Pi (GND)
   Verstärker (5V) → Externe 5V-Quelle (NICHT GPIO!)
   ```

#### Lautsprecher
- **2"-3" Full-Range** Lautsprecher (z. B. Visaton FRS-5, 8Ω)
- Anschluss an Verstärker-Ausgang
- **Polarität beachten:** + und - korrekt anschließen

### 1.3 Audioausgabe (Option B: Aktive Lautsprecher)

1. **USB-Lautsprecher oder 3.5mm-Lautsprecher**
   - USB-Lautsprecher: Einfach in USB-Port stecken
   - 3.5mm-Lautsprecher: In 3.5mm-Ausgang des Pi stecken (falls vorhanden)
   - **Vorteil:** Kein Verstärker nötig

---

## 2. Software-Setup

### 2.1 Audio-Geräte auflisten

Führe das Audio-Testskript aus, um alle verfügbaren Geräte zu sehen:

```bash
source .venv/bin/activate
python -m src.audio_test --list
```

**Erwartete Ausgabe:**
- ReSpeaker XVF3800 sollte als Eingabegerät erscheinen (z. B. "XMOS XVF3800")
- USB-DAC oder Lautsprecher sollte als Ausgabegerät erscheinen

**Beispiel:**
```
ID   Name                                      Channels     Sample Rate Default
----------------------------------------------------------------------------------
0    bcm2835 HDMI/HDMI                        0 in / 2 out 44100       [OUT]
1    bcm2835 Headphones                        0 in / 2 out 44100       
2    XMOS XVF3800                             4 in / 0 out 48000       [IN]
3    USB Audio DAC                             0 in / 2 out 44100       [OUT]
```

### 2.2 Geräte-ID notieren

Notiere dir die **ID** (erste Spalte) von:
- **Eingabegerät:** ReSpeaker XVF3800 (z. B. ID 2)
- **Ausgabegerät:** USB-DAC oder Lautsprecher (z. B. ID 3)

### 2.3 Konfiguration in `.env`

Öffne die `.env` Datei und setze die Geräte:

```bash
nano .env
```

**Option 1: Geräte-ID verwenden**
```
AUDIO_INPUT_DEVICE=2
AUDIO_OUTPUT_DEVICE=3
```

**Option 2: Gerätename verwenden (Teilstring)**
```
AUDIO_INPUT_DEVICE=XMOS
AUDIO_OUTPUT_DEVICE=USB Audio
```

**Hinweis:** Wenn die Variablen nicht gesetzt sind, werden die Standard-Geräte verwendet.

---

## 3. Audio-Tests

### 3.1 Mikrofon-Test

Teste, ob das Mikrofon-Array funktioniert:

```bash
python -m src.audio_test --mic
```

**Mit spezifischem Gerät:**
```bash
python -m src.audio_test --mic --device 2
```

**Was passiert:**
- 3 Sekunden Aufnahme
- Live-Pegelanzeige in der Konsole
- Du solltest einen Balken sehen, der sich bewegt, wenn du sprichst

**Erwartetes Ergebnis:**
- ✓ Grüner Balken bewegt sich beim Sprechen
- Maximaler Pegel zwischen 0.01 und 0.5

**Probleme:**
- ⚠️ Sehr niedriger Pegel (< 0.01): Prüfe Anschluss und Geräteauswahl
- ⚠️ Sehr hoher Pegel (> 0.5): Möglicherweise zu laut, Verzerrung möglich

### 3.2 Lautsprecher-Test

Teste, ob die Audioausgabe funktioniert:

```bash
python -m src.audio_test --speaker
```

**Mit spezifischem Gerät:**
```bash
python -m src.audio_test --speaker --device 3
```

**Was passiert:**
- Ein 440 Hz Testton (Kammerton A) wird für 2 Sekunden abgespielt
- Du solltest einen Ton hören

**Erwartetes Ergebnis:**
- ✓ Du hörst einen klaren, gleichmäßigen Ton

**Probleme:**
- ⚠️ Kein Ton: Prüfe Anschlüsse, Lautstärke, Geräteauswahl
- ⚠️ Verzerrter Ton: Lautstärke zu hoch, Verstärker übersteuert

### 3.3 Aufnahme & Wiedergabe-Test

Teste die komplette Audio-Pipeline:

```bash
python -m src.audio_test --full
```

**Was passiert:**
1. Geräte werden aufgelistet
2. Mikrofon-Test (3 Sekunden)
3. Lautsprecher-Test (Testton)
4. Aufnahme & Wiedergabe (3 Sekunden Aufnahme, dann Wiedergabe)

**Erwartetes Ergebnis:**
- ✓ Du hörst deine eigene Stimme in der Wiedergabe
- ✓ Klare, verständliche Wiedergabe

**Probleme:**
- ⚠️ Echo/Feedback: Mikrofon und Lautsprecher zu nah beieinander
- ⚠️ Verzerrung: Lautstärke zu hoch
- ⚠️ Kein Ton: Prüfe Ausgabegerät

---

## 4. Troubleshooting

### Problem: Mikrofon wird nicht erkannt

**Lösung:**
```bash
# Prüfe USB-Verbindung
lsusb | grep -i xmos

# Prüfe Audio-Geräte
python -m src.audio_test --list

# Prüfe Berechtigungen
groups  # sollte 'audio' enthalten sein
```

**Falls nicht erkannt:**
- USB-Kabel prüfen
- Anderen USB-Port probieren
- Raspberry Pi neu starten
- `sudo usermod -a -G audio $USER` (dann neu einloggen)

### Problem: Lautsprecher gibt keinen Ton aus

**Lösung:**
1. **Lautstärke prüfen:**
   ```bash
   alsamixer
   # Oder
   amixer set Master 50%
   ```

2. **Geräteauswahl prüfen:**
   ```bash
   python -m src.audio_test --list
   # Stelle sicher, dass das richtige Ausgabegerät in .env steht
   ```

3. **Verstärker prüfen:**
   - Stromversorgung des Verstärkers prüfen
   - Gemeinsame Masse (GND) mit Pi prüfen
   - Verstärker nicht aus GPIO speisen!

4. **Lautsprecher prüfen:**
   - Kabelverbindungen prüfen
   - Polarität (+/-) prüfen
   - Lautsprecher direkt am Verstärker testen

### Problem: Echo/Feedback

**Lösung:**
- Mikrofon und Lautsprecher **räumlich trennen**
- Lautstärke reduzieren
- Mikrofon-Richtung anpassen (weg vom Lautsprecher)

### Problem: Verzerrung

**Lösung:**
- Lautstärke reduzieren (am Verstärker oder in Software)
- Prüfe, ob Verstärker übersteuert wird
- Prüfe, ob USB-DAC Line-Level ausgibt (nicht zu stark)

### Problem: Falsches Gerät wird verwendet

**Lösung:**
1. Geräte auflisten:
   ```bash
   python -m src.audio_test --list
   ```

2. Richtige ID in `.env` setzen:
   ```
   AUDIO_INPUT_DEVICE=2
   AUDIO_OUTPUT_DEVICE=3
   ```

3. Testen:
   ```bash
   python -m src.audio_test --mic --device 2
   python -m src.audio_test --speaker --device 3
   ```

---

## 5. Integration in Hauptprogramm

Nach erfolgreichen Tests sollte das Hauptprogramm automatisch die konfigurierten Geräte verwenden:

```bash
python -m src.main
```

Die Audio-Geräte werden aus der `.env` Datei geladen. Falls nicht gesetzt, werden die Standard-Geräte verwendet.

---

## 6. Nächste Schritte

Nach erfolgreichem Audio-Setup:
1. ✅ LED-Test: `python -m src.main --test-leds`
2. ✅ PTT-Test: `python -m src.main --test-ptt`
3. ✅ Vollständiger Test: `python -m src.main`

Viel Erfolg! 🎤🔊

