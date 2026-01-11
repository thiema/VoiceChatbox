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

### 1.2 Audioausgabe (PCM5122 Audio Board + PAM8610 Verstärker + 4× Lautsprecher)

#### PCM5122 Audio Board (I2S-DAC HAT)
1. **Aufstecken auf Raspberry Pi**
   - Stecke das PCM5122 Audio Board direkt auf die **GPIO-Pins** des Raspberry Pi
   - Stelle sicher, dass alle Pins korrekt ausgerichtet sind (Pin 1 zu Pin 1)
   - Das Board wird über die GPIO-Pins versorgt (keine separate Stromversorgung nötig)
   - **WICHTIG:** Raspberry Pi vor dem Aufstecken ausschalten!
   - **📖 Detaillierte Pinout-Darstellung:** Siehe [docs/pcm5122-pinout.md](pcm5122-pinout.md)

2. **I2S aktivieren**
   ```bash
   sudo raspi-config
   # Navigiere zu: Interface Options → I2S → Enable
   # Reboot erforderlich
   ```

3. **Device Tree Overlay konfigurieren (falls nötig)**
   ```bash
   sudo nano /boot/config.txt
   # Füge am Ende hinzu (falls nicht vorhanden):
   dtoverlay=pcm512x
   # Oder für Hifiberry-kompatible Boards:
   # dtoverlay=hifiberry-dacplus
   # Speichern (Strg+O, Enter, Strg+X)
   sudo reboot
   ```

4. **Verifikation**
   ```bash
   # Prüfe, ob I2S-Gerät erkannt wurde
   aplay -l
   # PCM5122 sollte als Audio-Gerät erscheinen (z. B. "snd_rpi_pcm512x")
   
   # Prüfe Treiber
   lsmod | grep snd_soc_pcm512x
   ```

#### PAM8610 Verstärker
1. **Stromversorgung**
   - **WICHTIG:** Verstärker **nicht** aus GPIO-Pins speisen!
   - **Versorgungsspannung:** 8–15 V DC (empfohlen: 12 V)
   - Nutze eine separate 12V-Stromversorgung (z. B. 12V-Netzteil oder Powerbank)
   - **Gemeinsame Masse (GND)** mit Raspberry Pi verbinden
   - **Strombedarf:** Bis zu 2 A bei voller Leistung (abhängig von Lautstärke)

2. **Audio-Verbindung**
   - **PCM5122 Audio Board** hat **einen einzelnen Stereo-Audio-Ausgang** (meist 3.5mm Klinke)
   - **PAM8610 Verstärker** benötigt **zwei separate Eingänge** (L-In und R-In)
   - **Lösung:** Verwende ein **Y-Kabel** oder **Stereo-zu-Mono-Adapter**, um den Stereo-Ausgang in zwei Kanäle aufzuteilen
   - Verwende abgeschirmte Audio-Kabel für bessere Qualität

3. **Verdrahtung**
   ```
   PCM5122 (Stereo-Ausgang, 3.5mm) 
     ↓
   Y-Kabel / Adapter (Stereo → 2× Mono)
     ↓
   ├─→ PAM8610 (Audio-In L)
   └─→ PAM8610 (Audio-In R)
   
   PAM8610 (GND) → Raspberry Pi (GND)
   PAM8610 (VCC) → Externe 12V-Quelle (NICHT GPIO!)
   ```
   
   **Hinweis:** Das Y-Kabel teilt den Stereo-Ausgang in zwei separate Mono-Signale (Links und Rechts) auf.

4. **Hinweise zum PAM8610**
   - **Leistung:** 10 W pro Kanal (20 W gesamt)
   - **Lautstärke-Regelung:** Über Software (alsamixer) oder Hardware-Potis (falls vorhanden)
   - **Überhitzungsschutz:** Verstärker kann bei hoher Belastung warm werden

