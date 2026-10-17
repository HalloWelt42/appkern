"""Neue App aus der Vorlage (Ordner `dateien`): Backend auf dem Gerüst, Oberfläche in der gemeinsamen Schale,
Symbolsatz für alle Geräte, Eintrag fürs Stellwerk, Tests und Verbundtest.

    python -m appkern.vorlage --name Transkription --kennung transkription --rolle "macht aus Ton Text" \\
        --symbol fa-closed-captioning --port 8601 --ziel ~/Entwicklung/Apps

Mit `--appkern-lokal <Pfad>` zeigen Backend und Oberfläche auf eine lokale Arbeitskopie des Appkerns statt auf GitHub
(zum Entwickeln am Appkern selbst).
"""

from __future__ import annotations

import colorsys
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DATEIEN = Path(__file__).resolve().parent / "dateien"
REPO = Path(__file__).resolve().parents[2]
GITHUB_PY = "appkern[web] @ https://github.com/HalloWelt42/appkern/archive/refs/heads/main.tar.gz"
GITHUB_NPM = "github:HalloWelt42/appkern"
_KENNUNG = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
_SYMBOL = re.compile(r"^fa-[a-z0-9-]+$")
_FARBE = re.compile(r"^#[0-9a-fA-F]{6}$")
SVG = "http://www.w3.org/2000/svg"


class VorlagenFehler(ValueError):
    pass


