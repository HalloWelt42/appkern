#!/usr/bin/env bash
# Hebt den Appkern auf den neuesten Stand von GitHub, für Oberfläche und Backend auf denselben Commit (das Ausrollen
# prüft das). Ablauf im Appkern: appkern.werkzeuge.stand.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec backend/.venv/bin/python -m appkern.werkzeuge appkern
