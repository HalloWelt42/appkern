"""Schnittstelle der Anfragen für ein FastAPI-Backend: Dateiwahl in der App und Öffnen aus der Kellerwolke.

Die Dateiwahl blättert mit der Anmeldung des Menschen an dieser App durch sein Konto (nur Namen und Eckdaten); die
Wahl stellt eine Anfrage, die der Abholer sofort übernimmt. Öffnen: die Kellerwolke führt den Browser zu
`<adresse>/anfrage/<id>`; die Oberfläche nimmt die Anfrage hier an und zeigt die Datei mit dem Recht dieser Anfrage.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from appkern.anmeldung.api import KOPF
from appkern.kellerwolke import Anfrage, Kellerwolke, KellerwolkeFehler, WahlSeite

from .dienst import Abholer

_STATUS = {401: 401, 403: 403, 404: 404, 409: 409, 422: 422}


class WahlEingabe(BaseModel):
    knoten_id: UUID
    aktion: str = Field(min_length=1, max_length=40)


class Gewaehlt(BaseModel):
    anfrage: Anfrage
    auftrag_id: str | None = None   # der Auftrag, der die Anfrage im Hintergrund ausführt


def _fehler(f: KellerwolkeFehler) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(f.status, 502), detail=f.meldung)


def anfragen_router(abholer: Abholer, kellerwolke: Callable[[], Kellerwolke | None], mensch: Any, *,
                    prefix: str = "/api/v1/kellerwolke") -> APIRouter:
    """`mensch` ist die Abhängigkeit für angemeldete Menschen (andere Apps wählen nicht)."""
    router = APIRouter(prefix=prefix, tags=["kellerwolke"])

    def zugang() -> Kellerwolke:
        kw = kellerwolke()
        if kw is None:
            raise HTTPException(status_code=503, detail="Keine Kellerwolke eingerichtet")
        return kw

    @router.get("/wahl", response_model=WahlSeite, dependencies=[mensch])
    async def wahl(request: Request, ordner: UUID | None = None) -> WahlSeite:
        try:
            return await zugang().wahl(request.headers.get(KOPF, ""), ordner)
        except KellerwolkeFehler as f:
            raise _fehler(f) from None

    @router.post("/wahl", response_model=Gewaehlt, dependencies=[mensch])
    async def waehlen(eingabe: WahlEingabe, request: Request) -> Gewaehlt:
        kw = zugang()
        try:
            neu = await kw.waehlen(request.headers.get(KOPF, ""), eingabe.knoten_id, eingabe.aktion)
            auftrag_id = await abholer.uebernehmen(neu.anfrage, kw) if neu.anfrage.art == "hintergrund" else None
            return Gewaehlt(anfrage=await kw.anfrage(neu.anfrage.id), auftrag_id=auftrag_id)
        except KellerwolkeFehler as f:
            raise _fehler(f) from None

    @router.get("/anfragen/{anfrage_id}", response_model=Anfrage, dependencies=[mensch])
    async def anfrage(anfrage_id: UUID) -> Anfrage:
        """Stand einer Anfrage an diese App (etwa die Frist einer geöffneten Datei)."""
        try:
            return await zugang().anfrage(anfrage_id)
        except KellerwolkeFehler as f:
            raise _fehler(f) from None

    @router.post("/anfragen/{anfrage_id}/oeffnen", response_model=Anfrage, dependencies=[mensch])
    async def oeffnen(anfrage_id: UUID) -> Anfrage:
        """Die Kellerwolke hat den Browser mit dieser Anfrage geschickt: annehmen, dann zeigt die App die Datei."""
        try:
            return await zugang().anfrage_annehmen(anfrage_id)
        except KellerwolkeFehler as f:
            raise _fehler(f) from None

    return router