def _dunkler(farbe: str, faktor: float = 0.72) -> str:
    r, g, b = (int(farbe[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb(h, l * faktor, s)
    return "#" + "".join(f"{round(x * 255):02x}" for x in (r, g, b))


def _glyphe(symbol: str, ordner: Path | None) -> tuple[str, str] | None:
    """(viewBox, Pfad) des Font-Awesome-Symbols aus den SVG-Dateien des npm-Pakets, sonst None."""
    kandidaten = [ordner] if ordner else []
    kandidaten.append(REPO / "node_modules" / "@fortawesome" / "fontawesome-free" / "svgs")
    for basis in kandidaten:
        for art in ("solid", "regular", "brands"):
            datei = basis / art / f"{symbol.removeprefix('fa-')}.svg"
            if datei.is_file():
                wurzel = ET.fromstring(datei.read_text(encoding="utf-8"))
                pfad = next((k for k in wurzel.iter() if k.tag.endswith("path")), None)
                if pfad is not None:
                    return wurzel.get("viewBox", "0 0 512 512"), pfad.get("d", "")
    return None


def symbol_svg(name: str, symbol: str, farbe: str, ordner: Path | None = None) -> str:
    """Quelle des Symbolsatzes: abgerundetes Quadrat mit Verlauf der App-Farbe, darauf das Symbol in Weiß (oder der
    Anfangsbuchstabe, wenn das Symbol nicht zu finden ist)."""
    kopf = (f'<svg xmlns="{SVG}" viewBox="0 0 512 512"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{farbe}"/><stop offset="1" stop-color="{_dunkler(farbe)}"/></linearGradient></defs>'
            f'<rect width="512" height="512" rx="112" fill="url(#g)"/>')
    glyphe = _glyphe(symbol, ordner)
    if glyphe is None:
        return (kopf + f'<text x="256" y="256" dy="0.35em" text-anchor="middle" font-family="Helvetica, Arial, sans-serif" '
                f'font-weight="700" font-size="300" fill="#fff">{name[:1].upper()}</text></svg>')
    vx, vy, vb, vh = (float(z) for z in glyphe[0].split())
    massstab = 280 / max(vb, vh)
    x, y = 256 - vb * massstab / 2, 256 - vh * massstab / 2
    return (kopf + f'<path fill="#fff" transform="translate({x:.2f} {y:.2f}) scale({massstab:.4f}) translate({-vx:g} {-vy:g})" '
            f'd="{glyphe[1]}"/></svg>')


def _python_mit_cairosvg() -> str | None:
    """Ein Python mit cairosvg und Pillow (nur zum Erzeugen der Bilder nötig); auf dem Mac liegen mehrere."""
    kandidaten = [sys.executable, *(shutil.which(n) for n in ("python3", "python3.13", "python3.12")),
                  "/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"]
    for kandidat in dict.fromkeys(k for k in kandidaten if k):
        try:
            if subprocess.run([kandidat, "-c", "import cairosvg, PIL"], capture_output=True).returncode == 0:
                return kandidat
        except OSError:
            continue
    return None


def erzeugen(*, name: str, kennung: str, rolle: str, symbol: str, port: int, ziel: Path, devport: int | None = None,
             farbe: str = "#2f7ce0", appkern_lokal: Path | None = None, symbole_ordner: Path | None = None) -> Path:
    if not _KENNUNG.match(kennung):
        raise VorlagenFehler("Kennung: Kleinbuchstaben, Ziffern und Bindestrich, mit einem Buchstaben vorn")
    if not _SYMBOL.match(symbol):
        raise VorlagenFehler("Symbol: Name eines Font-Awesome-Symbols wie fa-closed-captioning")
    if not _FARBE.match(farbe):
        raise VorlagenFehler("Farbe: #rrggbb")
    if not (1024 <= port <= 65535) or (devport is not None and not (1024 <= devport <= 65535)):
        raise VorlagenFehler("Ports zwischen 1024 und 65535")
    ordner = Path(ziel).expanduser().resolve() / kennung
    if ordner.exists():
        raise VorlagenFehler(f"{ordner} gibt es schon")
    shutil.copytree(DATEIEN, ordner, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    (ordner / "gitignore").rename(ordner / ".gitignore")

    lokal = Path(appkern_lokal).expanduser().resolve() if appkern_lokal else None
    ersetzen = {
        "__NAME__": name, "__KENNUNG__": kennung, "__ROLLE__": rolle, "__SYMBOL__": symbol, "__PORT__": str(port),
        "__DEVPORT__": str(devport or port + 1000), "__FARBE__": farbe, "__ORDNER__": str(ordner),
        "__APPKERN_PY__": f"-e {lokal}[web]" if lokal else GITHUB_PY,
        "__APPKERN_NPM__": f"file:{lokal}" if lokal else GITHUB_NPM,
    }
    for datei in ordner.rglob("*"):
        if not datei.is_file():
            continue
        try:
            text = datei.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        neu = text
        for platzhalter, wert in ersetzen.items():
            neu = neu.replace(platzhalter, wert)
        if neu != text:
            datei.write_text(neu, encoding="utf-8")

    (ordner / "frontend" / "public" / "symbol.svg").write_text(symbol_svg(name, symbol, farbe, symbole_ordner), encoding="utf-8")
    python = _python_mit_cairosvg()
    if python:
        subprocess.run([python, str(ordner / "tools" / "symbole.py")], check=True, capture_output=True)
    return ordner


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m appkern.vorlage", description="Neue App aus der Vorlage des Appkerns")
    p.add_argument("--name", required=True, help="Name der App, etwa Transkription")
    p.add_argument("--kennung", required=True, help="technische Kennung, etwa transkription")
    p.add_argument("--rolle", required=True, help='was die App tut, als Satzende: "macht aus Ton Text"')
    p.add_argument("--symbol", required=True, help="Font-Awesome-Symbol, etwa fa-closed-captioning")
    p.add_argument("--port", required=True, type=int, help="Port des Backends")
    p.add_argument("--devport", type=int, help="Port der Oberfläche beim Entwickeln (Vorgabe: Port + 1000)")
    p.add_argument("--farbe", default="#2f7ce0", help="Farbe des Symbols (#rrggbb)")
    p.add_argument("--ziel", required=True, type=Path, help="Ordner, in dem die App als Unterordner entsteht")
    p.add_argument("--appkern-lokal", type=Path, help="lokale Arbeitskopie des Appkerns statt GitHub")
    a = p.parse_args(argv)
    try:
        ordner = erzeugen(name=a.name, kennung=a.kennung, rolle=a.rolle, symbol=a.symbol, port=a.port, devport=a.devport,
                          farbe=a.farbe, ziel=a.ziel, appkern_lokal=a.appkern_lokal)
    except VorlagenFehler as f:
        print(f"Nicht erzeugt: {f}", file=sys.stderr)
        return 2
    symbole = (ordner / "frontend" / "public" / "apple-touch-icon.png").is_file()
    print(f"{a.name} angelegt in {ordner}")
    if not symbole:
        print("Symbolsatz noch erzeugen: python3 tools/symbole.py (braucht cairosvg und Pillow)")
    print(f"Weiter: cd {ordner} && ./einrichten.sh; Stellwerk-Eintrag: stellwerk.toml nach ~/Stellwerk/apps/{a.kennung}.toml")
    return 0
