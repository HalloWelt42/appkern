"""Appkern: gemeinsame Bausteine der eigenen Apps. Jede App hält Dateien in der Kellerwolke und holt KI über die
Leitstelle; der Appkern bietet beides einmal, getestet, für alle.

Die Fassung steht in `version.json` im Wurzelordner; eine Installation legt sie als `VERSION` ins Paket.
"""

from __future__ import annotations

import json
from importlib import metadata
from pathlib import Path


def _fassung(paketordner: Path) -> str:
    """`VERSION` im Paket, `version.json` daneben (Quelle) oder die beim Bau eingetragene Fassung."""
    datei = paketordner / "VERSION"
    if datei.is_file():
        return datei.read_text(encoding="utf-8").strip()
    quelle = paketordner.parent / "version.json"
    if quelle.is_file():
        return json.loads(quelle.read_text(encoding="utf-8"))["version"]
    try:
        return metadata.version(paketordner.name)
    except metadata.PackageNotFoundError:
        return "0.0.0"


__version__ = _fassung(Path(__file__).resolve().parent)
