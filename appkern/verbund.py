"""Verbund: Aufrufe an andere Apps der Familie (Transkription, Vertonung, Fundus ...). Angemeldet wird mit dem
App-Schlüssel der Kellerwolke dieser App (Kopf Authorization), auf Wunsch im Auftrag der angemeldeten Person (Kopf
X-Kellerwolke-Sitzung): die andere App prüft dann deren Rechte wie in ihrer eigenen Oberfläche. Zertifikate prüft die
Zertifikatsstelle der App (wie für Kellerwolke und Leitstelle); eine Verbindung für alle Ziele, neu aufgebaut, wenn
sich Schlüssel oder Zertifikatsstelle ändern. Die Adresse jedes Ziels steht in einer Einstellung der App: `angebot`
bietet dafür die Apps des Verzeichnisses an, `anmelden` stellt das Ziel zu den Verbindungen (Fußleiste der Schale).

    v = geruest.verbund
    seite = (await v.anfrage("GET", adresse, "/api/v1/transkripte", sitzung=sitzung, params={"suche": "Dach"})).json()
    return await v.durchreichen(adresse, f"/api/v1/inhalt/transkripte/{tid}/ton", request, sitzung=sitzung)
    async with v.strom("POST", adresse, "/api/v1/sprechen/strom", sitzung=sitzung, json={"text": text}) as antwort:
        async for zeile in antwort.aiter_lines(): ...

Fehler kommen als `VerbundFehler` mit der Meldung des Ziels und seinem Status (ohne Status: nicht erreichbar oder nicht
eingerichtet). Wiederholt wird nichts von selbst.
"""

from __future__ import annotations

import logging
import ssl
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

import httpx
from fastapi import Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from appkern.einstellungen import Angebot, Option

if TYPE_CHECKING:
    from appkern.app.geruest import Geruest, Verbindung

logger = logging.getLogger("appkern.verbund")
ABFRAGE = httpx.Timeout(10.0)
ARBEIT = httpx.Timeout(10.0, read=None, write=60.0, pool=None)
SITZUNG = "X-Kellerwolke-Sitzung"
#: Köpfe, die beim Durchreichen von Inhalten mitgehen (hin: Bereiche; zurück: Art, Länge, Bereich, Zwischenspeicher)
HIN = ("range", "if-range")
ZURUECK = ("content-type", "content-length", "content-range", "accept-ranges", "etag", "last-modified", "cache-control",
           "content-disposition")


class VerbundFehler(Exception):
    """Ein Ziel antwortet mit einem Fehler oder ist nicht erreichbar; `meldung` in Worten, `status` wenn es eine
    Antwort gab."""

    def __init__(self, meldung: str, status: int | None = None) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        self.status = status


def meldung_aus(antwort: httpx.Response) -> str:
    """Der Grund einer Ablehnung in Worten (`detail` einer App des Appkerns, sonst der Anfang des Texts)."""
    try:
        detail = antwort.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        return "; ".join(str(d.get("msg", d)) for d in detail if isinstance(d, dict))[:300]
    return antwort.text[:300] or antwort.reason_phrase


def fassung_oder_verbunden(daten: Any) -> str:
    """Meldung einer Verbindung zu einer App des Appkerns: ihre Fassung aus /api/v1/app, sonst "verbunden"."""
    fassung = daten.get("fassung") if isinstance(daten, dict) else None
    return f"Fassung {fassung}" if fassung else "verbunden"


