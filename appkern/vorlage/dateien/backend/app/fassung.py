"""Fassung der App aus version.json (einzige Quelle)."""

import json
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[2]
FASSUNG: str = json.loads((WURZEL / "version.json").read_text(encoding="utf-8"))["version"]
