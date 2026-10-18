#!/usr/bin/env bash
# Ausrollen auf den Pi (vom Mac aus) nach deploy/ausrollen.toml. Ablauf und Prüfungen stehen für alle Apps gleich im
# Appkern (appkern.werkzeuge.ausrollen): nur gepushte Stände, Tests grün, Appkern gleich in Oberfläche und Backend,
# mit Ton das ffmpeg des Pi, Zertifikat, Datenbank sichern, bauen, Vorschaltdienst neu starten, Fassungen, HTTP/2 und
# Symbole.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec backend/.venv/bin/python -m appkern.werkzeuge ausrollen
