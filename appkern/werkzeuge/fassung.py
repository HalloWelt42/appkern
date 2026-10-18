"""Fassung hochzählen: einzige Quelle ist version.json ({version, id, voll}); `id` vergibt nur eine neue Kennung."""

import json
import secrets
from pathlib import Path
from typing import Literal

Art = Literal["patch", "minor", "major", "id"]


def hochzaehlen(datei: Path, art: Art = "patch") -> str:
    d = json.loads(datei.read_text())
    major, minor, patch = (int(x) for x in d["version"].split("."))
    if art == "major":
        major, minor, patch = major + 1, 0, 0
    elif art == "minor":
        minor, patch = minor + 1, 0
    elif art == "patch":
        patch += 1
    d["version"] = f"{major}.{minor}.{patch}"
    d["id"] = secrets.token_hex(3)
    d["voll"] = f"v{d['version']}-{d['id']}"
    datei.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    return d["voll"]
