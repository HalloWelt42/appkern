"""Schnittstelle der Aufträge für ein FastAPI-Backend (Zusatz `appkern[web]`).

Anlegen ist Sache der App (sie prüft ihre Eingaben in eigenen Endpunkten und ruft `einreihen`); hier gibt es
Liste, Zahlen je Zustand, Stand, Abbrechen, Wiederholen, Entfernen und den Ereignisstrom, für alle Apps gleich.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.params import Depends as Abhaengigkeit
from fastapi.responses import StreamingResponse

from .dienst import Auftraege, FalscherZustand, NichtGefunden, UnbekannteArt
from .modelle import Auftrag, Seite, Zahlen, Zustand

HERZSCHLAG_S = 15.0


async def _niemand() -> str:
    return ""


def auftrags_router(auftraege: Auftraege, *, prefix: str = "/api/v1/auftraege",
                    abhaengigkeiten: Sequence[Abhaengigkeit] = (), wer: Callable[..., Awaitable[str]] = _niemand) -> APIRouter:
    """`abhaengigkeiten` etwa für die Anmeldung der App (gelten für jeden Endpunkt); `wer`: Abhängigkeit, die den Namen
    des Aufrufers liefert (wer wiederholt, steht dann am neuen Auftrag)."""
    router = APIRouter(prefix=prefix, tags=["auftraege"], dependencies=list(abhaengigkeiten))

    def _fehler(f: Exception) -> HTTPException:
        if isinstance(f, NichtGefunden):
            return HTTPException(status_code=404, detail="Auftrag nicht gefunden")
        if isinstance(f, (FalscherZustand, UnbekannteArt)):
            return HTTPException(status_code=409, detail=str(f))
        raise f

    @router.get("", response_model=Seite)
    async def liste(zustand: list[Zustand] = Query(default=[]), art: str | None = None, stapel: str | None = None,
                    suche: str | None = None, grenze: int = Query(50, ge=1, le=500),
                    versatz: int = Query(0, ge=0)) -> Seite:
        return await auftraege.liste(zustand=zustand, art=art, stapel=stapel, suche=suche, grenze=grenze,
                                     versatz=versatz)

    @router.get("/zahlen", response_model=Zahlen)
    async def zahlen() -> Zahlen:
        """Wie viele Aufträge in jedem Zustand sind (eine Abfrage für Kopf und Navigation)."""
        return await auftraege.zahlen()

    @router.get("/ereignisse")
    async def ereignisse() -> StreamingResponse:
        """Server-Sent Events: `event: auftrag` mit dem Auftrag als JSON; Kommentarzeilen halten die Verbindung."""

        async def strom():
            async for auftrag in auftraege.ereignisse(HERZSCHLAG_S):
                if auftrag is None:
                    yield b": lebt\n\n"
                else:
                    yield f"event: auftrag\ndata: {auftrag.model_dump_json()}\n\n".encode()

        return StreamingResponse(strom(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @router.get("/{auftrag_id}", response_model=Auftrag)
    async def stand(auftrag_id: str) -> Auftrag:
        try:
            return await auftraege.holen(auftrag_id)
        except Exception as f:  # noqa: BLE001
            raise _fehler(f)

    @router.post("/{auftrag_id}/abbrechen", response_model=Auftrag)
    async def abbrechen(auftrag_id: str) -> Auftrag:
        try:
            return await auftraege.abbrechen(auftrag_id)
        except Exception as f:  # noqa: BLE001
            raise _fehler(f)

    @router.post("/{auftrag_id}/wiederholen", response_model=Auftrag, status_code=201)
    async def wiederholen(auftrag_id: str, von: str = Depends(wer)) -> Auftrag:
        try:
            return await auftraege.wiederholen(auftrag_id, von=von or None)
        except Exception as f:  # noqa: BLE001
            raise _fehler(f)

    @router.delete("/{auftrag_id}", status_code=204)
    async def entfernen(auftrag_id: str) -> Response:
        try:
            await auftraege.entfernen(auftrag_id)
        except Exception as f:  # noqa: BLE001
            raise _fehler(f)
        return Response(status_code=204)

    return router


__all__ = ["auftrags_router"]
