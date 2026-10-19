"""Gerüst einer App: verdrahtet die Bausteine des Appkerns einmal, damit jede App nur noch ihr Fachliches schreibt.

    geruest = Geruest(name="Transkription", kennung="transkription", rolle="macht aus Ton Text", fassung="0.1.0",
                      daten=Path("daten"), einstellungen=TranskriptionEinstellungen, arten=[...],
                      oberflaeche=Path("../frontend/dist"))
    app = geruest.fastapi()
    app.include_router(eigener_router)          # mit Depends(geruest.pflicht), Oberflächen-Eigenes mit geruest.mensch

Was das Gerüst übernimmt: Datenbank, Einstellungen (Grundeinstellungen plus die der App), Protokoll, Aufträge,
Anmeldung mit dem Kellerwolke-Konto (Besitzer ist das Konto des App-Schlüssels), Zugänge zu Kellerwolke und Leitstelle
(nach jeder Änderung der Einstellungen neu aufgebaut), App-Verzeichnis, Prüfung der Verbindungen, erste Einrichtung
(nur vom Rechner selbst, solange keine Kellerwolke eingetragen ist), tägliches Aufräumen, Auslieferung der gebauten
Oberfläche.

Die Schnittstellendoku zum Ausprobieren (/docs, /redoc, /openapi.json) gibt es nur in der Entwicklung, mit
`<KENNUNG>_SCHNITTSTELLEN_DOKU=1` in der Umgebung; sonst zeigt die App ihren Aufbau niemandem ohne Anmeldung.
`app.openapi()` liefert das Schema im Code immer (etwa für eine Ausfuhr).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import ssl
from collections.abc import Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Generic, TypeVar

import certifi
import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import appkern
from appkern.anfragen import Abholer, Angebot as AppAngebot
from appkern.anfragen.api import anfragen_router
from appkern.anmeldung import Anmeldung, Konto
from appkern.anmeldung.api import angemeldet, anmeldungs_router
from appkern.auftraege import Art, Auftraege
from appkern.auftraege.api import auftrags_router
from appkern.datenbank import LESER, Datenbank
from appkern.einstellungen import Angebot, Einstellungen, Option
from appkern.einstellungen.api import einstellungs_router
from appkern.kellerwolke import Kellerwolke, KellerwolkeFehler, NichtErreichbar, SchluesselUngueltig
from appkern.leitstelle import Leitstelle, LeitstellenFehler, geduld_setzen
from appkern.leitstelle.zugang import ARBEIT
from appkern.protokoll import Protokoll
from appkern.protokoll.api import protokoll_router
from appkern.verzeichnis import Verzeichnis

from .einrichtungscode import Einrichtungscode, Gesperrt
from .einstellungen import Grundeinstellungen

logger = logging.getLogger("appkern.app")


class Begleiter:
    """Hintergrundarbeit einer App, die mit dem Gerüst lebt, etwa ein Abgleich mit der Kellerwolke. Eine App leitet
    davon ab und überschreibt, was sie braucht; angemeldet mit `geruest.begleiter_anmelden`.

    Reihenfolge beim Start: Datenbank, Einstellungen, Protokoll, Zugänge, dann `starten` und `verbunden` jedes
    Begleiters, danach erst die Aufträge (die sich auf den Begleiter verlassen dürfen). `verbunden` kommt nach jedem
    Neuaufbau der Zugänge wieder (geänderte Kellerwolke oder Leitstelle). Beim Stoppen enden erst die Aufträge, dann die
    Begleiter in umgekehrter Reihenfolge. Ein Fehler eines Begleiters steht im Log und hält die App nicht an."""

    async def starten(self) -> None:
        """Einmal beim Start, etwa das eigene Datenbankschema einrichten."""

    async def verbunden(self) -> None:
        """Nach jedem Aufbau der Zugänge (auch dem ersten)."""

    async def stoppen(self) -> None:
        """Beim Beenden: eigene Aufgaben beenden."""
E = TypeVar("E", bound=Grundeinstellungen)
LOKAL = {"127.0.0.1", "::1", "localhost"}
TAG_S = 24 * 3600
JA = {"1", "ja", "an", "true", "yes", "on"}
# Endet der letzte Teil eines Wegs wie ein Dateiname (Punkt, dann Buchstabe, dann Buchstaben oder Ziffern), ist es eine
# Datei und nie eine Seite; Zahlen wie /transkripte/<kennung>/12.5 bleiben Seiten.
DATEIENDUNG = re.compile(r"\.[A-Za-z][A-Za-z0-9]*$")


def schnittstellen_doku(kennung: str) -> bool:
    """Ob die App ihre Schnittstellendoku zeigt: nur mit `<KENNUNG>_SCHNITTSTELLEN_DOKU=1` (Entwicklung)."""
    return os.environ.get(f"{kennung.upper()}_SCHNITTSTELLEN_DOKU", "").strip().lower() in JA


def hausstelle() -> Path | None:
    """Wurzelzertifikat der Hausstelle dieses Rechners (die lokale Zertifikatsstelle, von der Kellerwolke und Leitstelle
    im Heimnetz ihre HTTPS-Zertifikate haben), wenn es eines gibt: `$CAROOT`, sonst der übliche Ort auf Mac und Linux."""
    orte = [Path(os.environ["CAROOT"]) / "rootCA.pem"] if os.environ.get("CAROOT") else []
    orte += [Path.home() / "Library" / "Application Support" / "mkcert" / "rootCA.pem",
             Path.home() / ".local" / "share" / "mkcert" / "rootCA.pem"]
    return next((o for o in orte if o.is_file()), None)


class AppInfo(BaseModel):
    name: str
    kennung: str
    rolle: str
    symbol: str
    fassung: str
    appkern: str
    einrichtung_noetig: bool
    besitzer: str | None = None
    kellerwolke: str = ""       # Adresse, gegen die angemeldet und gekoppelt wird (nie der Schlüssel)
    oberflaeche: str | None = None  # Fassung der gebauten Oberfläche, die der Server gerade ausliefert
    auftraege_laufend: int = 0      # nur die Zahl (für das Ausrollen ohne Abbruch), nie Inhalte
    einrichtungscode: str | None = None  # solange die Einrichtung nötig ist: wo der Code steht (nie der Code)


class Verbindung(BaseModel):
    name: str
    ok: bool
    adresse: str = ""
    meldung: str = ""


class Einrichtung(BaseModel):
    kellerwolke_adresse: str = Field(min_length=1)
    kellerwolke_schluessel: str = Field(min_length=1)
    einrichtungscode: str = Field("", max_length=64)   # nötig, wenn die Anfrage nicht vom Rechner der App kommt


class AdresseEingabe(BaseModel):
    adresse: str = Field(pattern=r"^https?://[^/\s?#]+$", max_length=200,
                         description="Herkunft der Seite im Browser (location.origin), ohne Pfad")


class Geruest(Generic[E]):
    def __init__(self, *, name: str, kennung: str, rolle: str, fassung: str, daten: Path, einstellungen: type[E],
                 arten: Sequence[Art] = (), symbol: str = "fa-cube", oberflaeche: Path | None = None,
                 gleichzeitig: int = 1, angebote: Sequence[AppAngebot] = (), leseverbindungen: int = LESER,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        """`angebote`: was die App mit Dateien der Kellerwolke kann (Aktionen im Dateimenü, Dateiwahl in der App).
        `leseverbindungen`: so viele Lesungen der Datenbank laufen nebeneinander (neben dem Schreiben).
        `transport` nur für Tests: alle Verbindungen nach außen gehen dann über ihn."""
        self.name, self.kennung, self.rolle, self.symbol, self.fassung = name, kennung, rolle, symbol, fassung
        self.daten = Path(daten)
        self.oberflaeche = oberflaeche
        self._transport = transport
        self.db = Datenbank(self.daten / f"{kennung}.sqlite", leser=leseverbindungen)
        self.einrichtungscode = Einrichtungscode.aus_umgebung(kennung, self.daten)
        self.einstellungen: Einstellungen[E] = Einstellungen(self.db, einstellungen, umgebung_praefix=f"{kennung.upper()}_")
        self.protokoll = Protokoll(self.db)
        self.auftraege = Auftraege(self.db, arten, gleichzeitig=gleichzeitig, protokoll=self.protokoll)
        self.verzeichnis = Verzeichnis()
        self.besitzer: str | None = None
        self.app_name: str | None = None          # Name des Zugangs in der Kellerwolke (Anmeldungen gelten nur hier)
        self.kellerwolke: Kellerwolke | None = None
        self.leitstelle: Leitstelle | None = None
        self._clients: list[httpx.AsyncClient] = []
        self.anmeldung = Anmeldung("", self._erlaubt, app_name=self._eigener_name)
        self._grundangebote()
        self.pflicht = Depends(angemeldet(self.anmeldung))                          # Menschen und andere Apps
        self.mensch = Depends(angemeldet(self.anmeldung, nur_menschen=True))        # nur Menschen
        self.lesen = Depends(angemeldet(self.anmeldung, cookie=True))
        self._pflege: asyncio.Task | None = None
        self.abholer = Abholer(angebote, self.auftraege, lambda: self.kellerwolke,
                               lambda: self.einstellungen.stand.adresse or None)
        self._begleiter: list[Begleiter] = [self.abholer] if angebote else []
        self._oberflaeche_gemerkt: tuple[float, str | None] | None = None
        self._laeuft = False

    # --- Angebote für die Einstellungen: Auswahl aus dem System statt bloßer Textfelder ----------------------------

    def _grundangebote(self) -> None:
        async def verbindung(name: str) -> str:
            v = next((x for x in await self.verbindungen() if x.name == name), None)
            if v is None:
                return ""
            return f"verbunden: {v.meldung}" if v.ok else f"nicht verbunden: {v.meldung}"

        async def adressen(teil: str, aktuell: str) -> list[Option]:
            optionen = [Option(wert=aktuell, titel=aktuell, hinweis="eingetragen")] if aktuell else []
            for e in await self.verzeichnis.alle():
                if teil in e.kennung and e.adresse != aktuell:
                    optionen.append(Option(wert=e.adresse, titel=e.adresse, hinweis=f"{e.name} ({e.quelle})"))
            return optionen

        async def kellerwolke() -> Angebot:
            stand = self.einstellungen.stand
            return Angebot(optionen=await adressen("kellerwolke", stand.kellerwolke_adresse),
                           stand=await verbindung("Kellerwolke"))

        async def leitstelle() -> Angebot:
            stand = self.einstellungen.stand
            return Angebot(optionen=await adressen("leitstelle", stand.leitstelle_adresse), stand=await verbindung("Leitstelle"))

        async def zertifikate() -> Angebot:
            haus = hausstelle()
            optionen = [Option(wert="", titel="Automatisch", hinweis="übliche Stellen und die Hausstelle dieses Rechners")]
            if haus is not None:
                optionen.append(Option(wert=str(haus), titel=str(haus), hinweis="Hausstelle dieses Rechners"))
            gilt = self.einstellungen.stand.ca_datei or (f"Hausstelle {haus}" if haus else "nur die üblichen Stellen")
            return Angebot(optionen=optionen, stand=f"es gilt: {gilt}")

        async def extern() -> Angebot:
            if self.leitstelle is None:
                return Angebot(eigener_wert=False, stand="Leitstelle noch nicht eingerichtet")
            try:
                modelle = [m for m in await self.leitstelle.modelle() if m.extern]
            except LeitstellenFehler as f:
                return Angebot(eigener_wert=False, stand=f"Leitstelle antwortet nicht: {f.meldung}")
            optionen = [Option(wert=m.id, titel=m.name or m.id, hinweis=(m.steckbrief.zweck if m.steckbrief and m.steckbrief.zweck else "extern")
                               + (f", höchstens {m.steckbrief.anfragen_je_minute} je Minute" if m.steckbrief and m.steckbrief.anfragen_je_minute else ""))
                        for m in modelle]
            return Angebot(optionen=optionen, eigener_wert=False,
                           stand=f"gefunden: {len(optionen)} externe Modelle" if optionen
                           else "Die Leitstelle erlaubt dieser App keine externen Modelle (Leitstelle, Anwendungen, Zone extern)")

        self.einstellungen.anbieten("kellerwolke_adresse", kellerwolke)
        self.einstellungen.anbieten("leitstelle_extern", extern)
        self.einstellungen.anbieten("leitstelle_adresse", leitstelle)
        self.einstellungen.anbieten("ca_datei", zertifikate)

    def leitstelle_angebot(self, faehigkeit: str, *, leer: str | None = None):
        """Anbieter für ein Feld, das einen Dienst oder ein Modell der Leitstelle nennt: die Auswahl sind die Modelle und
        Dienste mit dieser Fähigkeit, die die App nutzen darf. `leer` bietet zusätzlich den leeren Wert mit diesem
        Namen an (etwa "Kette der App")."""

        async def anbieter() -> Angebot:
            optionen = [Option(wert="", titel=leer, hinweis="die Leitstelle wählt")] if leer else []
            if self.leitstelle is None:
                return Angebot(optionen=optionen, stand="Leitstelle noch nicht eingerichtet (Reiter Verbindungen)")
            try:
                modelle = await self.leitstelle.modelle()
            except LeitstellenFehler as f:
                return Angebot(optionen=optionen, stand=f"Leitstelle antwortet nicht: {f.meldung}")
            passend = [m for m in modelle if faehigkeit in m.faehigkeiten]
            optionen += [Option(wert=m.id, titel=m.name or m.id, hinweis=("geladen" if m.geladen else "")
                                + (f" auf {m.knoten_name or m.knoten}" if m.knoten else "")) for m in passend]
            return Angebot(optionen=optionen, stand="" if passend else "Die Leitstelle bietet dieser App dafür nichts an")

        return anbieter

    def begleiter_anmelden(self, *begleiter: Begleiter) -> None:
        """Vor dem Start anmelden (siehe `Begleiter`)."""
        if self._laeuft:
            raise RuntimeError("Begleiter vor dem Start anmelden")
        self._begleiter.extend(begleiter)

    async def _begleiter_rufen(self, schritt: str, begleiter: list[Begleiter] | None = None) -> None:
        for b in begleiter if begleiter is not None else self._begleiter:
            try:
                await getattr(b, schritt)()
            except Exception:  # noqa: BLE001 - ein Begleiter darf die App nie anhalten
                logger.exception("Begleiter %s: %s", type(b).__name__, schritt)

    # --- Zugänge ----------------------------------------------------------------------------------------------

    def _erlaubt(self) -> set[str]:
        if not self.besitzer:
            return set()
        return {self.besitzer, *self.einstellungen.stand.weitere_konten}

    def _pruefung(self) -> ssl.SSLContext:
        """Vertraut den üblichen Stellen und dazu der eingestellten Zertifikatsstelle, sonst der Hausstelle dieses
        Rechners. So geht HTTPS zu Kellerwolke und Leitstelle im Heimnetz ohne weitere Einstellung."""
        kontext = ssl.create_default_context(cafile=certifi.where())
        ca = self.einstellungen.stand.ca_datei.strip()
        zusatz = Path(ca).expanduser() if ca else hausstelle()
        if zusatz is not None:
            kontext.load_verify_locations(zusatz)
        return kontext

    async def _zugaenge_bauen(self) -> None:
        """Zugänge nach dem Stand der Einstellungen neu aufbauen und den Besitzer bestimmen."""
        alte = self._clients
        stand = self.einstellungen.stand
        try:
            pruefung: ssl.SSLContext | bool = self._pruefung()
        except (OSError, ssl.SSLError) as f:
            logger.warning("Zertifikatsstelle nicht lesbar: %s", f)
            pruefung = True
        kurz = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0), verify=pruefung, transport=self._transport)
        lang = httpx.AsyncClient(timeout=ARBEIT, verify=pruefung, transport=self._transport)
        self._clients = [kurz, lang]
        kw_schluessel = stand.kellerwolke_schluessel.get_secret_value()
        self.kellerwolke = Kellerwolke(stand.kellerwolke_adresse, kw_schluessel, client=kurz) \
            if stand.kellerwolke_adresse and kw_schluessel else None
        ls_schluessel = stand.leitstelle_schluessel.get_secret_value()
        self.leitstelle = Leitstelle(stand.leitstelle_adresse, ls_schluessel, self.name, client=lang, extern=stand.leitstelle_extern) \
            if stand.leitstelle_adresse and ls_schluessel else None
        self.anmeldung.verbinden(stand.kellerwolke_adresse, kurz)
        await self._besitzer_bestimmen()
        for c in alte:
            await c.aclose()

    async def _eigener_name(self) -> str | None:
        """Name des Zugangs in der Kellerwolke; fehlt er noch (Kellerwolke beim Start nicht erreichbar), neu fragen."""
        if self.app_name is None:
            await self._besitzer_bestimmen()
        return self.app_name

    async def _besitzer_bestimmen(self) -> None:
        """Besitzer und Name des Zugangs aus der Kellerwolke. Ist sie gerade nicht erreichbar, bleibt der zuletzt
        bekannte Stand; sonst wiese die App im Ausfall auch die Anmeldungen ab, die aus dem Merker weiter gelten."""
        if self.kellerwolke is None:
            self.besitzer = self.app_name = None
            return
        try:
            ich = await self.kellerwolke.ich()
            self.besitzer, self.app_name = ich.konto, ich.app
        except NichtErreichbar as f:
            logger.warning("Kellerwolke: Besitzer nicht bestimmbar (%s); es gilt der zuletzt bekannte", f)
        except KellerwolkeFehler as f:
            logger.warning("Kellerwolke: Besitzer nicht bestimmbar (%s)", f)
            self.besitzer = self.app_name = None

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
                self.besitzer, self.app_name = ich.konto, ich.app
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
        geduld_setzen(self.einstellungen.stand.leitstelle_geduld_min * 60)
        self.anmeldung.ausfall_s = self.einstellungen.stand.anmeldung_ausfall_h * 3600
        await self._zugaenge_bauen()
        self.einstellungen.bei_aenderung(self._nach_aenderung)
        self._laeuft = True
        await self._einrichtungscode_bereitstellen()
        gebaut = self.oberflaeche_fassung()
        if gebaut and gebaut != self.fassung:
            await self.protokoll.eintragen("app.oberflaeche_veraltet", f"Die Oberfläche ist für {gebaut} gebaut, die App ist "
                                           f"{self.fassung}: die Oberfläche neu bauen (einrichten.sh oder Ausrollen)", stufe="warnung")
            logger.warning("Oberfläche für %s gebaut, App ist %s", gebaut, self.fassung)
        await self._begleiter_rufen("starten")
        await self._begleiter_rufen("verbunden")
        await self.auftraege.starten()
        self._pflege = asyncio.create_task(self._taeglich(), name="pflege")

    async def _einrichtungscode_bereitstellen(self) -> None:
        """Solange die Einrichtung nötig ist, ein neuer Code je Start (Ort ins Protokoll, nie der Code); sonst keiner."""
        if not self.einrichtung_noetig:
            self.einrichtungscode.entfernen()
            return
        try:
            self.einrichtungscode.erzeugen()
        except OSError as f:
            logger.warning("Einrichtungscode nicht schreibbar (%s): erste Einrichtung nur am Rechner der App", f)
            return
        await self.protokoll.eintragen("app.einrichtungscode", f"Code für die erste Einrichtung liegt in {self.einrichtungscode.ort}")
        logger.warning("Erste Einrichtung nötig; der Einrichtungscode liegt in %s", self.einrichtungscode.ort)

    async def stoppen(self) -> None:
        if self._pflege:
            self._pflege.cancel()
            await asyncio.gather(self._pflege, return_exceptions=True)
        await self.auftraege.stoppen()
        await self._begleiter_rufen("stoppen", list(reversed(self._begleiter)))
        self._laeuft = False
        await self.anmeldung.schliessen()
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
                        "ca_datei", "adresse"}:
            await self._zugaenge_bauen()
            await self._begleiter_rufen("verbunden")
        elif "leitstelle_extern" in geaendert and self.leitstelle is not None:
            self.leitstelle.extern = tuple(stand.leitstelle_extern)
        if "leitstelle_geduld_min" in geaendert:
            geduld_setzen(stand.leitstelle_geduld_min * 60)
        if "anmeldung_ausfall_h" in geaendert:
            self.anmeldung.ausfall_s = stand.anmeldung_ausfall_h * 3600

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
                       appkern=appkern.__version__, einrichtung_noetig=self.einrichtung_noetig, besitzer=self.besitzer,
                       kellerwolke=self.einstellungen.stand.kellerwolke_adresse.rstrip("/"),
                       oberflaeche=self.oberflaeche_fassung(),
                       einrichtungscode=self.einrichtungscode.ort if self.einrichtung_noetig and self.einrichtungscode.aktiv else None)

    def oberflaeche_fassung(self) -> str | None:
        """Fassung der gebauten Oberfläche (Meta `app-fassung` in index.html, beim Bau eingesetzt). Gegen sie vergleicht
        ein offener Tab seine eigene: so lädt er genau dann neu, wenn es wirklich eine neuere Oberfläche gibt, und
        ein vergessener Bau nach einer neuen Fassung führt nicht zu einem Band, das nie verschwindet."""
        datei = self.oberflaeche / "index.html" if self.oberflaeche else None
        try:
            stand = datei.stat().st_mtime if datei else None
        except OSError:
            return None
        if stand is None:
            return None
        if self._oberflaeche_gemerkt and self._oberflaeche_gemerkt[0] == stand:
            return self._oberflaeche_gemerkt[1]
        treffer = re.search(r'<meta name="app-fassung" content="([^"]+)"', datei.read_text(encoding="utf-8", errors="replace"))
        fassung = treffer.group(1) if treffer else None
        self._oberflaeche_gemerkt = (stand, fassung)
        return fassung

    def _einrichtungscode_pruefen(self, code: str) -> None:
        if not self.einrichtungscode.aktiv:
            raise HTTPException(status_code=403, detail="Die erste Einrichtung geht nur am Rechner der App selbst")
        ort = self.einrichtungscode.ort
        if not code.strip():
            raise HTTPException(status_code=403, detail=f"Von hier aus braucht die erste Einrichtung den Einrichtungscode; er steht "
                                                        f"am Rechner der App in {ort}")
        try:
            richtig = self.einrichtungscode.pruefen(code)
        except Gesperrt as g:
            raise HTTPException(status_code=429, detail=f"Zu viele falsche Codes; in {max(1, g.sekunden // 60)} Minuten wieder")
        if not richtig:
            raise HTTPException(status_code=403, detail=f"Der Einrichtungscode stimmt nicht; er steht am Rechner der App in {ort}")

    def _grund_router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1", tags=["app"])

        @router.get("/app", response_model=AppInfo)
        async def app_info() -> AppInfo:
            return self.info().model_copy(update={"auftraege_laufend": await self.auftraege.laufend()})

        @router.post("/einrichtung", response_model=AppInfo)
        async def einrichten(eingabe: Einrichtung, request: Request) -> AppInfo:
            """Erste Einrichtung, nur solange keine Kellerwolke eingetragen ist: vom Rechner der App selbst, von
            anderswo (Vorschaltdienst, Docker, anderes Gerät) nur mit dem Einrichtungscode aus der Datei am Rechner."""
            if not self.einrichtung_noetig:
                raise HTTPException(status_code=409, detail="Die App ist schon eingerichtet; Änderungen unter Einstellungen")
            if (request.client.host if request.client else "") not in LOKAL:
                self._einrichtungscode_pruefen(eingabe.einrichtungscode)
            try:
                pruefung = self._pruefung()
            except (OSError, ssl.SSLError) as f:
                raise HTTPException(status_code=422, detail=f"Zertifikatsstelle nicht lesbar: {f}")
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), verify=pruefung,
                                         transport=self._transport) as client:
                probe = Kellerwolke(eingabe.kellerwolke_adresse, eingabe.kellerwolke_schluessel, client=client)
                try:
                    ich = await probe.ich()
                except NichtErreichbar as f:
                    raise HTTPException(status_code=422, detail=f"Die Kellerwolke unter {eingabe.kellerwolke_adresse} ist von "
                                                                f"diesem Rechner aus nicht erreichbar ({f.meldung}).")
                except SchluesselUngueltig:
                    raise HTTPException(status_code=422, detail="Die Kellerwolke kennt diesen App-Schlüssel nicht, oder er "
                                                                "ist gesperrt. In der Kellerwolke unter Einstellungen, Zugänge "
                                                                "prüfen oder neu ausstellen.")
                except KellerwolkeFehler as f:
                    raise HTTPException(status_code=422, detail=f"Die Kellerwolke antwortet unerwartet: {f.meldung}")
            await self.einstellungen.aendern({"kellerwolke_adresse": eingabe.kellerwolke_adresse.rstrip("/"),
                                              "kellerwolke_schluessel": eingabe.kellerwolke_schluessel})
            self.einrichtungscode.entfernen()
            await self.protokoll.eintragen("app.eingerichtet", f"Kellerwolke, Zweig {ich.zweig}", bezug_name=ich.konto)
            return self.info()

        @router.get("/verbindungen", response_model=list[Verbindung], dependencies=[self.pflicht])
        async def verbindungen() -> list[Verbindung]:
            return await self.verbindungen()

        @router.get("/ich", response_model=Konto)
        async def ich(konto: Konto = self.pflicht) -> Konto:
            return konto

        @router.post("/adresse", response_model=AdresseEingabe, dependencies=[self.mensch])
        async def adresse_melden(eingabe: AdresseEingabe) -> AdresseEingabe:
            """Die Oberfläche meldet nach der Anmeldung, unter welcher Adresse Menschen die App öffnen (so, wie der
            Browser sie sieht, auch hinter einem Proxy). Eingetragen wird sie einmal, danach gilt die Einstellung;
            dorthin führt Öffnen aus der Kellerwolke."""
            if not self.einstellungen.stand.adresse:
                await self.einstellungen.aendern({"adresse": eingabe.adresse})
            return AdresseEingabe(adresse=self.einstellungen.stand.adresse)

        return router

    def fastapi(self) -> FastAPI:
        @asynccontextmanager
        async def lebenszyklus(_app: FastAPI):
            await self.starten()
            try:
                yield
            finally:
                await self.stoppen()

        doku = schnittstellen_doku(self.kennung)
        app = FastAPI(title=self.name, version=self.fassung, lifespan=lebenszyklus, docs_url="/docs" if doku else None,
                      redoc_url="/redoc" if doku else None, openapi_url="/openapi.json" if doku else None)
        app.include_router(self._grund_router())
        app.include_router(anmeldungs_router(self.anmeldung, protokoll=self.protokoll))
        if self.abholer.angebote:
            app.include_router(anfragen_router(self.abholer, lambda: self.kellerwolke, self.mensch))
        for router in (auftrags_router(self.auftraege, abhaengigkeiten=[self.pflicht]),
                       einstellungs_router(self.einstellungen, abhaengigkeiten=[self.mensch]),
                       protokoll_router(self.protokoll, abhaengigkeiten=[self.pflicht])):
            app.include_router(router)
        return app

    def oberflaeche_ausliefern(self, app: FastAPI) -> None:
        """Die gebaute Oberfläche; zuletzt einbinden (fängt alle übrigen Pfade). Unbekannte Seiten bekommen index.html
        (die Oberfläche liest ihren Weg selbst); Pfade unter /api und fehlende Dateien (ein Weg mit Dateiendung, etwa
        /manifest.webmanifest) bekommen 404, damit der Browser nie eine Seite als Datei nimmt."""
        wurzel = self.oberflaeche.resolve() if self.oberflaeche else None

        @app.api_route("/{pfad:path}", methods=["GET", "HEAD"], include_in_schema=False)
        async def seite(pfad: str):
            if pfad.startswith("api/"):
                return JSONResponse({"detail": "Nicht gefunden"}, status_code=404)
            if wurzel is None or not (wurzel / "index.html").is_file():
                return JSONResponse({"meldung": f"{self.name}: Oberfläche nicht gebaut"})
            datei = (wurzel / pfad).resolve()
            if pfad and datei.is_file() and datei.is_relative_to(wurzel):
                kopf = {"Cache-Control": "public, max-age=31536000, immutable"} if pfad.startswith("assets/") \
                    else {"Cache-Control": "no-cache"}
                return FileResponse(datei, headers=kopf)
            if DATEIENDUNG.search(pfad.rsplit("/", 1)[-1]):
                return JSONResponse({"detail": "Nicht gefunden"}, status_code=404)
            return FileResponse(wurzel / "index.html", headers={"Cache-Control": "no-cache"})
