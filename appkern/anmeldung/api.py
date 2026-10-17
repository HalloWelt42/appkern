"""Schnittstelle der Anmeldung für ein FastAPI-Backend (Zusatz `appkern[web]`) und die Abhängigkeiten, mit denen die
App ihre Endpunkte schützt.

Der Token der Kellerwolke kommt im Kopf `X-Kellerwolke-Sitzung`, der App-Schlüssel einer anderen App als
`Authorization: Bearer kw_app_...`. Für Inhaltsadressen (Ton, Bild, Download in `<audio>`
oder `<img>`, die keinen Kopf senden können) richtet `POST .../zugang` ein Cookie ein, das nur für `inhalt_pfad` gilt
(HttpOnly, SameSite strict).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from appkern.protokoll import Protokoll

from .dienst import Anmeldung, AnmeldungsFehler, Konto

KOPF = "x-kellerwolke-sitzung"
COOKIE = "app_inhalt"
_ZUGANG_DAUER = 30 * 24 * 3600


class AnmeldenEingabe(BaseModel):
    kennung: str
    passwort: str


class KoppelnEingabe(BaseModel):
    code: str
    name: str
    art: Literal["webapp", "browser"]


class Angemeldet(BaseModel):
    token: str
    konto: Konto


class Stand(BaseModel):
    angemeldet: bool
    konto: Konto | None = None


def _https(request: Request) -> bool:
    return request.url.scheme == "https" or request.headers.get("x-forwarded-proto", "") == "https"


def _http(f: AnmeldungsFehler) -> HTTPException:
    kopf = {"Retry-After": str(f.nochmal_in)} if f.nochmal_in else None
    return HTTPException(status_code=f.status, detail=f.meldung, headers=kopf)


def _bearer(request: Request) -> str:
    art, _, wert = request.headers.get("authorization", "").partition(" ")
    return wert.strip() if art.lower() == "bearer" else ""


def angemeldet(anmeldung: Anmeldung, *, cookie: bool = False,
               nur_menschen: bool = False) -> Callable[[Request], Awaitable[Konto]]:
    """Abhängigkeit für geschützte Endpunkte; mit `cookie=True` auch für Inhaltsadressen, mit `nur_menschen=True` ohne
    andere Apps (etwa Einstellungen mit Geheimnissen)."""

    async def pruefen(request: Request) -> Konto:
        token = request.headers.get(KOPF) or _bearer(request) or (request.cookies.get(COOKIE, "") if cookie else "")
        try:
            konto = await anmeldung.pruefen(token)
        except AnmeldungsFehler as f:
            raise _http(f)
        if konto is None:
            raise HTTPException(status_code=401, detail="Anmeldung erforderlich")
        if nur_menschen and not konto.mensch:
            raise HTTPException(status_code=403, detail="Nur in der Oberfläche, nicht für andere Apps")
        return konto

    return pruefen


def anmeldungs_router(anmeldung: Anmeldung, *, prefix: str = "/api/v1/anmeldung",
                      inhalt_pfad: str = "/api/v1/inhalt", protokoll: Protokoll | None = None) -> APIRouter:
    """Mit `protokoll` werden Anmelden, Koppeln, Abweisungen und Abmelden eingetragen (nie Passwörter oder Token)."""
    router = APIRouter(prefix=prefix, tags=["anmeldung"])
    mensch = angemeldet(anmeldung, nur_menschen=True)

    async def eintragen(ereignis: str, text: str, name: str | None = None, stufe: str = "info") -> None:
        if protokoll is not None:
            await protokoll.eintragen(ereignis, text, stufe=stufe, bezug_art="konto", bezug_name=name)

    @router.get("", response_model=Stand)
    async def stand(request: Request) -> Stand:
        try:
            konto = await anmeldung.pruefen(request.headers.get(KOPF, ""))
        except AnmeldungsFehler as f:
            raise _http(f)
        return Stand(angemeldet=konto is not None, konto=konto)

    @router.post("", response_model=Angemeldet)
    async def anmelden(eingabe: AnmeldenEingabe) -> Angemeldet:
        try:
            token, konto = await anmeldung.anmelden(eingabe.kennung, eingabe.passwort)
        except AnmeldungsFehler as f:
            await eintragen("anmeldung.abgewiesen", f.meldung, eingabe.kennung, "warnung")
            raise _http(f)
        await eintragen("anmeldung.angemeldet", "mit Passwort", konto.name)
        return Angemeldet(token=token, konto=konto)

    @router.post("/koppeln", response_model=Angemeldet, status_code=201)
    async def koppeln(eingabe: KoppelnEingabe) -> Angemeldet:
        try:
            token, konto = await anmeldung.koppeln(eingabe.code, eingabe.name, eingabe.art)
        except AnmeldungsFehler as f:
            await eintragen("anmeldung.abgewiesen", f.meldung, eingabe.name, "warnung")
            raise _http(f)
        await eintragen("anmeldung.gekoppelt", f"{eingabe.name}, {'Web-App' if eingabe.art == 'webapp' else 'Browser'}",
                        konto.name)
        return Angemeldet(token=token, konto=konto)

    @router.post("/abmelden", status_code=204)
    async def abmelden(request: Request, response: Response) -> Response:
        token = request.headers.get(KOPF, "")
        try:
            konto = await anmeldung.pruefen(token)
        except AnmeldungsFehler:
            konto = None
        await anmeldung.abmelden(token)
        if konto is not None:
            await eintragen("anmeldung.abgemeldet", "Gerät getrennt" if konto.geraet else "Sitzung beendet", konto.name)
        response.delete_cookie(COOKIE, path=inhalt_pfad, httponly=True, samesite="strict", secure=_https(request))
        response.status_code = 204
        return response

    @router.post("/zugang", status_code=204)
    async def zugang(request: Request, response: Response, konto: Konto = Depends(mensch)) -> Response:
        response.set_cookie(COOKIE, request.headers[KOPF], max_age=_ZUGANG_DAUER, path=inhalt_pfad, httponly=True,
                            samesite="strict", secure=_https(request))
        response.status_code = 204
        return response

    return router


__all__ = ["COOKIE", "KOPF", "anmeldungs_router", "angemeldet"]
