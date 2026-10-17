"""Schnittstelle des Protokolls für ein FastAPI-Backend (Zusatz `appkern[web]`)."""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Query
from fastapi.params import Depends

from .dienst import Protokoll
from .modelle import Seite, Stufe


def protokoll_router(protokoll: Protokoll, *, prefix: str = "/api/v1/protokoll",
                     abhaengigkeiten: Sequence[Depends] = ()) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["protokoll"], dependencies=list(abhaengigkeiten))

    @router.get("", response_model=Seite)
    async def liste(ereignis: str | None = None, stufe: Stufe | None = None, bezug_id: str | None = None,
                    tag: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"), suche: str | None = None,
                    grenze: int = Query(100, ge=1, le=500), versatz: int = Query(0, ge=0)) -> Seite:
        return await protokoll.liste(ereignis=ereignis, stufe=stufe, bezug_id=bezug_id, tag=tag, suche=suche,
                                     grenze=grenze, versatz=versatz)

    return router


__all__ = ["protokoll_router"]
