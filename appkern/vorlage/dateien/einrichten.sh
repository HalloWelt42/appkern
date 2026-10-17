#!/usr/bin/env bash
# Python-Umgebung, Pakete der Oberfläche, Bau der Oberfläche.
set -euo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HIER/backend"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
cd "$HIER/frontend"
npm install --no-audit --no-fund
npm run build
echo "__NAME__ eingerichtet. Start: im Stellwerk oder backend/.venv/bin/uvicorn app.main:app --port __PORT__"
