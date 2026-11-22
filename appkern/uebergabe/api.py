"""WebSocket der Übergabe: anmelden mit der ersten Nachricht, dann Nachrichten an den Vermittler (RAD-18)."""
from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from ..anmeldung.dienst import Anmeldung as Anmeldedienst, AnmeldungsFehler
from .vermittler import Anmeldung, Vermittler

logger = logging.getLogger(__name__)

#: so lange wartet die Verbindung auf die Anmeldung
ANMELDEN_S = 10
#: größte Nachricht in Zeichen (ein Zustand oder Paket ist klein)
MAX_NACHRICHT = 64_000


def uebergabe_router(vermittler: Vermittler, anmeldung: Anmeldedienst, *, pfad: str = "/api/v1/geraete") -> APIRouter:
    """`{pfad}/ws`: erste Nachricht {"typ": "anmelden", "token", "id", "geraet", "name", "art"}; danach die
    Nachrichten des Vermittlers. "ping" als Text beantwortet sie mit "pong" (hält Vorschaltdienste wach)."""
    router = APIRouter(prefix=pfad, tags=["Übergabe"])

    @router.websocket("/ws")
    async def geraete_ws(ws: WebSocket) -> None:
        await ws.accept()
        try:
            roh = await asyncio.wait_for(ws.receive_text(), ANMELDEN_S)
            gruss = Anmeldung.model_validate_json(roh[:MAX_NACHRICHT])
            konto = await anmeldung.pruefen(gruss.token)
        except (asyncio.TimeoutError, ValidationError, AnmeldungsFehler, WebSocketDisconnect):
            konto = None
        if konto is None or not konto.mensch:
            await ws.close(code=4401, reason="Anmeldung erforderlich")
            return
        await vermittler.beitreten(ws, gruss, raum=konto.id)
        try:
            while True:
                text = await ws.receive_text()
                if text == "ping":
                    await ws.send_text("pong")
                    continue
                if len(text) > MAX_NACHRICHT:
                    continue
                try:
                    await vermittler.behandeln(gruss.id, json.loads(text))
                except json.JSONDecodeError:
                    continue
        except WebSocketDisconnect:
            pass
        finally:
            await vermittler.verlassen(gruss.id, ws)

    return router