#### Lautsprecher (4× 4 Ω / 5 W Boxen)
1. **WICHTIG: Impedanz beachten!**
   - **PAM8610 unterstützt:** 4–8 Ω pro Kanal
   - **4×4 Ω parallel = 1 Ω** → **ZU NIEDRIG!** Verstärker wird überlastet!
   - **Empfohlene Konfigurationen:**
     - **Option A:** 1 Box pro Kanal (4 Ω) → **2 Boxen verwenden**
     - **Option B:** 2 Boxen pro Kanal in Reihe (8 Ω) → **4 Boxen verwenden**

2. **Anschluss (Option A: 1 Box pro Kanal - empfohlen)**
   - **Stereo-Konfiguration:** 1 Box links, 1 Box rechts
   - **Impedanz:** 4 Ω pro Kanal (optimal für PAM8610)
   - **Leistung:** 5 W pro Box (ausreichend für Sprach-TTS)

3. **Verdrahtung (Option A: 1 Box pro Kanal - empfohlen)**
   ```
   PAM8610 (Out L+) → Lautsprecher 1 (+)
   PAM8610 (Out L-) → Lautsprecher 1 (-)
   PAM8610 (Out R+) → Lautsprecher 2 (+)
   PAM8610 (Out R-) → Lautsprecher 2 (-)
   ```
   **Verwendung:** 2 von 4 Boxen

4. **Alternative: Reihenschaltung (Option B: 2 Boxen pro Kanal = 8 Ω)**
   ```
   PAM8610 (Out L+) → Lautsprecher 1 (+) → Lautsprecher 1 (-) → Lautsprecher 3 (+) → Lautsprecher 3 (-) → PAM8610 (Out L-)
   ```
   **Erklärung:** Lautsprecher 1 und 3 in Reihe (4 Ω + 4 Ω = 8 Ω)
   (Gleiches für Rechts-Kanal mit Lautsprecher 2 und 4)
   **Verwendung:** Alle 4 Boxen

4. **Polarität beachten**
   - **+ und - korrekt anschließen** für korrekte Phasenlage
   - Falsche Polarität führt zu schlechterer Klangqualität

5. **Sicherheitshinweise**
   - **Niedrige Lautstärke zum Testen:** Beginne mit niedriger Lautstärke (z. B. 20–30%)
   - **Überlastung vermeiden:** 
     - ❌ **NICHT:** 4×4 Ω parallel = 1 Ω (zu niedrig, Verstärker wird überlastet!)
     - ❌ **NICHT:** 2×4 Ω parallel = 2 Ω (zu niedrig für PAM8610)
     - ✅ **OK:** 1×4 Ω = 4 Ω pro Kanal
     - ✅ **OK:** 2×4 Ω in Reihe = 8 Ω pro Kanal
   - **Empfohlene Konfiguration:** 1 Box pro Kanal (4 Ω) für beste Performance
   - **Wärmeentwicklung:** PAM8610 kann bei hoher Lautstärke warm werden (normal)

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
- PCM5122 Audio Board sollte als Ausgabegerät erscheinen (z. B. "snd_rpi_pcm512x" oder ähnlich)

**Beispiel:**
```
ID   Name                                      Channels     Sample Rate Default
----------------------------------------------------------------------------------
0    bcm2835 HDMI/HDMI                        0 in / 2 out 44100       [OUT]
1    bcm2835 Headphones                        0 in / 2 out 44100       
2    XMOS XVF3800                             4 in / 0 out 48000       [IN]
3    snd_rpi_pcm512x                          0 in / 2 out 44100       [OUT]
```

### 2.2 Geräte-ID notieren

Notiere dir die **ID** (erste Spalte) von:
- **Eingabegerät:** ReSpeaker XVF3800 (z. B. ID 2)
- **Ausgabegerät:** PCM5122 Audio Board (z. B. ID 3, Name: "snd_rpi_pcm512x" oder ähnlich)

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
AUDIO_OUTPUT_DEVICE=pcm512x
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

3. **PCM5122 Audio Board prüfen:**
   - Ist das Board korrekt auf die GPIO-Pins aufgesteckt?
   - I2S aktiviert? (`sudo raspi-config` → Interface Options → I2S)
   - Prüfe mit: `aplay -l` (sollte PCM5122/pcm512x zeigen)