class Verbund:
    def __init__(self, geruest: Geruest, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.g = geruest
        self.transport = transport
        self._client: httpx.AsyncClient | None = None
        self._stand: tuple[str, str] | None = None
        self._alte: list[httpx.AsyncClient] = []              # nach einer Änderung: laufende Anfragen enden in Ruhe

    def _schluessel(self) -> str:
        return self.g.einstellungen.stand.kellerwolke_schluessel.get_secret_value()

    def client(self) -> httpx.AsyncClient:
        stand = (self._schluessel(), self.g.einstellungen.stand.ca_datei)
        if self._client is None or stand != self._stand:
            try:
                pruefung: ssl.SSLContext | bool = self.g.tls_pruefung()
            except (OSError, ssl.SSLError) as f:
                logger.warning("Zertifikatsstelle nicht lesbar: %s", f)
                pruefung = True
            if self._client is not None:
                self._alte.append(self._client)
            self._client = httpx.AsyncClient(timeout=ARBEIT, verify=pruefung, transport=self.transport)
            self._stand = stand
        return self._client

    async def schliessen(self) -> None:
        for c in [*self._alte, *([self._client] if self._client else [])]:
            await c.aclose()
        self._alte, self._client, self._stand = [], None, None

    def koepfe(self, sitzung: str | None = None) -> dict[str, str]:
        """Anmeldung mit dem App-Schlüssel, mit `sitzung` im Auftrag dieser Person."""
        kopf = {"Authorization": f"Bearer {self._schluessel()}"}
        if sitzung:
            kopf[SITZUNG] = sitzung
        return kopf

    def _ziel(self, adresse: str, pfad: str) -> str:
        if not adresse or not self._schluessel():
            raise VerbundFehler("nicht eingerichtet")
        return adresse.rstrip("/") + pfad

    async def anfrage(self, methode: str, adresse: str, pfad: str, *, sitzung: str | None = None,
                      timeout: httpx.Timeout = ARBEIT, **art: Any) -> httpx.Response:
        """Eine Anfrage am Stück; ab Status 400 ein `VerbundFehler` mit der Meldung des Ziels."""
        ziel = self._ziel(adresse, pfad)
        try:
            antwort = await self.client().request(methode, ziel, headers=self.koepfe(sitzung), timeout=timeout, **art)
        except httpx.TransportError as f:
            raise VerbundFehler(f"nicht erreichbar ({type(f).__name__})") from f
        if antwort.status_code >= 400:
            raise VerbundFehler(meldung_aus(antwort), antwort.status_code)
        return antwort

    @asynccontextmanager
    async def strom(self, methode: str, adresse: str, pfad: str, *, sitzung: str | None = None,
                    **art: Any) -> AsyncIterator[httpx.Response]:
        """Eine Antwort, die als Strom kommt (etwa Satz für Satz als NDJSON): lesen mit `aiter_lines` oder
        `aiter_bytes`; endet der Block, endet die Anfrage (bricht der Leser ab, hört das Ziel auf). Ab Status 400 ein
        `VerbundFehler` mit der Meldung des Ziels, bevor etwas gelesen wird."""
        ziel = self._ziel(adresse, pfad)
        client = self.client()
        try:
            antwort = await client.send(client.build_request(methode, ziel, headers=self.koepfe(sitzung), **art), stream=True)
        except httpx.TransportError as f:
            raise VerbundFehler(f"nicht erreichbar ({type(f).__name__})") from f
        try:
            if antwort.status_code >= 400:
                await antwort.aread()
                raise VerbundFehler(meldung_aus(antwort), antwort.status_code)
            yield antwort
        finally:
            await antwort.aclose()

    async def durchreichen(self, adresse: str, pfad: str, request: Request, *, sitzung: str | None = None) -> Response:
        """Einen Inhalt des Ziels an den Browser reichen, Stück für Stück und mit Bereichen (Range), damit ein Spieler
        in langen Aufnahmen springen kann, ohne alles zu laden."""
        ziel = self._ziel(adresse, pfad)
        kopf = self.koepfe(sitzung) | {k: v for k in HIN if (v := request.headers.get(k))}
        client = self.client()
        try:
            antwort = await client.send(client.build_request("GET", ziel, headers=kopf), stream=True)
        except httpx.TransportError as f:
            raise VerbundFehler(f"nicht erreichbar ({type(f).__name__})") from f
        if antwort.status_code >= 400:
            await antwort.aread()
            await antwort.aclose()
            raise VerbundFehler(meldung_aus(antwort), antwort.status_code)
        weiter = {k: antwort.headers[k] for k in ZURUECK if k in antwort.headers}
        if "content-encoding" in antwort.headers:                # entpackt weitergereicht: die Länge stimmt dann nicht
            weiter.pop("content-length", None)
        return StreamingResponse(antwort.aiter_bytes(), status_code=antwort.status_code, headers=weiter,
                                 background=BackgroundTask(antwort.aclose))

    def pruefung(self, name: str, adresse: Callable[[], str], pfad: str = "/api/v1/app",
                 meldung: Callable[[Any], str] | None = None) -> Callable[[], Awaitable[Verbindung]]:
        """Prüfung für die Liste der Verbindungen: ein lesender Aufruf, der nichts startet. `meldung` macht aus der
        Antwort (JSON, sonst None) den Text; ohne steht bei einer App des Appkerns ihre Fassung da."""
        from appkern.app.geruest import Verbindung

        async def pruefen() -> Verbindung:
            ziel = adresse()
            if not ziel:
                return Verbindung(name=name, ok=False, meldung="nicht eingerichtet")
            try:
                antwort = await self.anfrage("GET", ziel, pfad, timeout=ABFRAGE)
                daten = antwort.json() if antwort.headers.get("content-type", "").startswith("application/json") else None
            except VerbundFehler as f:
                return Verbindung(name=name, ok=False, adresse=ziel, meldung=f.meldung)
            return Verbindung(name=name, ok=True, adresse=ziel, meldung=(meldung or fassung_oder_verbunden)(daten))

        return pruefen

    def anmelden(self, name: str, adresse: Callable[[], str], pfad: str = "/api/v1/app",
                 meldung: Callable[[Any], str] | None = None) -> None:
        """Das Ziel zu den Verbindungen der App stellen (`/api/v1/verbindungen`, Fußleiste)."""
        self.g.verbindung_anmelden(name, self.pruefung(name, adresse, pfad, meldung))

    def angebot(self, name: str, kennung: str, adresse: Callable[[], str]) -> Callable[[], Awaitable[Angebot]]:
        """Anbieter für das Feld der Adresse eines Ziels: die eingetragene und die Apps des Verzeichnisses, deren
        Kennung `kennung` enthält; dazu, ob die Verbindung steht."""

        async def anbieter() -> Angebot:
            aktuell = adresse()
            optionen = [Option(wert=aktuell, titel=aktuell, hinweis="eingetragen")] if aktuell else []
            for e in await self.g.verzeichnis.alle():
                if kennung in e.kennung and e.adresse != aktuell:
                    optionen.append(Option(wert=e.adresse, titel=e.adresse, hinweis=f"{e.name} ({e.quelle})"))
            v = next((x for x in await self.g.verbindungen() if x.name == name), None)
            stand = "" if v is None else f"verbunden: {v.meldung}" if v.ok else f"nicht verbunden: {v.meldung}"
            return Angebot(optionen=optionen, stand=stand)

        return anbieter
