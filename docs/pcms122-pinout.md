# PCM5122 Audio Board - GPIO Pinout & Anschluss

Diese Dokumentation zeigt die grafische/schematische Darstellung für den Anschluss des PCM5122 Audio Boards auf die GPIO-Pins des Raspberry Pi.

---

## Übersicht: PCM5122 auf Raspberry Pi

Das PCM5122 Audio Board wird **direkt auf die GPIO-Pins** des Raspberry Pi aufgesteckt (HAT-Format). Es nutzt das **I2S-Interface** für die Audio-Übertragung.

```
┌─────────────────────────────────────────┐
│                                         │
│         PCM5122 Audio Board             │
│         (I2S-DAC HAT)                   │
│                                         │
│    ┌─────────────────────────────┐     │
│    │                             │     │
│    │   PCM5122 DAC Chip         │     │
│    │                             │     │
│    └─────────────────────────────┘     │
│                                         │
│    [Line-Out L]  [Line-Out R]          │
│                                         │
└─────────────────────────────────────────┘
              │
              │ 40-Pin GPIO Header
              │
              ▼
┌─────────────────────────────────────────┐
│                                         │
│      Raspberry Pi 5 (40-Pin GPIO)       │
│                                         │
└─────────────────────────────────────────┘
```

---

## GPIO Pinout (Raspberry Pi 5 - 40 Pins)

### Ansicht von oben (Raspberry Pi)

```
     ┌─────────────────────────────────────┐
     │  [USB-C]  [HDMI]  [Ethernet]        │
     │                                     │
     │  ┌─────────────────────────────┐   │
     │  │                             │   │
     │  │   GPIO Header (40 Pins)     │   │
     │  │                             │   │
     │  └─────────────────────────────┘   │
     │                                     │
     └─────────────────────────────────────┘
```

### GPIO Pin-Belegung (für PCM5122)

```
     ┌─────────────────────────────────────┐
     │                                     │
     │  Pin 1  (3.3V)  ────────┐          │
     │  Pin 2  (5V)    ────────┤          │
     │  Pin 3  (SDA)           │          │
     │  Pin 4  (5V)    ────────┤          │
     │  Pin 5  (SCL)           │          │
     │  Pin 6  (GND)   ────────┼──────────┤ GND
     │  Pin 7  (GPIO7)         │          │
     │  Pin 8  (GPIO14)        │          │
     │  Pin 9  (GND)   ────────┼──────────┤ GND
     │  Pin 10 (GPIO15)        │          │
     │  Pin 11 (GPIO17)        │          │
     │  Pin 12 (GPIO18) ───────┼──────────┤ I2S BCLK
     │  Pin 13 (GPIO27)        │          │
     │  Pin 14 (GND)   ────────┼──────────┤ GND
     │  Pin 15 (GPIO22)        │          │
     │  Pin 16 (GPIO23)        │          │
     │  Pin 17 (3.3V)  ────────┼──────────┤ 3.3V
     │  Pin 18 (GPIO24)        │          │
     │  Pin 19 (GPIO10) ───────┼──────────┤ I2S MOSI
     │  Pin 20 (GND)   ────────┼──────────┤ GND
     │  Pin 21 (GPIO9)         │          │
     │  Pin 22 (GPIO25)        │          │
     │  Pin 23 (GPIO11)        │          │
     │  Pin 24 (GPIO8)         │          │
     │  Pin 25 (GND)   ────────┼──────────┤ GND
     │  Pin 26 (GPIO7)         │          │
     │  Pin 27 (ID_SD)         │          │
     │  Pin 28 (ID_SC)         │          │
     │  Pin 29 (GPIO5)         │          │
     │  Pin 30 (GND)   ────────┼──────────┤ GND
     │  Pin 31 (GPIO6)         │          │
     │  Pin 32 (GPIO12)        │          │
     │  Pin 33 (GPIO13)        │          │
     │  Pin 34 (GND)   ────────┼──────────┤ GND
     │  Pin 35 (GPIO19) ───────┼──────────┤ I2S LRCLK
     │  Pin 36 (GPIO16)        │          │
     │  Pin 37 (GPIO26)        │          │
     │  Pin 38 (GPIO20)        │          │
     │  Pin 39 (GND)   ────────┼──────────┤ GND
     │  Pin 40 (GPIO21)        │          │
     │                                     │
     └─────────────────────────────────────┘
```

