"""Sicherung von außen, im Abbild einer App aufgerufen, ohne dass die App dafür laufen muss:

    python -m appkern.sicherung vor-ausrollen --kennung pinnwand --datenbank /x/pinnwand.sqlite --ordner /x/sicherungen

Das Ausrollen ruft das vor dem Neustart (`appkern.werkzeuge.ausrollen.sichern`). Die Werte der Regel kommen wie in der
App aus ihren Einstellungen (gespeichert, dann `<KENNUNG>_SICHERUNG_...` aus der Umgebung, dann Vorgabe), nur lesend:
in die Datenbank schreibt dieser Aufruf nie. Gibt eine Zeile mit dem Ergebnis aus; Rückgabe 0, auch wenn keine neue
nötig war, 1 bei einem Fehler (dann bricht das Ausrollen ab).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path

from pydantic import ValidationError

from appkern.app.einstellungen import Grundeinstellungen
from appkern.app.sicherung import regel_aus
from appkern.einstellungen import nur_lesen

from .regel import Ablage, vor_ausrollen


def main(argv: list[str] | None = None) -> int:
    teiler = argparse.ArgumentParser(prog="python -m appkern.sicherung")
    befehle = teiler.add_subparsers(dest="befehl", required=True)
    v = befehle.add_parser("vor-ausrollen", help="sichern nach der Regel vor dem Ausrollen")
    v.add_argument("--kennung", required=True, help="Kennung der App (Name der Sicherungen, Vorsilbe der Umgebung)")
    v.add_argument("--datenbank", required=True, type=Path)
    v.add_argument("--ordner", required=True, type=Path, help="Ordner der Sicherungen")
    a = teiler.parse_args(argv)
    try:
        stand = nur_lesen(a.datenbank, Grundeinstellungen, umgebung_praefix=f"{a.kennung.upper()}_")
        ergebnis = vor_ausrollen(Ablage(a.datenbank, a.ordner, a.kennung), regel_aus(stand), time.time())
    except (OSError, sqlite3.Error, ValidationError, ValueError) as f:
        print(f"Sicherung gescheitert: {f}", file=sys.stderr)
        return 1
    print(ergebnis.zeile())
    return 0


if __name__ == "__main__":
    sys.exit(main())
