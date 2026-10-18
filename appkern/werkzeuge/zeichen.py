"""Nur gerade Zeichen: keine Gedankenstriche und keine typografischen Anführungszeichen in Texten und Code."""

import re
from pathlib import Path

from .befund import Befund

MUSTER = re.compile("[\u2013\u2014\u201c\u201d\u201e\u2018\u2019]")
ENDUNGEN = (".md", ".html", ".js", ".mjs", ".ts", ".svelte", ".py", ".css", ".json", ".sh", ".toml", ".yml", ".yaml")


def zeichen_pruefen(dateien: list[Path], wurzel: Path) -> list[Befund]:
    befunde: list[Befund] = []
    for p in dateien:
        if not p.name.endswith(ENDUNGEN) or "node_modules" in p.parts or not p.is_file():
            continue
        for nr, text in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if MUSTER.search(text):
                befunde.append(Befund(datei=str(p.relative_to(wurzel)), zeile=nr, regel="typografisches Zeichen", text=text.strip()))
    return befunde
