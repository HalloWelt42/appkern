"""Wege der Mitteilungen unter /api/v1/push: der öffentliche Schlüssel, das Abo dieses Geräts melden oder entfernen,
die Geräte der angemeldeten Person, eine Probe an alle ihre Geräte und der Dienst im Browser (dienst.js)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, params
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..anmeldung.dienst import Konto
from .dienst import Abo, Geraet, Mitteilung, Push, Versand

DIENST_JS = Path(__file__).with_name("dienst.js")


class Schluessel(BaseModel):
    schluessel: str


class AboEingabe(BaseModel):
    abo: Abo
    #: wie das Gerät in der Liste heißt ("iPhone, Web-App")
    geraet: str = Field("", max_length=80)


class Endpunkt(BaseModel):
    endpunkt: str = Field(max_length=2000)


class Entfernt(BaseModel):
    entfernt: bool


def push_router(push: Push, mensch: params.Depends, name: str) -> APIRouter:
    """`mensch`: Abhängigkeit, die nur angemeldete Menschen durchlässt; `name`: Name der App für die Probe."""
    r = APIRouter(prefix="/api/v1/push", tags=["push"])

    @r.get("/schluessel", response_model=Schluessel)
    async def schluessel(_konto: Konto = mensch) -> Schluessel:
        return Schluessel(schluessel=await push.oeffentlich())

    @r.get("/geraete", response_model=list[Geraet])
    async def geraete(konto: Konto = mensch) -> list[Geraet]:
        return await push.geraete(konto.id)

    @r.post("/abo", response_model=Geraet)
    async def abo(eingabe: AboEingabe, konto: Konto = mensch) -> Geraet:
        return await push.abo_setzen(konto.id, eingabe.abo, eingabe.geraet)

    @r.post("/abo/entfernen", response_model=Entfernt)
    async def abo_entfernen(eingabe: Endpunkt, konto: Konto = mensch) -> Entfernt:
        return Entfernt(entfernt=await push.entfernen(konto.id, endpunkt=eingabe.endpunkt))

    @r.delete("/geraete/{geraet_id}", response_model=Entfernt)
    async def geraet_entfernen(geraet_id: str, konto: Konto = mensch) -> Entfernt:
        if not await push.entfernen(konto.id, geraet=geraet_id):
            raise HTTPException(404, detail="Dieses Gerät bekommt keine Mitteilungen (mehr)")
        return Entfernt(entfernt=True)

    @r.post("/probe", response_model=Versand)
    async def probe(konto: Konto = mensch) -> Versand:
        """Eine Probe an alle Geräte der Person: so sieht man, dass Mitteilungen ankommen."""
        return await push.senden(konto.id, Mitteilung(titel=name, text="Probe: Mitteilungen kommen auf diesem Gerät an.",
                                                      tag="probe"))

    @r.get("/dienst.js", include_in_schema=False)
    async def dienst() -> Response:
        return Response(DIENST_JS.read_text(encoding="utf-8"), media_type="text/javascript",
                        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})

    return r
