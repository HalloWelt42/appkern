"""Schnittstelle der Einstellungen für ein FastAPI-Backend (Zusatz `appkern[web]`)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from pydantic import BaseModel, ValidationError

from .dienst import Einstellungen, UnbekanntesFeld
from .modelle import Angebot, Feld


class Aenderung(BaseModel):
    werte: dict[str, Any]


class Geheimnis(BaseModel):
    name: str
    wert: str


def einstellungs_router(einstellungen: Einstellungen, *, prefix: str = "/api/v1/einstellungen",
                        abhaengigkeiten: Sequence[Depends] = ()) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["einstellungen"], dependencies=list(abhaengigkeiten))

    @router.get("", response_model=list[Feld])
    async def felder() -> list[Feld]:
        return einstellungen.felder()

    @router.patch("", response_model=list[Feld])
    async def aendern(eingabe: Aenderung) -> list[Feld]:
        try:
            await einstellungen.aendern(eingabe.werte)
        except UnbekanntesFeld as f:
            raise HTTPException(status_code=422, detail=f"Unbekannte Einstellung: {f.args[0]}")
        except ValidationError as f:
            fehler = "; ".join(f"{'.'.join(str(t) for t in e['loc'])}: {e['msg']}" for e in f.errors())
            raise HTTPException(status_code=422, detail=fehler)
        return einstellungen.felder()

    @router.get("/geheimnis/{name}", response_model=Geheimnis)
    async def geheimnis(name: str) -> Geheimnis:
        """Deckt ein Geheimnis auf (das Auge in der Oberfläche); verdeckt wird nur in der Anzeige."""
        try:
            return Geheimnis(name=name, wert=einstellungen.geheimnis(name))
        except UnbekanntesFeld:
            raise HTTPException(status_code=404, detail="Kein Geheimnis dieses Namens")

    @router.get("/angebot/{name}", response_model=Angebot)
    async def angebot(name: str) -> Angebot:
        """Was für ein Feld zur Wahl steht und was gerade gilt (live aus dem System)."""
        try:
            return await einstellungen.angebot(name)
        except UnbekanntesFeld:
            raise HTTPException(status_code=404, detail="Für dieses Feld gibt es kein Angebot")

    return router


__all__ = ["einstellungs_router"]
