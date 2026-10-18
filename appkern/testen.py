"""Hilfen für die Tests der Apps (Lehren 18 und 20 der Transkription).

- Tests haben einen eigenen Zugang der Kellerwolke (App-Schlüssel und Konto nur in `backend/.env.test`), nie den der
  Entwicklungsinstanz: sonst melden die Tests deren Aktionen ohne Adresse neu, und "Öffnen" fehlt dort danach.
- Am Ende eines Laufs mit gestarteter App zieht `aktionen_zurueckziehen` die Aktionen des Testzugangs zurück, damit das
  Dateimenü der Kellerwolke nur echte Apps zeigt.
- `aufraeumen` legt Angelegtes in den Papierkorb: Dateien vor Ordnern, tiefe Ordner zuerst, mit Wiederholung; ein
  Ordner, der vor seinen Dateien drankommt, bliebe sonst liegen.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

from .kellerwolke import Kellerwolke, NichtGefunden

PFLICHT = ("KELLERWOLKE_ADRESSE", "KELLERWOLKE_SCHLUESSEL", "KELLERWOLKE_KENNUNG", "KELLERWOLKE_PASSWORT")


def werte(datei: Path) -> dict[str, str]:
    """Umgebung, ergänzt um die Zeilen `NAME=wert` aus `datei` (die Umgebung hat Vorrang)."""
    alle = dict(os.environ)
    if datei.is_file():
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            k, _, w = zeile.partition("=")
            if k.strip() and not k.lstrip().startswith("#"):
                alle.setdefault(k.strip(), w.strip())
    return alle


def hat_kellerwolke(w: dict[str, str]) -> bool:
    """Ein eigener Testzugang ist eingerichtet (sonst werden Verbundtests übersprungen)."""
    return all(w.get(k) for k in PFLICHT)


async def aufraeumen(kw: Kellerwolke, knoten: Iterable[UUID | str], versuche: int = 3) -> list[str]:
    """Legt die Knoten in den Papierkorb, Dateien vor Ordnern und tiefe Ordner vor flachen; was schon weg ist, zählt als
    erledigt. Zurück kommen die Kennungen, die auch nach `versuche` Läufen noch da sind."""
    offen = list(dict.fromkeys(str(k) for k in knoten))
    for lauf in range(versuche):
        bekannt = []
        for k in offen:
            try:
                bekannt.append(await kw.knoten(k))
            except NichtGefunden:
                continue
        bekannt.sort(key=lambda n: (n.typ == "ordner", -n.pfad.count("/")))
        offen = []
        for n in bekannt:
            try:
                await kw.loeschen(n.id)
            except NichtGefunden:
                continue
            except Exception:  # noqa: BLE001 - beim nächsten Lauf noch einmal
                offen.append(str(n.id))
        if not offen:
            return []
        await asyncio.sleep(0.2 * (lauf + 1))
    return offen


async def aktionen_zurueckziehen(adresse: str, schluessel: str) -> None:
    kw = Kellerwolke(adresse, schluessel)
    try:
        await kw.aktionen_melden([])
    finally:
        await kw.schliessen()
