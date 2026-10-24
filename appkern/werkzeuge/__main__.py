"""Befehle für die Entwicklung, im Wurzelordner einer App (oder des Appkerns) aufzurufen:

    python -m appkern.werkzeuge vor-dem-commit       Fassung hochzählen (nur neue Kennung, wenn version.json schon
                                                     vorgemerkt ist), vormerken, vorgemerkte Dateien prüfen
    python -m appkern.werkzeuge pruefen [PFAD ...]   Zeichen, Stil und Marken prüfen (ohne Pfade: alle Dateien im Repo)
    python -m appkern.werkzeuge marken [PFAD ...]    nur die Marken der Gestaltung, mit Zahl je Regel und Datei
    python -m appkern.werkzeuge fassung [patch|minor|major|id]
    python -m appkern.werkzeuge appkern              Appkern in Oberfläche und Backend auf den neuesten Commit heben
    python -m appkern.werkzeuge ausrollen [--ziel DATEI] [--ergaenzung DATEI] [--auslaufen]  auf den Pi nach deploy/ausrollen.toml (oder DATEI)
"""

import argparse
import subprocess
import sys
from pathlib import Path

from .ausrollen import ZIEL_DATEI, Abbruch, ausrollen
from .fassung import hochzaehlen
from .marken import marken_pruefen, strenge, zusammenfassung
from .stil import schalen_klassen, stil_pruefen
from .stand import anheben
from .zeichen import zeichen_pruefen


def _git(*args: str, wurzel: Path | None = None) -> str:
    return subprocess.run(["git", *args], cwd=wurzel, check=True, capture_output=True, text=True).stdout


def _wurzel() -> Path:
    return Path(_git("rev-parse", "--show-toplevel").strip())


def _schale(wurzel: Path) -> set[str] | None:
    """Klassen der Schale aus dem eingebundenen Appkern; None im Appkern selbst (dort ist der Stil die Schale) und in
    einer App mit eigener Schale (sie lädt den Stil des Appkerns nicht, nutzt nur seine Bausteine; dann kann keine
    ihrer Regeln die Schale mit ändern)."""
    paket = wurzel / "frontend" / "node_modules" / "appkern-oberflaeche" / "oberflaeche"
    if (wurzel / "oberflaeche" / "stil" / "schale.css").is_file() or not paket.is_dir():
        return None
    if not _laedt_stil(wurzel / "frontend" / "src"):
        return None
    return schalen_klassen(paket / "stil", paket / "teile")


def _laedt_stil(quellen: Path) -> bool:
    """Lädt die Oberfläche der App den Stil oder die Schale des Appkerns?"""
    for datei in quellen.rglob("*"):
        if datei.suffix in (".ts", ".js", ".svelte", ".css", ".html") and datei.is_file():
            text = datei.read_text(encoding="utf-8", errors="replace")
            if "appkern-oberflaeche/stil.css" in text or "<Schale" in text:
                return True
    return False


def pruefen(wurzel: Path, dateien: list[Path]) -> int:
    """Zeichen und Stil halten den Commit immer auf; die Marken der Gestaltung nur, wenn gestaltung.toml sie scharf
    schaltet, sonst werden sie gemeldet (so wird eine App erst sauber und dann scharf geschaltet)."""
    befunde = zeichen_pruefen(dateien, wurzel) + stil_pruefen(dateien, wurzel, _schale(wurzel))
    marken = marken_pruefen(dateien, wurzel)
    scharf = strenge(wurzel) == "scharf"
    for b in befunde + (marken if scharf else []):
        print(b, file=sys.stderr)
    if marken and not scharf:
        print(f"Hinweis: {len(marken)} Befunde der Gestaltung gemeldet ({zusammenfassung(marken)}); "
              "python -m appkern.werkzeuge marken zeigt sie, scharf in gestaltung.toml, sobald keiner mehr da ist",
              file=sys.stderr)
    alle = befunde + (marken if scharf else [])
    if alle:
        print(f"Abbruch: {len(alle)} Befunde (Zeichen nur gerade, Stil ohne !important, einseitige Streifen und "
              "Regeln auf Klassen der Schale" + (", nur Marken des Appkerns, Ausnahme mit Kommentar und Grund" if scharf else "")
              + ")", file=sys.stderr)
    return 1 if alle else 0