---

## PCM5122 Pin-Zuordnung

### Wichtige Verbindungen

| PCM5122 Pin | Raspberry Pi Pin | Funktion | Beschreibung |
|-------------|------------------|----------|--------------|
| **VCC** | Pin 2 oder 4 | **5V** | Stromversorgung |
| **GND** | Pin 6, 9, 14, 20, 25, 30, 34, 39 | **GND** | Masse (mehrere Pins) |
| **3.3V** | Pin 1 oder 17 | **3.3V** | Logik-Versorgung |
| **BCLK** | Pin 12 (GPIO18) | **I2S BCLK** | Bit Clock (I2S) |
| **LRCLK** | Pin 35 (GPIO19) | **I2S LRCLK** | Left/Right Clock (I2S) |
| **DIN** | Pin 19 (GPIO10) | **I2S MOSI** | Data In (I2S) |
| **MCLK** | Pin 12 (GPIO18) | **I2S MCLK** | Master Clock (optional) |

### Schematische Darstellung

```
PCM5122 Audio Board
┌─────────────────────────────────────┐
│                                     │
│  ┌───────────────────────────────┐  │
│  │   PCM5122 DAC                 │  │
│  │                               │  │
│  │   VCC ────┐                   │  │
│  │   GND ────┼───┐               │  │
│  │   3.3V ───┼───┼───┐           │  │
│  │   BCLK ───┼───┼───┼───┐       │  │
│  │   LRCLK ──┼───┼───┼───┼───┐   │  │
│  │   DIN ────┼───┼───┼───┼───┼───┤  │
│  │           │   │   │   │   │   │  │
│  └───────────┼───┼───┼───┼───┼───┘  │
│              │   │   │   │   │       │
│              │   │   │   │   │       │
│  [Line-Out L]│   │   │   │   │       │
│  [Line-Out R]│   │   │   │   │       │
│              │   │   │   │   │       │
└──────────────┼───┼───┼───┼───┼───────┘
               │   │   │   │   │
               │   │   │   │   │
               ▼   ▼   ▼   ▼   ▼
Raspberry Pi GPIO Header
┌─────────────────────────────────────┐
│  Pin 2/4: 5V                       │
│  Pin 6/9/14/...: GND               │
│  Pin 1/17: 3.3V                    │
│  Pin 12: GPIO18 (BCLK)             │
│  Pin 35: GPIO19 (LRCLK)            │
│  Pin 19: GPIO10 (DIN)              │
└─────────────────────────────────────┘
```

---

## Aufsteck-Anleitung

### Schritt 1: Raspberry Pi ausschalten
```
⚠️  WICHTIG: Raspberry Pi VOR dem Aufstecken ausschalten!
```

### Schritt 2: Pin-Ausrichtung prüfen
```
PCM5122 Board:
┌─────────────┐
│             │
│  [Header]   │  ← 40-Pin Header (unten)
│             │
└─────────────┘

Raspberry Pi:
┌─────────────┐
│             │
│  [GPIO]     │  ← 40-Pin GPIO (oben)
│             │
└─────────────┘

Ausrichtung:
- Pin 1 (PCM5122) → Pin 1 (Raspberry Pi)
- Pin 2 (PCM5122) → Pin 2 (Raspberry Pi)
- ...
- Alle 40 Pins müssen korrekt ausgerichtet sein!
```

### Schritt 3: Aufstecken
```
1. Stelle sicher, dass alle Pins gerade ausgerichtet sind
2. Setze das Board vorsichtig auf die GPIO-Pins
3. Drücke gleichmäßig nach unten, bis alle Pins eingesteckt sind
4. Prüfe, dass das Board fest sitzt (nicht wackeln)
```

### Schritt 4: Verifikation
```bash
# Nach dem Booten prüfen:
aplay -l
# Sollte PCM5122/pcm512x zeigen

lsmod | grep snd_soc_pcm512x
# Sollte Treiber zeigen
```

---

## I2S Signal-Details

### Signal-Funktionen

