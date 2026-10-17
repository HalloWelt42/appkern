"""Anfragen aus der Kellerwolke abarbeiten (Entscheidung 17.10.2026: Aktionen der Apps, Recht je Auftrag).

Eine App meldet beim Start, was sie mit welchen Dateien kann (`Angebot`: eine Aktion und die Art des Auftrags, der sie
ausführt), und holt Anfragen selbst ab: aus dem Dateimenü der Kellerwolke, aus der Dateiwahl in der App, von einer
anderen App weitergegeben. Jede Anfrage im Hintergrund wird ein Auftrag mit `AnfrageEingabe`; dessen Fortschritt und
Ende gehen an die Kellerwolke zurück. Die Arbeit liest und schreibt über `kellerwolke.mit_anfrage(eingabe.anfrage_id)`:
genau die angefragte Datei und ihre Begleiter, solange die Anfrage offen ist.

Bricht der Mensch die Anfrage in der Kellerwolke ab, bricht der Abholer den Auftrag ab. Ist die App aus, wartet die
Anfrage in der Kellerwolke, bis sie wieder läuft; nichts geht verloren. Das Ergebnis eines Auftrags nennt den
geschriebenen Begleiter in `ergebnis_id`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from appkern.auftraege import Auftraege, Auftrag, FalscherZustand
from appkern.kellerwolke import (
    Aktion, Anfrage, Kellerwolke, KellerwolkeFehler, Konflikt, NichtErreichbar, SchluesselUngueltig,
)

logger = logging.getLogger("appkern.anfragen")

WARTEN_S = 25.0       # so lange wartet die Kellerwolke beim Abholen auf eine neue Anfrage
MELDEN_S = 2.0        # Fortschritt höchstens so oft an die Kellerwolke
PAUSE_MAX_S = 60.0


class AnfrageEingabe(BaseModel):
    """Eingabe eines Auftrags, der eine Anfrage ausführt."""

    anfrage_id: UUID
    knoten_id: UUID
    aktion: str
    knoten_name: str = ""


@dataclass(frozen=True)
class Angebot:
    """Eine Aktion der App; `auftrag` ist die Art des Auftrags, die eine Anfrage im Hintergrund ausführt (bei Aktionen
    zum Öffnen leer: die Oberfläche der App nimmt sie an)."""

    aktion: Aktion
    auftrag: str | None = None

    def __post_init__(self) -> None:
        if self.aktion.art == "hintergrund" and not self.auftrag:
            raise ValueError(f"Aktion {self.aktion.kennung}: im Hintergrund braucht sie eine Art von Auftrag")


def anfrage_von(auftrag: Auftrag) -> str | None:
    wert = auftrag.eingabe.get("anfrage_id") if isinstance(auftrag.eingabe, dict) else None
    return str(wert) if wert else None


class Abholer:
    """Begleiter des Gerüsts (starten, verbunden, stoppen): meldet die Aktionen, holt Anfragen ab, führt sie als
    Aufträge aus und meldet den Stand zurück."""

    def __init__(self, angebote: Sequence[Angebot], auftraege: Auftraege, kellerwolke: Callable[[], Kellerwolke | None],
                 adresse: Callable[[], str | None] = lambda: None) -> None:
        self.angebote = {a.aktion.kennung: a for a in angebote}
        self.auftraege = auftraege
        self._kellerwolke = kellerwolke
        self._adresse = adresse
        self._laufend: dict[str, str] = {}          # Anfrage -> Auftrag
        self._gemeldet: dict[str, float] = {}       # Anfrage -> Zeitpunkt der letzten Meldung des Fortschritts
        self._sperre = asyncio.Lock()
        self._schleife: asyncio.Task | None = None
        self._rueckmeldung: asyncio.Task | None = None

    # --- Lebenszyklus (Begleiter) ---------------------------------------------------------------------------------

    async def starten(self) -> None:
        self._rueckmeldung = asyncio.create_task(self._rueckmelden(), name="anfragen-rueckmeldung")

    async def verbunden(self) -> None:
        """Nach jedem Aufbau der Zugänge: Aktionen melden, laufende Aufträge zuordnen, Abholen neu beginnen."""
        await self._schleife_beenden()
        kw = self._kellerwolke()
        if kw is None or not self.angebote:
            return
        for auftrag in (await self.auftraege.liste(zustand=("wartet", "laeuft"))).eintraege:
            anfrage = anfrage_von(auftrag)
            if anfrage:
                self._laufend[anfrage] = auftrag.id
        self._schleife = asyncio.create_task(self._abholen(kw), name="anfragen-abholen")

    async def stoppen(self) -> None:
        await self._schleife_beenden()
        if self._rueckmeldung:
            self._rueckmeldung.cancel()
            await asyncio.gather(self._rueckmeldung, return_exceptions=True)

    async def _schleife_beenden(self) -> None:
        if self._schleife:
            self._schleife.cancel()
            await asyncio.gather(self._schleife, return_exceptions=True)
            self._schleife = None

    # --- Abholen --------------------------------------------------------------------------------------------------

    async def _abholen(self, kw: Kellerwolke) -> None:
        pause = 1.0
        gemeldet = False
        while True:
            try:
                if not gemeldet:
                    await kw.aktionen_melden([a.aktion for a in self.angebote.values()], self._adresse())
                    gemeldet = True
                for anfrage in await kw.anfragen_holen(WARTEN_S):
                    await self.uebernehmen(anfrage, kw)
                pause = 1.0
            except asyncio.CancelledError:
                raise
            except (NichtErreichbar, SchluesselUngueltig) as f:
                logger.info("Anfragen: Kellerwolke gerade nicht nutzbar (%s), neuer Versuch in %.0f s", f, pause)
                await asyncio.sleep(pause)
                pause = min(pause * 2, PAUSE_MAX_S)
            except Exception:  # noqa: BLE001 - das Abholen darf nie enden
                logger.exception("Anfragen: Abholen")
                await asyncio.sleep(pause)
                pause = min(pause * 2, PAUSE_MAX_S)

    async def uebernehmen(self, anfrage: Anfrage, kw: Kellerwolke | None = None) -> str | None:
        """Nimmt eine Anfrage im Hintergrund an und reiht ihren Auftrag ein; liefert dessen Kennung. Doppelt
        übernommen (Abholen und Dateiwahl zugleich) wird nie."""
        kw = kw or self._kellerwolke()
        if kw is None:
            return None
        schluessel = str(anfrage.id)
        async with self._sperre:
            if schluessel in self._laufend:
                return self._laufend[schluessel]
            angebot = self.angebote.get(anfrage.aktion)
            if angebot is None or not angebot.auftrag:
                await self._still(kw.anfrage_melden(anfrage.id, zustand="fehler",
                                                    meldung="Diese App kennt die Aktion nicht (mehr)"))
                return None
            try:
                await kw.anfrage_annehmen(anfrage.id)
            except Konflikt:
                return None                     # inzwischen abgebrochen oder abgelaufen
            # Als dict: die Art darf ein eigenes Eingabemodell haben, das AnfrageEingabe erweitert.
            eingabe = AnfrageEingabe(anfrage_id=anfrage.id, knoten_id=anfrage.knoten_id, aktion=anfrage.aktion,
                                     knoten_name=anfrage.knoten_name).model_dump(mode="json")
            auftrag = await self.auftraege.einreihen(angebot.auftrag, eingabe,
                                                     titel=f"{angebot.aktion.titel}: {anfrage.knoten_name}")
            self._laufend[schluessel] = auftrag.id
            return auftrag.id

    # --- Rückmeldung ----------------------------------------------------------------------------------------------

    async def _rueckmelden(self) -> None:
        while True:
            try:
                async for auftrag in self.auftraege.ereignisse():
                    if auftrag is not None and anfrage_von(auftrag):
                        await self._melden(auftrag)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - die Rückmeldung darf nie enden
                logger.exception("Anfragen: Rückmeldung")
                await asyncio.sleep(1.0)

    async def _melden(self, auftrag: Auftrag) -> None:
        anfrage = anfrage_von(auftrag)
        kw = self._kellerwolke()
        if kw is None or anfrage is None:
            return
        daten: dict[str, Any]
        if auftrag.zustand == "laeuft":
            jetzt = time.monotonic()
            if jetzt - self._gemeldet.get(anfrage, 0.0) < MELDEN_S:
                return
            self._gemeldet[anfrage] = jetzt
            daten = {"zustand": "laeuft", "fortschritt": auftrag.fortschritt, "meldung": auftrag.schritt or None}
        elif auftrag.zustand == "fertig":
            daten = {"zustand": "fertig", "ergebnis_id": (auftrag.ergebnis or {}).get("ergebnis_id"), "fortschritt": 1.0}
        elif auftrag.zustand == "fehler":
            daten = {"zustand": "fehler", "meldung": (auftrag.fehler or "Fehler")[:300]}
        elif auftrag.zustand == "abgebrochen":
            daten = {"zustand": "fehler", "meldung": "in der App abgebrochen"}
        else:
            return                              # wartet oder unterbrochen: die Anfrage bleibt offen
        try:
            await kw.anfrage_melden(anfrage, **daten)
        except Konflikt:
            # In der Kellerwolke abgebrochen oder abgelaufen: der Auftrag hört auf.
            if auftrag.zustand in ("wartet", "laeuft"):
                try:
                    await self.auftraege.abbrechen(auftrag.id)
                except FalscherZustand:
                    pass
        except KellerwolkeFehler as f:
            logger.warning("Anfragen: Stand von %s nicht gemeldet (%s)", anfrage, f)
        if auftrag.zustand not in ("wartet", "laeuft"):
            self._laufend.pop(anfrage, None)
            self._gemeldet.pop(anfrage, None)

    @staticmethod
    async def _still(aufruf) -> None:
        try:
            await aufruf
        except KellerwolkeFehler:
            pass
