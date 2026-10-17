"""Aufträge einer App: persistente Warteschlange mit Phasen, Fortschritt als Ereignisstrom, Abbruch, Wiederholen
und Fortsetzen nach einem Neustart.

Eine App meldet ihre Arten an (`Art`: Name, Phasen, Eingabemodell, die Arbeit selbst) und reiht Aufträge ein. Die
Arbeit bekommt einen `Kontext`: Eingabe, Fortschritt melden, Zwischenstand merken, Abbruch prüfen. Abgebrochen wird
gemeinsam, nie mit einer Uhr: die Arbeit fragt an ihren Haltepunkten `pruefen()`. Ein Neustart beendet keinen
Auftrag still: was lief, wird je Art fortgesetzt (Zwischenstand bleibt) oder als unterbrochen gezeigt; Wiederholen ist
dann ein Klick.

Fortschritt wird gedrosselt geschrieben (höchstens alle `DROSSEL_S`), ein Phasenwechsel immer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from pydantic import BaseModel

from appkern.datenbank import Datenbank
from appkern.protokoll import Protokoll

from .modelle import OFFEN, WIEDERHOLBAR, Auftrag, Phase, Seite, Zustand

logger = logging.getLogger("appkern.auftraege")

DROSSEL_S = 0.25
SCHEMA = [
    """
    CREATE TABLE auftrag (
        id               TEXT PRIMARY KEY,
        art              TEXT NOT NULL,
        titel            TEXT NOT NULL,
        zustand          TEXT NOT NULL CHECK (zustand IN ('wartet','laeuft','fertig','fehler','abgebrochen','unterbrochen')),
        eingabe          TEXT NOT NULL,
        ergebnis         TEXT,
        fehler           TEXT,
        fehler_spur      TEXT,
        fortschritt      REAL,
        schritt          TEXT NOT NULL DEFAULT '',
        phase            TEXT,
        zwischenstand    TEXT NOT NULL DEFAULT '{}',
        abbruch          INTEGER NOT NULL DEFAULT 0,
        stapel           TEXT,
        wiederholung_von TEXT,
        erstellt_am      TEXT NOT NULL,
        begonnen_am      TEXT,
        beendet_am       TEXT
    );
    CREATE INDEX auftrag_zustand_idx ON auftrag (zustand, erstellt_am);
    CREATE INDEX auftrag_stapel_idx ON auftrag (stapel);
    """,
]


class AuftragAbgebrochen(Exception):
    """Wird von `Kontext.pruefen()` geworfen, wenn der Mensch abgebrochen hat."""


class UnbekannteArt(ValueError):
    pass


class NichtGefunden(LookupError):
    pass


class FalscherZustand(ValueError):
    pass


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat()


Arbeit = Callable[["Kontext"], Awaitable[BaseModel | dict[str, Any] | None]]


@dataclass(frozen=True)
class Art:
    """Eine Art von Auftrag.

    `nach_neustart`: "fortsetzen" reiht einen beim Neustart laufenden Auftrag wieder ein (mit Zwischenstand),
    "anhalten" zeigt ihn als unterbrochen. `fortsetzbar`: Wiederholen übernimmt den Zwischenstand.
    """

    name: str
    titel: str
    arbeit: Arbeit
    eingabe: type[BaseModel] | None = None
    phasen: Sequence[Phase] = ()
    fortsetzbar: bool = False
    nach_neustart: Literal["fortsetzen", "anhalten"] = "anhalten"


@dataclass
class Kontext:
    """Was die Arbeit eines Auftrags in der Hand hat."""

    auftrag_id: str
    eingabe: Any                                   # das Eingabemodell der Art, sonst ein dict
    zwischenstand: dict[str, Any]
    _dienst: Auftraege = field(repr=False)
    _abbruch: asyncio.Event = field(repr=False)
    _zuletzt: float = 0.0

    @property
    def abbruch_gewuenscht(self) -> bool:
        return self._abbruch.is_set()

    async def pruefen(self) -> None:
        """Haltepunkt: wirft `AuftragAbgebrochen`, wenn abgebrochen wurde."""
        if self._abbruch.is_set():
            raise AuftragAbgebrochen()

    async def fortschritt(self, anteil: float | None, schritt: str = "", phase: str | None = None) -> None:
        jetzt = asyncio.get_running_loop().time()
        if phase is None and jetzt - self._zuletzt < DROSSEL_S:
            return
        self._zuletzt = jetzt
        await self._dienst._fortschritt(self.auftrag_id, anteil, schritt, phase)

    async def merken(self, **werte: Any) -> None:
        """Zwischenstand ergänzen und sofort sichern (JSON-fähige Werte); Grundlage fürs Fortsetzen."""
        self.zwischenstand.update(werte)
        await self._dienst._zwischenstand(self.auftrag_id, self.zwischenstand)


class Auftraege:
    def __init__(self, db: Datenbank, arten: Sequence[Art], *, gleichzeitig: int = 1, aufbewahren_tage: int = 30,
                 protokoll: Protokoll | None = None) -> None:
        """`protokoll`: jedes Ende eines Auftrags (fertig, Fehler, abgebrochen, unterbrochen) wird eingetragen."""
        self.db = db
        self.protokoll = protokoll
        self.arten = {a.name: a for a in arten}
        self.gleichzeitig = max(1, gleichzeitig)
        self.aufbewahren_tage = aufbewahren_tage
        self._laufend: dict[str, tuple[asyncio.Task, asyncio.Event]] = {}
        self._wecker = asyncio.Event()
        self._schleife: asyncio.Task | None = None
        self._hoerer: set[asyncio.Queue[Auftrag]] = set()

    # --- Lebenszyklus ------------------------------------------------------------------------------------------

    async def starten(self) -> None:
        """Im Lebenszyklus der App: Schema, Aufräumen nach einem Neustart, dann die Schleife."""
        await self.db.einrichten("auftraege", SCHEMA)
        for zeile in await self.db.zeilen("SELECT id, art FROM auftrag WHERE zustand='laeuft'"):
            art = self.arten.get(zeile["art"])
            if art and art.nach_neustart == "fortsetzen":
                await self.db.ausfuehren("UPDATE auftrag SET zustand='wartet', schritt='Nach Neustart fortgesetzt', "
                                         "abbruch=0 WHERE id=?", (zeile["id"],))
            else:
                await self.db.ausfuehren("UPDATE auftrag SET zustand='unterbrochen', fehler=?, beendet_am=? WHERE id=?",
                                         ("Durch einen Neustart unterbrochen", _jetzt(), zeile["id"]))
                await self._eintragen(await self.holen(zeile["id"]))
        self._schleife = asyncio.create_task(self._takt(), name="auftraege")

    async def stoppen(self) -> None:
        """Beim Herunterfahren: die Schleife endet; laufende Arbeit wird beendet und gilt beim nächsten Start als
        unterbrochen (oder wird fortgesetzt)."""
        if self._schleife:
            self._schleife.cancel()
            await asyncio.gather(self._schleife, return_exceptions=True)
            self._schleife = None
        aufgaben = [t for t, _ in self._laufend.values()]
        for t in aufgaben:
            t.cancel()
        await asyncio.gather(*aufgaben, return_exceptions=True)

    # --- Für die App ---------------------------------------------------------------------------------------------

    async def einreihen(self, art: str, eingabe: BaseModel | dict[str, Any] | None = None, *, titel: str = "",
                        stapel: str | None = None) -> Auftrag:
        a = self.arten.get(art)
        if a is None:
            raise UnbekannteArt(f"Unbekannte Art: {art}")
        daten = self._eingabe_json(a, eingabe)
        auftrag_id = str(uuid.uuid4())
        await self.db.ausfuehren(
            "INSERT INTO auftrag (id, art, titel, zustand, eingabe, stapel, erstellt_am) VALUES (?,?,?,?,?,?,?)",
            (auftrag_id, art, titel or a.titel, "wartet", json.dumps(daten, ensure_ascii=False), stapel, _jetzt()))
        auftrag = await self.holen(auftrag_id)
        self._melden(auftrag)
        self._wecker.set()
        return auftrag

    @staticmethod
    def _eingabe_json(art: Art, eingabe: BaseModel | dict[str, Any] | None) -> dict[str, Any]:
        if art.eingabe is not None:
            modell = eingabe if isinstance(eingabe, art.eingabe) else art.eingabe.model_validate(eingabe or {})
            return modell.model_dump(mode="json")
        if isinstance(eingabe, BaseModel):
            return eingabe.model_dump(mode="json")
        return dict(eingabe or {})

    async def holen(self, auftrag_id: str) -> Auftrag:
        zeile = await self.db.zeile("SELECT * FROM auftrag WHERE id=?", (auftrag_id,))
        if zeile is None:
            raise NichtGefunden(f"Auftrag {auftrag_id} nicht gefunden")
        return self._als_auftrag(zeile)

    async def liste(self, *, zustand: Sequence[Zustand] = (), art: str | None = None, stapel: str | None = None,
                    grenze: int = 50, versatz: int = 0) -> Seite:
        """Neueste zuerst, seitenweise."""
        bedingungen, werte = [], []
        if zustand:
            bedingungen.append(f"zustand IN ({','.join('?' * len(zustand))})")
            werte += list(zustand)
        if art:
            bedingungen.append("art=?")
            werte.append(art)
        if stapel:
            bedingungen.append("stapel=?")
            werte.append(stapel)
        wo = f"WHERE {' AND '.join(bedingungen)}" if bedingungen else ""
        gesamt = (await self.db.zeile(f"SELECT count(*) AS n FROM auftrag {wo}", werte))["n"]
        zeilen = await self.db.zeilen(f"SELECT * FROM auftrag {wo} ORDER BY erstellt_am DESC, id LIMIT ? OFFSET ?",
                                      [*werte, max(1, min(grenze, 500)), max(0, versatz)])
        return Seite(eintraege=[self._als_auftrag(z) for z in zeilen], gesamt=gesamt)

    async def abbrechen(self, auftrag_id: str) -> Auftrag:
        """Wartend: sofort abgebrochen. Laufend: die Arbeit hört am nächsten Haltepunkt auf."""
        auftrag = await self.holen(auftrag_id)
        if auftrag.zustand == "wartet":
            await self.db.ausfuehren("UPDATE auftrag SET zustand='abgebrochen', beendet_am=? WHERE id=? AND zustand='wartet'",
                                     (_jetzt(), auftrag_id))
        elif auftrag.zustand == "laeuft":
            await self.db.ausfuehren("UPDATE auftrag SET abbruch=1, schritt='Wird abgebrochen' WHERE id=?", (auftrag_id,))
            laufend = self._laufend.get(auftrag_id)
            if laufend:
                laufend[1].set()
        else:
            raise FalscherZustand(f"Ein Auftrag im Zustand {auftrag.zustand} lässt sich nicht abbrechen")
        vorher = auftrag.zustand
        auftrag = await self.holen(auftrag_id)
        self._melden(auftrag)
        if vorher == "wartet":
            await self._eintragen(auftrag)
        return auftrag

    async def wiederholen(self, auftrag_id: str) -> Auftrag:
        """Neuer Auftrag mit derselben Eingabe; bei fortsetzbaren Arten mit dem Zwischenstand des alten."""
        alt = await self.db.zeile("SELECT * FROM auftrag WHERE id=?", (auftrag_id,))
        if alt is None:
            raise NichtGefunden(f"Auftrag {auftrag_id} nicht gefunden")
        if alt["zustand"] not in WIEDERHOLBAR:
            raise FalscherZustand(f"Ein Auftrag im Zustand {alt['zustand']} lässt sich nicht wiederholen")
        art = self.arten.get(alt["art"])
        if art is None:
            raise UnbekannteArt(f"Unbekannte Art: {alt['art']}")
        neu_id = str(uuid.uuid4())
        zwischen = alt["zwischenstand"] if art.fortsetzbar else "{}"
        await self.db.ausfuehren(
            "INSERT INTO auftrag (id, art, titel, zustand, eingabe, zwischenstand, stapel, wiederholung_von, erstellt_am) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (neu_id, alt["art"], alt["titel"], "wartet", alt["eingabe"], zwischen, alt["stapel"], auftrag_id, _jetzt()))
        auftrag = await self.holen(neu_id)
        self._melden(auftrag)
        self._wecker.set()
        return auftrag

    async def entfernen(self, auftrag_id: str) -> None:
        """Einen beendeten Auftrag aus der Liste nehmen (die Ergebnisse der App bleiben, wo sie sind)."""
        auftrag = await self.holen(auftrag_id)
        if auftrag.zustand in OFFEN:
            raise FalscherZustand("Offene Aufträge erst abbrechen")
        await self.db.ausfuehren("DELETE FROM auftrag WHERE id=?", (auftrag_id,))

    async def aufraeumen(self) -> int:
        """Beendete Aufträge, älter als `aufbewahren_tage`, aus der Liste nehmen."""
        grenze = (datetime.now(timezone.utc) - timedelta(days=self.aufbewahren_tage)).isoformat()
        return await self.db.ausfuehren(
            "DELETE FROM auftrag WHERE zustand NOT IN ('wartet','laeuft') AND beendet_am IS NOT NULL AND beendet_am < ?",
            (grenze,))

    async def ereignisse(self, herzschlag_s: float | None = None) -> AsyncIterator[Auftrag | None]:
        """Jeder neue Stand eines Auftrags. Zuerst die offenen, dann alles, was geschieht. Mit `herzschlag_s` kommt
        nach so langer Stille ein `None` (etwa für eine Lebenszeile im Ereignisstrom). Ein zu langsamer Leser
        verliert Zwischenstände, nie den Endstand (der kommt mit dem nächsten Abruf)."""
        schlange: asyncio.Queue[Auftrag] = asyncio.Queue(maxsize=256)
        self._hoerer.add(schlange)
        try:
            for a in (await self.liste(zustand=OFFEN, grenze=500)).eintraege:
                yield a
            while True:
                try:
                    yield await asyncio.wait_for(schlange.get(), herzschlag_s)
                except TimeoutError:
                    yield None
        finally:
            self._hoerer.discard(schlange)

    # --- Innen ---------------------------------------------------------------------------------------------------

    def _melden(self, auftrag: Auftrag) -> None:
        for s in list(self._hoerer):
            try:
                s.put_nowait(auftrag)
            except asyncio.QueueFull:
                pass

    def _als_auftrag(self, z: dict[str, Any]) -> Auftrag:
        art = self.arten.get(z["art"])
        return Auftrag(
            id=z["id"], art=z["art"], titel=z["titel"], zustand=z["zustand"], eingabe=json.loads(z["eingabe"]),
            ergebnis=json.loads(z["ergebnis"]) if z["ergebnis"] else None, fehler=z["fehler"],
            fortschritt=z["fortschritt"], schritt=z["schritt"], phase=z["phase"],
            phasen=list(art.phasen) if art else [], abbruch_gewuenscht=bool(z["abbruch"]),
            fortsetzbar=bool(art and art.fortsetzbar), stapel=z["stapel"], wiederholung_von=z["wiederholung_von"],
            erstellt_am=z["erstellt_am"], begonnen_am=z["begonnen_am"], beendet_am=z["beendet_am"])

    async def _fortschritt(self, auftrag_id: str, anteil: float | None, schritt: str, phase: str | None) -> None:
        anteil = None if anteil is None else min(1.0, max(0.0, anteil))
        if phase is None:
            await self.db.ausfuehren("UPDATE auftrag SET fortschritt=?, schritt=? WHERE id=?", (anteil, schritt, auftrag_id))
        else:
            await self.db.ausfuehren("UPDATE auftrag SET fortschritt=?, schritt=?, phase=? WHERE id=?",
                                     (anteil, schritt, phase, auftrag_id))
        self._melden(await self.holen(auftrag_id))

    async def _zwischenstand(self, auftrag_id: str, stand: dict[str, Any]) -> None:
        await self.db.ausfuehren("UPDATE auftrag SET zwischenstand=? WHERE id=?",
                                 (json.dumps(stand, ensure_ascii=False), auftrag_id))

    async def _nehmen(self) -> dict[str, Any] | None:
        """Den ältesten wartenden Auftrag atomar übernehmen."""

        def arbeit(v):
            z = v.execute("SELECT * FROM auftrag WHERE zustand='wartet' ORDER BY erstellt_am, id LIMIT 1").fetchone()
            if z is None:
                return None
            v.execute("UPDATE auftrag SET zustand='laeuft', begonnen_am=coalesce(begonnen_am, ?) WHERE id=?",
                      (_jetzt(), z["id"]))
            return dict(z) | {"zustand": "laeuft"}

        return await self.db.transaktion(arbeit)

    async def _takt(self) -> None:
        while True:
            # Erst den Wecker zurücksetzen, dann nehmen: wer während des Nehmens einreiht, weckt die nächste Runde.
            self._wecker.clear()
            while len(self._laufend) < self.gleichzeitig:
                zeile = await self._nehmen()
                if zeile is None:
                    break
                abbruch = asyncio.Event()
                aufgabe = asyncio.create_task(self._ausfuehren(zeile, abbruch), name=f"auftrag-{zeile['id'][:8]}")
                self._laufend[zeile["id"]] = (aufgabe, abbruch)
            await self._wecker.wait()

    async def _ausfuehren(self, zeile: dict[str, Any], abbruch: asyncio.Event) -> None:
        auftrag_id = zeile["id"]
        try:
            self._melden(await self.holen(auftrag_id))
            art = self.arten.get(zeile["art"])
            if art is None:
                await self._beenden(auftrag_id, "fehler", fehler=f"Unbekannte Art: {zeile['art']}")
                return
            eingabe = json.loads(zeile["eingabe"])
            kontext = Kontext(auftrag_id=auftrag_id, eingabe=art.eingabe.model_validate(eingabe) if art.eingabe else eingabe,
                              zwischenstand=json.loads(zeile["zwischenstand"] or "{}"), _dienst=self, _abbruch=abbruch)
            try:
                ergebnis = await art.arbeit(kontext)
            except AuftragAbgebrochen:
                await self._beenden(auftrag_id, "abgebrochen")
            except asyncio.CancelledError:
                raise
            except Exception as f:  # noqa: BLE001 - jeder Fehler der Arbeit gehört in den Auftrag, nie ins Leere
                meldung = f"{type(f).__name__}: {f}".strip().rstrip(":").strip() or type(f).__name__
                logger.exception("Auftrag %s (%s) fehlgeschlagen", auftrag_id[:8], zeile["art"])
                await self._beenden(auftrag_id, "fehler", fehler=meldung, spur=traceback.format_exc()[-2000:])
            else:
                daten = ergebnis.model_dump(mode="json") if isinstance(ergebnis, BaseModel) else ergebnis
                await self._beenden(auftrag_id, "fertig", ergebnis=daten)
        finally:
            self._laufend.pop(auftrag_id, None)
            self._wecker.set()

    async def _beenden(self, auftrag_id: str, zustand: Zustand, *, ergebnis: dict[str, Any] | None = None,
                       fehler: str | None = None, spur: str | None = None) -> None:
        fertig = zustand == "fertig"
        await self.db.ausfuehren(
            "UPDATE auftrag SET zustand=?, ergebnis=?, fehler=?, fehler_spur=?, beendet_am=?, "
            "fortschritt=CASE WHEN ? THEN 1.0 ELSE fortschritt END, schritt=CASE WHEN ? THEN '' ELSE schritt END WHERE id=?",
            (zustand, json.dumps(ergebnis, ensure_ascii=False) if ergebnis is not None else None, fehler, spur, _jetzt(),
             fertig, fertig, auftrag_id))
        auftrag = await self.holen(auftrag_id)
        self._melden(auftrag)
        await self._eintragen(auftrag)

    async def _eintragen(self, auftrag: Auftrag) -> None:
        if self.protokoll is None:
            return
        await self.protokoll.eintragen(
            f"auftrag.{auftrag.zustand}", auftrag.fehler or "",
            stufe="fehler" if auftrag.zustand == "fehler" else ("warnung" if auftrag.zustand != "fertig" else "info"),
            bezug_art="auftrag", bezug_id=auftrag.id, bezug_name=auftrag.titel, daten={"art": auftrag.art})
