#!/usr/bin/env bash
# Version hochzählen: tools/version.sh [patch|minor|major|id]
# Einzige Quelle ist version.json ({version, id, voll}). "id" vergibt nur eine neue Build-Kennung.
set -euo pipefail
HIER="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATEI="$HIER/version.json"
ART="${1:-patch}"
python3 - "$DATEI" "$ART" <<'PY_ENDE_2d7c'
import json, secrets, sys, pathlib
datei, art = pathlib.Path(sys.argv[1]), sys.argv[2]
d = json.loads(datei.read_text())
major, minor, patch = (int(x) for x in d["version"].split("."))
if art == "major": major, minor, patch = major + 1, 0, 0
elif art == "minor": minor, patch = minor + 1, 0
elif art == "patch": patch += 1
elif art == "id": pass
else: sys.exit(f"unbekannte Art: {art}")
d["version"] = f"{major}.{minor}.{patch}"
d["id"] = secrets.token_hex(3)
d["voll"] = f"v{d['version']}-{d['id']}"
datei.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
print(d["voll"])
PY_ENDE_2d7c
