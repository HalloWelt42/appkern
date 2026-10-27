#!/usr/bin/env bash
# Ausrollen auf den Pi (vom Mac aus) nach deploy/ausrollen.toml. Ablauf und Prüfungen stehen für alle Apps gleich im
# Appkern (appkern.werkzeuge.ausrollen): nur gepushte Stände, Tests grün, Appkern gleich in Oberfläche und Backend,
# mit Ton der Tondienst in der Leitstelle, Zertifikat, bauen, Datenbank sichern nach der Regel der Sicherung, neu
# starten, Fassungen, HTTP/2 und Symbole, danach Docker aufräumen. Rechner, Ordner, Adresse, Namen und Leitstelle kommen aus der privaten Wahrheit (handbuch ziel).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ergaenzung="$(mktemp)"
trap 'rm -f "$ergaenzung"' EXIT
handbuch ziel "$(pwd)" --toml > "$ergaenzung" || { echo "Abbruch: kein Ziel in der privaten Wahrheit (handbuch ziel)" >&2; exit 1; }
backend/.venv/bin/python -m appkern.werkzeuge ausrollen --ergaenzung "$ergaenzung" "$@"
