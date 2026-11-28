"""Gegenseite des Erkennen-Dienstes (Protokoll in `dienst.py`): die Route, die im Dienst auf dem Mac läuft (Wirt: Bildwerk,
Dienst `bild-erkennen`). Nimmt das Bild an, lässt `ErkennenHier` rechnen und antwortet mit `Erkannt`."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .dienst import BILD_FEHLER
from .modelle import Erkannt, Erkennen
from .rechnen import BildFehler, ErkennenHier

GROESSE = 64 * 1024 * 1024


def routen(hier: ErkennenHier, *, gleichzeitig: int = 2) -> APIRouter:
    """Höchstens `gleichzeitig` Bilder rechnen nebeneinander; die übrigen warten."""
    sperre = asyncio.Semaphore(gleichzeitig)
    r = APIRouter(tags=["bild_erkennen"])

    def fehler(code: int, grund: str, meldung: str) -> JSONResponse:
        return JSONResponse(status_code=code, content={"error": {"code": grund, "message": meldung[:500]}})

    @r.post("/erkennen", response_model=Erkannt)
    async def erkennen(bild: UploadFile = File(...), auftrag: str = Form("{}")):
        try:
            a = Erkennen.model_validate_json(auftrag or "{}")
        except ValidationError as f:
            return fehler(422, "auftrag", f"Der Auftrag passt nicht: {f.errors()[0]['msg']}")
        inhalt = await bild.read(GROESSE + 1)
        if not inhalt:
            return fehler(422, BILD_FEHLER, "Das Bild ist leer")
        if len(inhalt) > GROESSE:
            return fehler(413, BILD_FEHLER, "Das Bild ist größer als 64 MB")
        async with sperre:
            try:
                return await asyncio.to_thread(hier.erkennen, inhalt, a)
            except BildFehler as f:
                return fehler(422, BILD_FEHLER, str(f))

    return r
