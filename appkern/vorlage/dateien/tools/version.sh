#!/usr/bin/env bash
# Fassung hochzählen: tools/version.sh [patch|minor|major|id]. Einzige Quelle ist version.json ({version, id, voll});
# "id" vergibt nur eine neue Kennung. Gerechnet wird im Appkern (appkern.werkzeuge).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
exec backend/.venv/bin/python -m appkern.werkzeuge fassung "${1:-patch}"
