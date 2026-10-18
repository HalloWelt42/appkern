"""Fehler der Bausteine als HTTP-Antworten, für jede App gleich: Kellerwolke, Leitstelle, Ton. Eine App nennt dazu nur
ihre eigenen Fehler mit Status (`eigene`); die Meldung ist der Text des Fehlers."""

from __future__ import annotations

from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..kellerwolke import (
    Gesperrt, KeinRecht, KellerwolkeFehler, NichtErreichbar, NichtGefunden, SchluesselUngueltig, StandVeraltet, ZuGross,
)
from ..leitstelle import LeitstellenFehler
from ..ton import TonFehler


def antwort(status: int, meldung: str, kopf: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse({"detail": meldung}, status_code=status, headers=kopf)


def kellerwolke_antwort(f: KellerwolkeFehler) -> JSONResponse:
    if isinstance(f, StandVeraltet):
        return antwort(409, "Inzwischen geändert: bitte neu laden und dann ändern")
    if isinstance(f, NichtGefunden):
        return antwort(404, f.meldung or "Nicht gefunden")
    if isinstance(f, KeinRecht):
        return antwort(403, f.meldung)
    if isinstance(f, Gesperrt):
        return antwort(423, f.meldung)
    if isinstance(f, ZuGross):
        return antwort(413, f.meldung)
    if isinstance(f, SchluesselUngueltig):
        return antwort(503, "Die Kellerwolke nimmt den App-Schlüssel nicht (Einstellungen prüfen)")
    if isinstance(f, NichtErreichbar):
        return antwort(503, "Die Kellerwolke ist gerade nicht erreichbar")
    return antwort(502, f"Kellerwolke: {f.meldung}")


def fehler_behandeln(app: FastAPI, eigene: Mapping[type[Exception], int] | None = None) -> None:
    @app.exception_handler(KellerwolkeFehler)
    async def kellerwolke(_: Request, f: KellerwolkeFehler):
        return kellerwolke_antwort(f)

    @app.exception_handler(LeitstellenFehler)
    async def leitstelle(_: Request, f: LeitstellenFehler):
        kopf = {"Retry-After": str(f.nochmal_in)} if f.nochmal_in else None
        return antwort(503 if f.status in (0, 503) else 502, f"Leitstelle: {f.meldung}", kopf)

    @app.exception_handler(TonFehler)
    async def ton(_: Request, f: TonFehler):
        return antwort(422, str(f))

    for art, status in (eigene or {}).items():
        def behandler(status: int = status):
            async def behandeln(_: Request, f: Exception):
                return antwort(status, str(f))
            return behandeln
        app.add_exception_handler(art, behandler())
