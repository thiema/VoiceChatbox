#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[1/6] Systempakete installieren..."
sudo apt-get update
sudo apt-get install -y \
  python3-venv python3-dev \
  portaudio19-dev \
  ffmpeg \
  i2c-tools \
  git \
  build-essential

echo "[2/6] Python venv anlegen..."
cd "$PROJECT_DIR"
python3 -m venv .venv

echo "[3/6] Python requirements installieren..."
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "[4/6] .env vorbereiten..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  -> .env erstellt (bitte OPENAI_API_KEY eintragen)"
else
  echo "  -> .env existiert bereits"
fi

echo "[5/6] I2C aktivieren (optional, falls OLED genutzt wird)..."
# Hinweis: benötigt ggf. raspi-config; wir aktivieren nicht automatisch, sondern geben Anleitung aus
echo "  -> Falls OLED genutzt wird: 'sudo raspi-config' -> Interface Options -> I2C -> Enable"

echo "[6/6] Fertig."
echo "Nächste Schritte:"
echo "  1) nano .env (OPENAI_API_KEY eintragen)"
echo "  2) source .venv/bin/activate"
echo "  3) python -m src.main"
