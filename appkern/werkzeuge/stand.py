"""Appkern einer App auf den neuesten Stand von GitHub heben, für Oberfläche und Backend auf denselben Commit
(Lehre 5 der Transkription): die Oberfläche über package-lock.json, das Backend über requirements.txt (Archiv dieses
Commits statt `main.tar.gz`, das sich nie ändert und Docker die alte Schicht nehmen lässt). Das Ausrollen prüft die
Gleichheit."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .ausrollen import Abbruch, appkern_staende

ZEILE = re.compile(r"appkern(\[[^\]]*\])? @ https://github\.com/HalloWelt42/appkern/archive/[^\s]+\.tar\.gz")


def anheben(wurzel: Path) -> str:
    anforderungen = wurzel / "backend" / "requirements.txt"
    text = anforderungen.read_text()
    if not ZEILE.search(text):
        raise Abbruch("requirements.txt bindet den Appkern nicht von GitHub ein (lokale Arbeitskopie?)")
    subprocess.run(["npm", "install", "--no-audit", "--no-fund", "appkern-oberflaeche@github:HalloWelt42/appkern"],
                   cwd=wurzel / "frontend", check=True, capture_output=True)
    commit, _ = appkern_staende(wurzel)
    neu = ZEILE.sub(lambda m: f"appkern{m.group(1) or ''} @ https://github.com/HalloWelt42/appkern/archive/{commit}.tar.gz", text)
    anforderungen.write_text(neu)
    subprocess.run([".venv/bin/pip", "install", "-q", "-r", "requirements.txt"], cwd=wurzel / "backend", check=True)
    return commit