4. **PAM8610 Verstärker prüfen:**
   - **Stromversorgung:** 12V angeschlossen? (NICHT aus GPIO!)
   - **Gemeinsame Masse (GND)** mit Pi verbunden?
   - **Y-Kabel/Adapter:** Ist das Y-Kabel korrekt angeschlossen?
     - PCM5122 (Stereo-Ausgang) → Y-Kabel → PAM8610 (L-In und R-In)
   - Audio-Kabel von PCM5122 zu Verstärker korrekt?
   - Verstärker wird warm? (Normal bei Betrieb)

5. **Lautsprecher prüfen:**
   - Kabelverbindungen prüfen
   - Polarität (+/-) prüfen
   - **Impedanz prüfen:** Pro Kanal max. 1 Box (4 Ω) oder 2 Boxen in Reihe (8 Ω)
   - Lautsprecher direkt am Verstärker testen (niedrige Lautstärke!)

### Problem: Echo/Feedback

**Lösung:**
- Mikrofon und Lautsprecher **räumlich trennen**
- Lautstärke reduzieren
- Mikrofon-Richtung anpassen (weg vom Lautsprecher)

### Problem: Verzerrung

**Lösung:**
- Lautstärke reduzieren (in Software: `alsamixer` oder `amixer`)
- Prüfe, ob PAM8610 Verstärker übersteuert wird
- Prüfe, ob PCM5122 Line-Level korrekt ausgibt
- **Impedanz prüfen:** Zu niedrige Impedanz (z. B. 2 Ω bei 4×4 Ω parallel) kann Verzerrung verursachen
- **Empfehlung:** Pro Kanal nur 1 Box (4 Ω) verwenden

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
   Oder per Name:
   ```
   AUDIO_INPUT_DEVICE=XMOS
   AUDIO_OUTPUT_DEVICE=pcm512x
   ```

3. Testen:
   ```bash
   python -m src.audio_test --mic --device 2
   python -m src.audio_test --speaker --device 3
   ```

### Problem: PCM5122 wird nicht erkannt

**Lösung:**
1. **I2S aktivieren:**
   ```bash
   sudo raspi-config
   # Interface Options → I2S → Enable
   sudo reboot
   ```

2. **Treiber prüfen:**
   ```bash
   # Prüfe, ob Treiber geladen ist
   lsmod | grep snd_soc_pcm512x
   # Oder allgemein
   lsmod | grep snd
   ```

3. **Device Tree Overlay prüfen:**
   ```bash
   # Prüfe /boot/config.txt
   cat /boot/config.txt | grep -i pcm
   # Sollte enthalten: dtoverlay=hifiberry-dacplus oder ähnlich
   # Für PCM5122 könnte es sein: dtoverlay=pcm512x
   ```

4. **Manuell aktivieren (falls nötig):**
   ```bash
   sudo nano /boot/config.txt
   # Füge hinzu:
   dtoverlay=pcm512x
   # Oder für Hifiberry-kompatible Boards:
   dtoverlay=hifiberry-dacplus
   sudo reboot
   ```

5. **Nach Reboot prüfen:**
   ```bash
   aplay -l
   # PCM5122 sollte jetzt erscheinen
   ```

### Problem: Kein Ton trotz korrekter Verbindung

**Lösung:**
1. **Y-Kabel prüfen:**
   - Ist das Y-Kabel korrekt angeschlossen?
   - PCM5122 (Stereo-Ausgang) → Y-Kabel → PAM8610 (L-In und R-In)
   - Teste das Y-Kabel mit einem anderen Gerät

2. **Stereo vs. Mono:**
   - Stelle sicher, dass das Y-Kabel den Stereo-Ausgang korrekt in zwei Mono-Signale aufteilt
   - Links-Kanal → PAM8610 L-In
   - Rechts-Kanal → PAM8610 R-In

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

