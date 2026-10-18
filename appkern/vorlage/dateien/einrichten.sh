#!/usr/bin/env bash
# Python-Umgebung, Pakete und Bau der Oberfläche; Appkern in Oberfläche und Backend auf denselben Commit; Git-Hooks
# (vor jedem Commit Fassung hochzählen und Zeichen und Stil prüfen).
set -euo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HIER/backend"
[ -x .venv/bin/python ] || python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
cd "$HIER/frontend"
npm install --no-audit --no-fund
cd "$HIER"
# frisch aus der Vorlage zeigt das Backend auf den Zweig main des Appkerns; festgelegt wird ein Commit (Lehre 5)
if grep -q "appkern/archive/refs/heads/main.tar.gz" backend/requirements.txt; then tools/appkern.sh; fi
if git rev-parse --git-dir >/dev/null 2>&1; then git config core.hooksPath tools/git-hooks; fi
cd "$HIER/frontend"
npm run build
echo "__NAME__ eingerichtet. Start: im Stellwerk oder backend/.venv/bin/uvicorn app.main:app --port __PORT__"