def marken_zeigen(wurzel: Path, dateien: list[Path]) -> int:
    marken = marken_pruefen(dateien, wurzel)
    je_datei: dict[str, int] = {}
    for b in marken:
        print(b)
        je_datei[b.datei] = je_datei.get(b.datei, 0) + 1
    for datei, zahl in sorted(je_datei.items(), key=lambda x: -x[1]):
        print(f"{zahl:5d}  {datei}")
    stufe = strenge(wurzel)
    print(f"{len(marken)} Befunde der Gestaltung ({zusammenfassung(marken) or 'keine'}); Strenge: {stufe}")
    return 1 if marken and stufe == "scharf" else 0


def main(argv: list[str] | None = None) -> int:
    teiler = argparse.ArgumentParser(prog="python -m appkern.werkzeuge")
    befehle = teiler.add_subparsers(dest="befehl", required=True)
    befehle.add_parser("vor-dem-commit")
    p = befehle.add_parser("pruefen")
    p.add_argument("pfade", nargs="*", type=Path)
    m = befehle.add_parser("marken")
    m.add_argument("pfade", nargs="*", type=Path)
    f = befehle.add_parser("fassung")
    f.add_argument("art", nargs="?", default="patch", choices=["patch", "minor", "major", "id"])
    befehle.add_parser("appkern")
    aus = befehle.add_parser("ausrollen")
    aus.add_argument("--sofort", action="store_true", help="nicht auf laufende Aufträge warten (bricht sie ab)")
    aus.add_argument("--auslaufen", action="store_true",
                     help="anhalten, den laufenden Schritt auslaufen lassen, ausrollen, danach weiter wie vorher ([auslaufen] im Ziel)")
    aus.add_argument("--ziel", type=Path, default=ZIEL_DATEI, metavar="DATEI",
                     help="Angaben des Ziels, relativ zum Ordner der App (Vorgabe deploy/ausrollen.toml)")
    aus.add_argument("--ergaenzung", type=Path, metavar="DATEI",
                     help="private Angaben des Hauses (TOML: rechner, wurzel, adresse, namen, leitstelle); füllt, was das Ziel nicht nennt")
    a = teiler.parse_args(argv)
    wurzel = _wurzel()

    if a.befehl == "fassung":
        print(hochzaehlen(wurzel / "version.json", a.art))
        return 0
    if a.befehl == "ausrollen":
        return ausrollen(wurzel, a.sofort, a.ziel, a.auslaufen, a.ergaenzung)
    if a.befehl == "appkern":
        try:
            print(f"Appkern auf {anheben(wurzel)[:7]} (Oberfläche und Backend)")
        except Abbruch as f:
            print(f"Abbruch: {f}", file=sys.stderr)
            return 1
        return 0
    if a.befehl in ("pruefen", "marken"):
        if a.pfade:
            dateien = [q.resolve() for q in a.pfade for q in ([q] if q.is_file() else sorted(q.rglob("*")))]
        else:
            dateien = [wurzel / n for n in _git("ls-files", wurzel=wurzel).splitlines()]
        return pruefen(wurzel, dateien) if a.befehl == "pruefen" else marken_zeigen(wurzel, dateien)
    # vor dem Commit
    vorgemerkt = _git("diff", "--cached", "--name-only", "--diff-filter=ACM", wurzel=wurzel).splitlines()
    hochzaehlen(wurzel / "version.json", "id" if "version.json" in vorgemerkt else "patch")
    _git("add", "version.json", wurzel=wurzel)
    return pruefen(wurzel, [wurzel / n for n in vorgemerkt])


if __name__ == "__main__":
    sys.exit(main())
