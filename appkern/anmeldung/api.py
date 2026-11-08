"""Schnittstelle der Anmeldung für ein FastAPI-Backend (Zusatz `appkern[web]`) und die Abhängigkeiten, mit denen die
App ihre Endpunkte schützt.

Der Token der Kellerwolke kommt im Kopf `X-Kellerwolke-Sitzung`, der App-Schlüssel einer anderen App als
`Authorization: Bearer kw_app_...`. Für Inhaltsadressen (Ton, Bild, Download in `<audio>`
oder `<img>`, die keinen Kopf senden können) richtet `POST .../zugang` ein Cookie ein, das nur unter den Inhaltspfaden
gilt (`/api/v1/inhalt` und was die App dazu angibt; HttpOnly, SameSite strict).

Schickt eine andere App mit ihrem App-Schlüssel auf den Klick eines Menschen dessen Sitzung bei ihr mit, gilt der Aufruf
als der dieses Menschen (`Anmeldung.im_auftrag`); sonst als der der App.

Weist die App eine Anmeldung ab (401), sagt der Kopf `WWW-Authenticate: Kellerwolke-Sitzung` es; nur dann meldet sich
die Oberfläche ab. Ein 401, den eine App von einem anderen Dienst weiterreicht, beendet so nie die eigene Anmeldung.

Ohne Anmeldung (`Anmeldung.ohne_anmeldung`) sagt `GET` den festen Nutzer an, Anmelden und Koppeln antworten 409, Abmelden
und der Lesezugang tun nichts (Inhaltsadressen brauchen dann kein Cookie).
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Sequence
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from appkern.protokoll import Protokoll

from .dienst import APP_PRAEFIX, Anmeldung, AnmeldungsFehler, Konto

KOPF = "x-kellerwolke-sitzung"
ABGEWIESEN = {"WWW-Authenticate": "Kellerwolke-Sitzung"}     # Kennzeichen: diese App weist die Anmeldung ab
COOKIE = "app_inhalt"
INHALT_PFAD = "/api/v1/inhalt"                                  # Inhaltsadressen (Bilder, Töne) hinter dem Cookie


def inhalt_cookie(kennung: str) -> str:
    """Name des Inhalts-Cookies einer App (HELF-56). Ein Cookie gilt für den Rechner, nicht für den Port: alle Apps auf
    demselben Rechner (etwa der Pi mit Pinnwand, Leitstelle, Transkription) teilten sich sonst eines, und die zuletzt
    geöffnete App überschrieb es mit ihrer Sitzung; Bilder und Töne der anderen kamen dann nicht mehr. Darum trägt jede
    App ihre Kennung im Namen."""
    return f"{COOKIE}_{re.sub(r'[^a-z0-9]+', '_', kennung.lower()).strip('_') or 'app'}"
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
    kopf = {"Retry-After": str(f.nochmal_in)} if f.nochmal_in else {}
    if f.status == 401:
        kopf.update(ABGEWIESEN)
    return HTTPException(status_code=f.status, detail=f.meldung, headers=kopf or None)


def _bearer(request: Request) -> str:
    art, _, wert = request.headers.get("authorization", "").partition(" ")
    return wert.strip() if art.lower() == "bearer" else ""


def angemeldet(anmeldung: Anmeldung, *, cookie: bool | str = False, nur_menschen: bool = False,
               umleiten: str | None = None) -> Callable[[Request], Awaitable[Konto]]:
    """Abhängigkeit für geschützte Endpunkte; mit `cookie` auch für Inhaltsadressen (der Name des Inhalts-Cookies der
    App, siehe `inhalt_cookie`; `True` heißt der alte gemeinsame Name), mit `nur_menschen=True` ohne andere Apps, auch
    nicht im Auftrag eines Menschen (etwa Einstellungen mit Geheimnissen). Mit `umleiten` (etwa "/") führt ein Browser,
    der ohne Anmeldung eine Seite öffnet, dorthin zur Anmeldung, statt eine nackte Fehlermeldung zu sehen."""
    keks = COOKIE if cookie is True else (cookie or "")

    def abweisen(request: Request, fehler: HTTPException) -> HTTPException:
        seite = "text/html" in request.headers.get("accept", "")
        if umleiten is not None and fehler.status_code == 401 and request.method == "GET" and seite:
            return HTTPException(status_code=303, detail=fehler.detail, headers={"Location": umleiten})
        return fehler

    async def pruefen(request: Request) -> Konto:
        sitzung, bearer = request.headers.get(KOPF, ""), _bearer(request)
        try:
            if sitzung and bearer.startswith(APP_PRAEFIX):
                rufer = await anmeldung.pruefen(bearer)
                konto = (await anmeldung.im_auftrag(sitzung, rufer.app) if rufer and rufer.app else None) or rufer
            else:
                token = sitzung or bearer or (request.cookies.get(keks, "") if keks else "")
                konto = await anmeldung.pruefen(token)
        except AnmeldungsFehler as f:
            raise abweisen(request, _http(f))
        if konto is None:
            raise abweisen(request, HTTPException(status_code=401, detail="Anmeldung erforderlich", headers=ABGEWIESEN))
        if nur_menschen and (not konto.mensch or konto.im_auftrag):     # nur in der eigenen Oberfläche
            raise HTTPException(status_code=403, detail="Nur in der Oberfläche, nicht für andere Apps")
        return konto

    return pruefen


def anmeldungs_router(anmeldung: Anmeldung, *, prefix: str = "/api/v1/anmeldung",
                      inhalt_pfade: Sequence[str] = (INHALT_PFAD,), protokoll: Protokoll | None = None,
                      cookie: str = COOKIE) -> APIRouter:
    """Mit `protokoll` werden Anmelden, Koppeln, Abweisungen und Abmelden eingetragen (nie Passwörter oder Token).
    `cookie`: Name des Inhalts-Cookies der App (`inhalt_cookie(kennung)`), damit Apps auf demselben Rechner einander
    das Cookie nicht überschreiben. `inhalt_pfade`: unter diesen Pfaden schickt der Browser das Cookie mit (je Pfad ein
    Cookie gleichen Namens), etwa zusätzlich eine gebaute Seite, die die App hinter der Anmeldung ausliefert."""
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
        if anmeldung.ohne_anmeldung():
            response.status_code = 204                 # ohne Anmeldung gibt es nichts zu beenden
            return response
        token = request.headers.get(KOPF, "")
        try:
            konto = await anmeldung.pruefen(token)
        except AnmeldungsFehler:
            konto = None
        await anmeldung.abmelden(token)
        if konto is not None:
            await eintragen("anmeldung.abgemeldet", "Gerät getrennt" if konto.geraet else "Sitzung beendet", konto.name)
        for pfad in inhalt_pfade:
            response.delete_cookie(cookie, path=pfad, httponly=True, samesite="strict", secure=_https(request))
        response.status_code = 204
        return response

    @router.post("/zugang", status_code=204)
    async def zugang(request: Request, response: Response, konto: Konto = Depends(mensch)) -> Response:
        if anmeldung.ohne_anmeldung():
            response.status_code = 204                 # Inhaltsadressen gelten ohne Anmeldung auch ohne Cookie
            return response
        for pfad in inhalt_pfade:
            response.set_cookie(cookie, request.headers[KOPF], max_age=_ZUGANG_DAUER, path=pfad, httponly=True,
                                samesite="strict", secure=_https(request))
        response.status_code = 204
        return response

    return router


__all__ = ["ABGEWIESEN", "COOKIE", "INHALT_PFAD", "KOPF", "anmeldungs_router", "angemeldet", "inhalt_cookie"]
