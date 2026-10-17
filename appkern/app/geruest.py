"""Gerüst einer App: verdrahtet die Bausteine des Appkerns einmal, damit jede App nur noch ihr Fachliches schreibt.

    geruest = Geruest(name="Transkription", kennung="transkription", rolle="macht aus Ton Text", fassung="0.1.0",
                      daten=Path("daten"), einstellungen=TranskriptionEinstellungen, arten=[...],
                      oberflaeche=Path("../frontend/dist"))
    app = geruest.fastapi()
    app.include_router(eigener_router)          # mit Depends(geruest.pflicht)

Was das Gerüst übernimmt: Datenbank, Einstellungen (Grundeinstellungen plus die der App), Protokoll, Aufträge,
Anmeldung mit dem Kellerwolke-Konto (Besitzer ist das Konto des App-Schlüssels), Zugänge zu Kellerwolke und Leitstelle
(nach jeder Änderung der Einstellungen neu aufgebaut), App-Verzeichnis, Prüfung der Verbindungen, erste Einrichtung
(nur vom Rechner selbst, solange keine Kellerwolke eingetragen ist), tägliches Aufräumen, Auslieferung der gebauten
Oberfläche.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generic, TypeVar

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import appkern
from appkern.anmeldung import Anmeldung, Konto
from appkern.anmeldung.api import angemeldet, anmeldungs_router
from appkern.auftraege import Art, Auftraege
from appkern.auftraege.api import auftrags_router
from appkern.datenbank import Datenbank
from appkern.einstellungen import Einstellungen
from appkern.einstellungen.api import einstellungs_router
from appkern.kellerwolke import Kellerwolke, KellerwolkeFehler
from appkern.leitstelle import Leitstelle, LeitstellenFehler
from appkern.leitstelle.zugang import ARBEIT
from appkern.protokoll import Protokoll
from appkern.protokoll.api import protokoll_router
from appkern.verzeichnis import Verzeichnis

from .einstellungen import Grundeinstellungen

logger = logging.getLogger("appkern.app")
E = TypeVar("E", bound=Grundeinstellungen)
LOKAL = {"127.0.0.1", "::1", "localhost"}
TAG_S = 24 * 3600


class AppInfo(BaseModel):
    name: str
    kennung: str
    rolle: str
    symbol: str
    fassung: str
    appkern: str
    einrichtung_noetig: bool
    besitzer: str | None = None


class Verbindung(BaseModel):
    name: str
    ok: bool
    adresse: str = ""
    meldung: str = ""


class Einrichtung(BaseModel):
    kellerwolke_adresse: str = Field(min_length=1)
    kellerwolke_schluessel: str = Field(min_length=1)


class Geruest(Generic[E]):
    def __init__(self, *, name: str, kennung: str, rolle: str, fassung: str, daten: Path, einstellungen: type[E],
                 arten: Sequence[Art] = (), symbol: str = "fa-cube", oberflaeche: Path | None = None,
                 gleichzeitig: int = 1, transport: httpx.AsyncBaseTransport | None = None) -> None:
        """`transport` nur für Tests: alle Verbindungen nach außen gehen dann über ihn."""
        self.name, self.kennung, self.rolle, self.symbol, self.fassung = name, kennung, rolle, symbol, fassung
        self.daten = Path(daten)
        self.oberflaeche = oberflaeche
        self._transport = transport
        self.db = Datenbank(self.daten / f"{kennung}.sqlite")
        self.einstellungen: Einstellungen[E] = Einstellungen(self.db, einstellungen, umgebung_praefix=f"{kennung.upper()}_")
        self.protokoll = Protokoll(self.db)
        self.auftraege = Auftraege(self.db, arten, gleichzeitig=gleichzeitig, protokoll=self.protokoll)
        self.verzeichnis = Verzeichnis()
        self.besitzer: str | None = None
        self.kellerwolke: Kellerwolke | None = None
        self.leitstelle: Leitstelle | None = None
        self._clients: list[httpx.AsyncClient] = []
        self.anmeldung = Anmeldung("", self._erlaubt)
        self.pflicht = Depends(angemeldet(self.anmeldung))
        self.lesen = Depends(angemeldet(self.anmeldung, cookie=True))
        self._pflege: asyncio.Task | None = None

    # --- Zugänge ----------------------------------------------------------------------------------------------

    def _erlaubt(self) -> set[str]:
        if not self.besitzer:
            return set()
        return {self.besitzer, *self.einstellungen.stand.weitere_konten}

    def _pruefung(self) -> ssl.SSLContext | bool:
        ca = self.einstellungen.stand.ca_datei.strip()
        if not ca:
            return True
        kontext = ssl.create_default_context()
        kontext.load_verify_locations(Path(ca).expanduser())
        return kontext

    async def _zugaenge_bauen(self) -> None:
        """Zugänge nach dem Stand der Einstellungen neu aufbauen und den Besitzer bestimmen."""
        alte = self._clients
        stand = self.einstellungen.stand
        try:
            pruefung = self._pruefung()
        except OSError as f:
            logger.warning("Zertifikatsstelle nicht lesbar: %s", f)
            pruefung = True
        kurz = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0), verify=pruefung, transport=self._transport)
        lang = httpx.AsyncClient(timeout=ARBEIT, verify=pruefung, transport=self._transport)
        self._clients = [kurz, lang]
        kw_schluessel = stand.kellerwolke_schluessel.get_secret_value()
        self.kellerwolke = Kellerwolke(stand.kellerwolke_adresse, kw_schluessel, client=kurz) \
            if stand.kellerwolke_adresse and kw_schluessel else None
        ls_schluessel = stand.leitstelle_schluessel.get_secret_value()
        self.leitstelle = Leitstelle(stand.leitstelle_adresse, ls_schluessel, self.name, client=lang) \
            if stand.leitstelle_adresse and ls_schluessel else None
        self.anmeldung.verbinden(stand.kellerwolke_adresse, kurz)
        await self._besitzer_bestimmen()
        for c in alte:
            await c.aclose()

    async def _besitzer_bestimmen(self) -> None:
        if self.kellerwolke is None:
            self.besitzer = None
            return
        try:
            self.besitzer = (await self.kellerwolke.ich()).konto
        except KellerwolkeFehler as f:
            logger.warning("Kellerwolke: Besitzer nicht bestimmbar (%s)", f)
            self.besitzer = None

    @property
    def einrichtung_noetig(self) -> bool:
        stand = self.einstellungen.stand
        return not (stand.kellerwolke_adresse and stand.kellerwolke_schluessel.get_secret_value())

    async def verbindungen(self) -> list[Verbindung]:
        stand = self.einstellungen.stand
        ergebnis = []
        if self.kellerwolke is None:
            ergebnis.append(Verbindung(name="Kellerwolke", ok=False, meldung="nicht eingerichtet"))
        else:
            try:
                ich = await self.kellerwolke.ich()
                self.besitzer = ich.konto
                ergebnis.append(Verbindung(name="Kellerwolke", ok=True, adresse=stand.kellerwolke_adresse, meldung=ich.zweig))
            except KellerwolkeFehler as f:
                ergebnis.append(Verbindung(name="Kellerwolke", ok=False, adresse=stand.kellerwolke_adresse, meldung=f.meldung))
        if self.leitstelle is None:
            ergebnis.append(Verbindung(name="Leitstelle", ok=False, meldung="nicht eingerichtet"))
        else:
            try:
                modelle = await self.leitstelle.modelle()
                ergebnis.append(Verbindung(name="Leitstelle", ok=True, adresse=stand.leitstelle_adresse,
                                           meldung=f"{len(modelle)} Modelle und Dienste"))
            except LeitstellenFehler as f:
                ergebnis.append(Verbindung(name="Leitstelle", ok=False, adresse=stand.leitstelle_adresse, meldung=f.meldung))
        return ergebnis

    # --- Lebenszyklus -----------------------------------------------------------------------------------------

    async def starten(self) -> None:
        await self.db.oeffnen()
        await self.einstellungen.starten()
        await self.protokoll.starten()
        await self._zugaenge_bauen()
        self.einstellungen.bei_aenderung(self._nach_aenderung)
        await self.auftraege.starten()
        self._pflege = asyncio.create_task(self._taeglich(), name="pflege")

    async def stoppen(self) -> None:
        if self._pflege:
            self._pflege.cancel()
            await asyncio.gather(self._pflege, return_exceptions=True)
        await self.auftraege.stoppen()
        await self.verzeichnis.schliessen()
        for c in self._clients:
            await c.aclose()
        await self.db.schliessen()

    async def _nach_aenderung(self, stand: E, geaendert: set[str]) -> None:
        felder = self.einstellungen.modell.model_fields
        titel = sorted(felder[n].title or n for n in geaendert)
        await self.protokoll.eintragen("einstellung.geaendert", ", ".join(titel), bezug_art="einstellungen",
                                       daten={"felder": sorted(geaendert)})
        if geaendert & {"kellerwolke_adresse", "kellerwolke_schluessel", "leitstelle_adresse", "leitstelle_schluessel",
                        "ca_datei"}:
            await self._zugaenge_bauen()

    async def _taeglich(self) -> None:
        while True:
            for arbeit in (self.auftraege.aufraeumen, self.protokoll.aufraeumen):
                try:
                    await arbeit()
                except Exception:  # noqa: BLE001 - Pflege darf die App nie anhalten
                    logger.exception("Tägliche Pflege")
            await asyncio.sleep(TAG_S)

    # --- Schnittstelle ----------------------------------------------------------------------------------------

    def info(self) -> AppInfo:
        return AppInfo(name=self.name, kennung=self.kennung, rolle=self.rolle, symbol=self.symbol, fassung=self.fassung,
                       appkern=appkern.__version__, einrichtung_noetig=self.einrichtung_noetig, besitzer=self.besitzer)

    def _grund_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1", tags=["app"])

        @router.get("/app", response_model=AppInfo)
        async def app_info() -> AppInfo:
            return self.info()

        @router.post("/einrichtung", response_model=AppInfo)
        async def einrichten(eingabe: Einrichtung, request: Request) -> AppInfo:
            """Erste Einrichtung: nur vom Rechner selbst und nur, solange keine Kellerwolke eingetragen ist."""
            if not self.einrichtung_noetig:
                raise HTTPException(status_code=409, detail="Die App ist schon eingerichtet; Änderungen unter Einstellungen")
            if (request.client.host if request.client else "") not in LOKAL:
                raise HTTPException(status_code=403, detail="Die erste Einrichtung geht nur am Rechner der App selbst")
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), verify=self._pruefung(),
                                         transport=self._transport) as client:
                probe = Kellerwolke(eingabe.kellerwolke_adresse, eingabe.kellerwolke_schluessel, client=client)
                try:
                    ich = await probe.ich()
                except KellerwolkeFehler as f:
                    raise HTTPException(status_code=422, detail=f"Die Kellerwolke nimmt den Schlüssel nicht: {f.meldung}")
            await self.einstellungen.aendern({"kellerwolke_adresse": eingabe.kellerwolke_adresse.rstrip("/"),
                                              "kellerwolke_schluessel": eingabe.kellerwolke_schluessel})
            await self.protokoll.eintragen("app.eingerichtet", f"Kellerwolke, Zweig {ich.zweig}", bezug_name=ich.konto)
            return self.info()

        @router.get("/verbindungen", response_model=list[Verbindung], dependencies=[self.pflicht])
        async def verbindungen() -> list[Verbindung]:
            return await self.verbindungen()

        @router.get("/ich", response_model=Konto)
        async def ich(konto: Konto = self.pflicht) -> Konto:
            return konto

        return router

    def fastapi(self) -> FastAPI:
        @asynccontextmanager
        async def lebenszyklus(_app: FastAPI):
            await self.starten()
            try:
                yield
            finally:
                await self.stoppen()

        app = FastAPI(title=self.name, version=self.fassung, lifespan=lebenszyklus)
        app.include_router(self._grund_router())
        app.include_router(anmeldungs_router(self.anmeldung, protokoll=self.protokoll))
        for router in (auftrags_router(self.auftraege, abhaengigkeiten=[self.pflicht]),
                       einstellungs_router(self.einstellungen, abhaengigkeiten=[self.pflicht]),
                       protokoll_router(self.protokoll, abhaengigkeiten=[self.pflicht])):
            app.include_router(router)
        return app

    def oberflaeche_ausliefern(self, app: FastAPI) -> None:
        """Die gebaute Oberfläche; zuletzt einbinden (fängt alle übrigen Pfade). Unbekannte Pfade bekommen index.html,
        Pfade unter /api nie."""
        wurzel = self.oberflaeche.resolve() if self.oberflaeche else None

        @app.api_route("/{pfad:path}", methods=["GET", "HEAD"], include_in_schema=False)
        async def seite(pfad: str):
            if pfad.startswith("api/"):
                return JSONResponse({"detail": "Nicht gefunden"}, status_code=404)
            if wurzel is None or not (wurzel / "index.html").is_file():
                return JSONResponse({"meldung": f"{self.name}: Oberfläche nicht gebaut; Schnittstelle unter /docs"})
            datei = (wurzel / pfad).resolve()
            if pfad and datei.is_file() and datei.is_relative_to(wurzel):
                kopf = {"Cache-Control": "public, max-age=31536000, immutable"} if pfad.startswith("assets/") \
                    else {"Cache-Control": "no-cache"}
                return FileResponse(datei, headers=kopf)
            return FileResponse(wurzel / "index.html", headers={"Cache-Control": "no-cache"})