| Signal | GPIO | Funktion | Beschreibung |
|--------|------|----------|--------------|
| **BCLK** | GPIO18 (Pin 12) | Bit Clock | Takt für einzelne Bits |
| **LRCLK** | GPIO19 (Pin 35) | Left/Right Clock | Wechselt zwischen L/R Kanal |
| **DIN** | GPIO10 (Pin 19) | Data In | Serielle Audio-Daten |
| **MCLK** | GPIO18 (Pin 12) | Master Clock | Optional, für höhere Qualität |

### Timing-Diagramm (vereinfacht)

```
BCLK:  ──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──┐ ┌──
         └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘ └─┘

LRCLK: ────────┐                   ┌───────
               └───────────────────┘
               (Left)              (Right)

DIN:   ──[D0][D1][D2][D3][D4][D5][D6][D7]──
       (Audio-Daten werden seriell übertragen)
```

---

## Stromversorgung

### PCM5122 Versorgung

```
Raspberry Pi GPIO:
├─ Pin 2 (5V) ────────┐
│                     │
├─ Pin 4 (5V) ───────┼──→ PCM5122 VCC (5V)
│                     │
├─ Pin 1 (3.3V) ──────┼──→ PCM5122 3.3V (Logik)
│                     │
└─ Pin 6/9/14/... ────┴──→ PCM5122 GND
   (GND)
```

**Hinweis:** Das PCM5122 Board wird vollständig über die GPIO-Pins versorgt. Keine separate Stromversorgung nötig!

---

## Audio-Ausgang

### Line-Out Anschlüsse

```
PCM5122 Audio Board
┌─────────────────────────┐
│                         │
│  [Line-Out L]  [Line-Out R]
│      │              │
│      │              │
└──────┼──────────────┼──────┘
       │              │
       │              │
       ▼              ▼
   PAM8610        PAM8610
   (L-In)         (R-In)
```

**Anschluss:**
- **Line-Out L** → PAM8610 Audio-In L
- **Line-Out R** → PAM8610 Audio-In R
- **GND** → Gemeinsame Masse mit PAM8610

---

## Troubleshooting

### Problem: PCM5122 wird nicht erkannt

**Prüfliste:**
1. ✅ Ist das Board korrekt aufgesteckt? (alle Pins)
2. ✅ Pin-Ausrichtung korrekt? (Pin 1 zu Pin 1)
3. ✅ I2S aktiviert? (`sudo raspi-config` → I2S → Enable)
4. ✅ Device Tree Overlay konfiguriert? (`dtoverlay=pcm512x` in `/boot/config.txt`)
5. ✅ Raspberry Pi neu gestartet?

### Problem: Kein Audio-Ausgang

**Prüfliste:**
1. ✅ Line-Out Kabel korrekt angeschlossen?
2. ✅ Lautstärke in Software eingestellt? (`alsamixer`)
3. ✅ Richtiges Ausgabegerät ausgewählt? (`aplay -l`)
4. ✅ PAM8610 Verstärker angeschlossen und mit Strom versorgt?

---

## Zusammenfassung

### Wichtige Pins für PCM5122

| Funktion | Raspberry Pi Pin | GPIO | Beschreibung |
|----------|------------------|------|--------------|
| **5V** | Pin 2 oder 4 | - | Stromversorgung |
| **GND** | Pin 6, 9, 14, 20, 25, 30, 34, 39 | - | Masse |
| **3.3V** | Pin 1 oder 17 | - | Logik-Versorgung |
| **I2S BCLK** | Pin 12 | GPIO18 | Bit Clock |
| **I2S LRCLK** | Pin 35 | GPIO19 | Left/Right Clock |
| **I2S DIN** | Pin 19 | GPIO10 | Data In |

### Aufsteck-Prozess

1. **Raspberry Pi ausschalten** ⚠️
2. **Pin-Ausrichtung prüfen** (Pin 1 zu Pin 1)
3. **Board aufstecken** (gleichmäßig, alle Pins)
4. **Raspberry Pi starten**
5. **I2S aktivieren** (`raspi-config`)
6. **Device Tree Overlay konfigurieren** (`/boot/config.txt`)
7. **Reboot und testen** (`aplay -l`)

---

**Viel Erfolg beim Aufbau!** 🎵

