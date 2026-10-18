"""Befehle für die Entwicklung, im Wurzelordner einer App (oder des Appkerns) aufzurufen:

    python -m appkern.werkzeuge vor-dem-commit       Fassung hochzählen (nur neue Kennung, wenn version.json schon
                                                     vorgemerkt ist), vormerken, vorgemerkte Dateien prüfen
    python -m appkern.werkzeuge pruefen [PFAD ...]   Zeichen und Stil prüfen (ohne Pfade: alle Dateien im Repo)
    python -m appkern.werkzeuge fassung [patch|minor|major|id]
    python -m appkern.werkzeuge appkern              Appkern in Oberfläche und Backend auf den neuesten Commit heben
    python -m appkern.werkzeuge ausrollen            auf den Pi nach deploy/ausrollen.toml
"""

import argparse
import subprocess
import sys
from pathlib import Path

from .ausrollen import Abbruch, ausrollen
from .fassung import hochzaehlen
from .stil import schalen_klassen, stil_pruefen
from .stand import anheben
from .zeichen import zeichen_pruefen


def _git(*args: str, wurzel: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=wurzel, check=True, capture_output=True, text=True).stdout


def _wurzel() -> Path:
    return Path(_git("rev-parse", "--show-toplevel").strip())


def _schale(wurzel: Path) -> set[str] | None:
    """Klassen der Schale aus dem eingebundenen Appkern; None im Appkern selbst (dort ist der Stil die Schale)."""
    paket = wurzel / "frontend" / "node_modules" / "appkern-oberflaeche" / "oberflaeche"
    if (wurzel / "oberflaeche" / "stil" / "schale.css").is_file() or not paket.is_dir():
        return None
    return schalen_klassen(paket / "stil", paket / "teile")


def pruefen(wurzel: Path, dateien: list[Path]) -> int:
    befunde = zeichen_pruefen(dateien, wurzel) + stil_pruefen(dateien, wurzel, _schale(wurzel))
    for b in befunde:
        print(b, file=sys.stderr)
    if befunde:
        print(f"Abbruch: {len(befunde)} Befunde (Zeichen nur gerade, Stil ohne !important, einseitige Streifen und "
              "Regeln auf Klassen der Schale)", file=sys.stderr)
    return 1 if befunde else 0


def main(argv: list[str] | None = None) -> int:
    teiler = argparse.ArgumentParser(prog="python -m appkern.werkzeuge")
    befehle = teiler.add_subparsers(dest="befehl", required=True)
    befehle.add_parser("vor-dem-commit")
    p = befehle.add_parser("pruefen")
    p.add_argument("pfade", nargs="*", type=Path)
    f = befehle.add_parser("fassung")
    f.add_argument("art", nargs="?", default="patch", choices=["patch", "minor", "major", "id"])
    befehle.add_parser("appkern")
    befehle.add_parser("ausrollen")
    a = teiler.parse_args(argv)
    wurzel = _wurzel()

    if a.befehl == "fassung":
        print(hochzaehlen(wurzel / "version.json", a.art))
        return 0
    if a.befehl == "ausrollen":
        return ausrollen(wurzel)
    if a.befehl == "appkern":
        try:
            print(f"Appkern auf {anheben(wurzel)[:7]} (Oberfläche und Backend)")
        except Abbruch as f:
            print(f"Abbruch: {f}", file=sys.stderr)
            return 1
        return 0
    if a.befehl == "pruefen":
        if a.pfade:
            dateien = [q.resolve() for q in a.pfade for q in ([q] if q.is_file() else sorted(q.rglob("*")))]
        else:
            dateien = [wurzel / n for n in _git("ls-files", wurzel=wurzel).splitlines()]
        return pruefen(wurzel, dateien)
    # vor dem Commit
    vorgemerkt = _git("diff", "--cached", "--name-only", "--diff-filter=ACM", wurzel=wurzel).splitlines()
    hochzaehlen(wurzel / "version.json", "id" if "version.json" in vorgemerkt else "patch")
    _git("add", "version.json", wurzel=wurzel)
    return pruefen(wurzel, [wurzel / n for n in vorgemerkt])


if __name__ == "__main__":
    sys.exit(main())
