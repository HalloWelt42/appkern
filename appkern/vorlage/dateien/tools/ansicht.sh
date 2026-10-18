#!/usr/bin/env bash
# Ansichtsprüfung: jede Seite aus frontend/ansicht.json in allen Breiten, hell und dunkel; misst seitliches Rollen,
# Überlauf, Kontrast und Verschiebung beim Zustandswechsel (Werkzeug der gemeinsamen Oberfläche des Appkerns).
#   tools/ansicht.sh [adresse] [--ausgabe ORDNER] [--nur SEITE]     Vorgabe: die Entwicklungsinstanz
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ADRESSE="${1:-http://127.0.0.1:__PORT__}"
[ $# -gt 0 ] && shift
exec node frontend/node_modules/appkern-oberflaeche/oberflaeche/werkzeuge/ansicht.mjs "$ADRESSE" "$@"
