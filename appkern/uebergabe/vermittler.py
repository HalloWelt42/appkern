"""Übergabe zwischen Geräten (RAD-18, aus TubeVault): Vermittler für alle Apps.

Jedes Fenster einer App, das sich per WebSocket meldet, ist ein Gerät. Der Vermittler hält nichts fest und spielt
nichts; er reicht nur weiter, und zwar nur zwischen Geräten desselben Kontos (Raum):

  zustand     ein Gerät meldet, was es gerade spielt; die anderen sehen es
  befehl      ein Gerät bittet ein anderes um etwas (etwa "abgeben": seine Wiedergabe herschicken), bei Bedarf mit einer
              Zahl (etwa der Lautstärke); welche Befehle es gibt, bestimmt die App
  uebergabe   ein Gerät gibt seine Wiedergabe samt Stelle an ein anderes ab
  name        ein Gerät benennt sich um (gilt für alle Fenster desselben Browsers)
  aktiv       ein Fenster war zuletzt im Vordergrund

Was ein Zustand und ein Paket enthalten, bestimmt die App mit eigenen Modellen (`zustand_modell`, `paket_modell`);
der Vermittler prüft sie damit und kennt ihren Inhalt sonst nicht. Wer die Verbindung schließt, ist weg.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Generic, Literal, Optional, Protocol, TypeVar, Union

from pydantic import BaseModel, Field, TypeAdapter, ValidationError

logger = logging.getLogger(__name__)

MAX_NAME = 40

Geraeteart = Literal["rechner", "telefon", "tablet"]
Z = TypeVar("Z", bound=BaseModel)
P = TypeVar("P", bound=BaseModel)


class Geraet(BaseModel):
    """Ein Fenster der App; `geraet` ist der Browser (mehrere Fenster teilen ihn und den Namen)"""
    id: str = Field(min_length=1, max_length=64)
    geraet: str = Field(min_length=1, max_length=64)
    name: str
    art: Geraeteart
    seit: float
    aktiv: float
    zustand: Optional[dict[str, Any]] = None   # der geprüfte Zustand der App, als Daten weitergereicht


class Anmeldung(BaseModel):
    """Erste Nachricht jeder Verbindung: der Token der Sitzung reist nicht in der Adresse (Protokolle, Verlauf)"""
    typ: Literal["anmelden"]
    token: str = ""
    id: str = Field(min_length=1, max_length=64)
    geraet: str = Field(min_length=1, max_length=64)
    name: str = ""
    art: Geraeteart = "rechner"


class _Befehl(BaseModel):
    typ: Literal["befehl"]
    an: str
    aktion: str = Field(min_length=1, max_length=40)
    wert: Optional[float] = Field(None, allow_inf_nan=False)


class _Name(BaseModel):
    typ: Literal["name"]
    name: str


class _Aktiv(BaseModel):
    typ: Literal["aktiv"]


class Verbindung(Protocol):
    async def send_json(self, data: Any) -> None: ...


def sauberer_name(name: str, ersatz: str = "Gerät") -> str:
    name = " ".join((name or "").split())[:MAX_NAME]
    return name or ersatz


class Vermittler(Generic[Z, P]):
    def __init__(self, zustand_modell: type[Z], paket_modell: type[P]) -> None:
        self._zustand = zustand_modell
        self._paket = paket_modell
        self._geraete: dict[str, Geraet] = {}
        self._raum: dict[str, str] = {}                  # Gerät -> Konto
        self._verbindungen: dict[str, Verbindung] = {}

        class _Zustand(BaseModel):
            typ: Literal["zustand"]
            zustand: Optional[zustand_modell] = None     # type: ignore[valid-type]  # None: spielt nichts mehr

        class _Uebergabe(BaseModel):
            typ: Literal["uebergabe"]
            an: str
            paket: paket_modell                          # type: ignore[valid-type]

        self._eingang = TypeAdapter(Union[_Zustand, _Befehl, _Uebergabe, _Name, _Aktiv])
        self._ZustandNachricht, self._UebergabeNachricht = _Zustand, _Uebergabe

    def geraete(self, raum: str) -> list[Geraet]:
        return sorted((g for g in self._geraete.values() if self._raum.get(g.id) == raum), key=lambda g: g.seit)

    async def beitreten(self, verbindung: Verbindung, anmeldung: Anmeldung, raum: str) -> Geraet:
        jetzt = time.time()
        geraet = Geraet(id=anmeldung.id, geraet=anmeldung.geraet, name=sauberer_name(anmeldung.name), art=anmeldung.art,
                        seit=jetzt, aktiv=jetzt)
        self._geraete[geraet.id] = geraet                # neu laden ersetzt die alte Verbindung desselben Fensters
        self._raum[geraet.id] = raum
        self._verbindungen[geraet.id] = verbindung
        await self._senden(geraet.id, {"typ": "willkommen", "du": geraet.model_dump(), "geraete": self._liste(raum)})
        await self._geraete_senden(raum, ausser=geraet.id)
        return geraet

    async def verlassen(self, geraet_id: str, verbindung: Verbindung) -> None:
        if self._verbindungen.get(geraet_id) is not verbindung:
            return                                       # längst durch eine neuere Verbindung ersetzt
        raum = self._raum.pop(geraet_id, "")
        self._geraete.pop(geraet_id, None)
        self._verbindungen.pop(geraet_id, None)
        await self._geraete_senden(raum)

    async def behandeln(self, geraet_id: str, roh: Any) -> None:
        absender = self._geraete.get(geraet_id)
        if not absender:
            return
        raum = self._raum[geraet_id]
        try:
            nachricht = self._eingang.validate_python(roh)
        except ValidationError as e:
            await self._senden(geraet_id, {"typ": "fehler", "text": "Nachricht nicht verstanden"})
            erster = e.errors()[0] if e.errors() else {}
            typ = roh.get("typ") if isinstance(roh, dict) else type(roh).__name__
            logger.warning("Übergabe: %s: %s nicht verstanden (%s: %s)", absender.name, typ,
                           ".".join(map(str, erster.get("loc", ()))), erster.get("msg", ""))
            return

        if isinstance(nachricht, self._ZustandNachricht):
            absender.zustand = nachricht.zustand.model_dump() if nachricht.zustand else None
            await self._an_raum(raum, {"typ": "zustand", "id": geraet_id, "zustand": absender.zustand}, ausser=geraet_id)
        elif isinstance(nachricht, _Befehl):
            await self._weiterreichen(absender, nachricht.an, {"typ": "befehl", "aktion": nachricht.aktion,
                                                            "wert": nachricht.wert})
        elif isinstance(nachricht, self._UebergabeNachricht):
            await self._weiterreichen(absender, nachricht.an, {"typ": "uebergabe", "paket": nachricht.paket.model_dump()})
        elif isinstance(nachricht, _Name):
            name = sauberer_name(nachricht.name, absender.name)
            for g in self.geraete(raum):                 # der Name gilt für alle Fenster des Browsers
                if g.geraet == absender.geraet:
                    g.name = name
            await self._geraete_senden(raum)
        elif isinstance(nachricht, _Aktiv):
            absender.aktiv = time.time()
            await self._geraete_senden(raum)

    async def _weiterreichen(self, absender: Geraet, ziel: str, nachricht: dict[str, Any]) -> None:
        if ziel == absender.id or self._raum.get(ziel) != self._raum.get(absender.id):
            await self._senden(absender.id, {"typ": "fehler", "text": "Das Gerät ist nicht mehr da"})
            return
        await self._senden(ziel, {**nachricht, "von": absender.id, "von_name": absender.name})

    def _liste(self, raum: str) -> list[dict[str, Any]]:
        return [g.model_dump() for g in self.geraete(raum)]

    async def _geraete_senden(self, raum: str, ausser: Optional[str] = None) -> None:
        await self._an_raum(raum, {"typ": "geraete", "geraete": self._liste(raum)}, ausser=ausser)

    async def _an_raum(self, raum: str, nachricht: dict[str, Any], ausser: Optional[str] = None) -> None:
        for geraet_id, r in list(self._raum.items()):
            if r == raum and geraet_id != ausser:
                await self._senden(geraet_id, nachricht)

    async def _senden(self, geraet_id: str, nachricht: dict[str, Any]) -> bool:
        verbindung = self._verbindungen.get(geraet_id)
        if not verbindung:
            return False
        try:
            await verbindung.send_json(nachricht)
            return True
        except Exception:
            return False                                 # abgerissen: verlassen() räumt beim Schließen auf
