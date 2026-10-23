"""Hilfen für die Tests der Apps (Lehren 18 und 20 der Transkription).

- Tests haben einen eigenen Zugang der Kellerwolke (App-Schlüssel und Konto nur in `backend/.env.test`), nie den der
  Entwicklungsinstanz: sonst melden die Tests deren Aktionen ohne Adresse neu, und "Öffnen" fehlt dort danach.
- Am Ende eines Laufs mit gestarteter App zieht `aktionen_zurueckziehen` die Aktionen des Testzugangs zurück, damit das
  Dateimenü der Kellerwolke nur echte Apps zeigt.
- `aufraeumen` legt Angelegtes in den Papierkorb: Dateien vor Ordnern, tiefe Ordner zuerst, mit Wiederholung; ein
  Ordner, der vor seinen Dateien drankommt, bliebe sonst liegen.
- `Tondienst` ist der echte Tondienst im Prozess (rechnet hier mit ffmpeg) für eine nachgestellte Leitstelle: der
  Verbundtest geht denselben Weg wie der Betrieb (Tonarbeit über die Leitstelle), ohne Mac.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from pathlib import Path
from uuid import UUID

# In Tests fällt eine fehlende Kellerwolke sofort auf, statt dass jeder Aufruf die Geduld des Betriebs (15 min) abwartet;
# muss vor dem Laden des Zugangs gesetzt sein, darum hier beim Import der Testhilfen.
os.environ.setdefault("APPKERN_KELLERWOLKE_GEDULD_S", "0")

import httpx

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


def hat_kellerwolke(w: dict[str, str], frist_s: float = 5.0) -> bool:
    """Ein eigener Testzugang ist eingerichtet und die Kellerwolke der Entwicklung antwortet darauf (sonst werden
    Verbundtests übersprungen, wie die Tests mit Docker ohne Docker: ein abgeschalteter Teil der Entwicklung ist kein
    Fehler der App)."""
    return all(w.get(k) for k in PFLICHT) and kellerwolke_antwortet(w["KELLERWOLKE_ADRESSE"], w["KELLERWOLKE_SCHLUESSEL"], frist_s)


def kellerwolke_antwortet(adresse: str, schluessel: str, frist_s: float = 5.0) -> bool:
    """Die Kellerwolke unter `adresse` nimmt den App-Schlüssel an (für Verbundtests: sonst überspringen)."""
    try:
        antwort = httpx.get(f"{adresse.rstrip('/')}/api/v1/ablage/ich", timeout=frist_s, headers={"Authorization": f"Bearer {schluessel}"})
    except httpx.HTTPError:
        return False
    return antwort.status_code == 200


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


class Tondienst:
    """Der Tondienst einer nachgestellten Leitstelle: `zustaendig(request)` sagt, ob eine Anfrage ihm gilt
    (`/v1/dienste/<name>/...`), `transport` beantwortet sie mit den echten Routen und `TonHier`."""

    def __init__(self, ablage: Path, name: str = "klangwerk-ton") -> None:
        import httpx
        from fastapi import FastAPI

        from .ton import TonHier
        from .ton.gegenseite import routen

        self.praefix = f"/v1/dienste/{name}/"
        app = FastAPI()
        app.include_router(routen(TonHier(), ablage), prefix=self.praefix.rstrip("/"))
        self.transport = httpx.ASGITransport(app=app)

    def zustaendig(self, request) -> bool:
        return request.url.path.startswith(self.praefix)
