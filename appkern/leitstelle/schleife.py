"""Werkzeugschleife: ein Gesprächsmodell der Leitstelle ruft Werkzeuge auf, die App führt sie aus, mehrstufig.

Eine Stelle für alle Apps (Assistent, Fundus, ...): Runden mit Strom, Werkzeugaufrufe zusammengesetzt, lesende
Werkzeuge bis `gleichzeitig` nebeneinander, die übrigen der Reihe nach, Ergebnisse in der Reihenfolge der Aufrufe,
Rundengrenze, Nachladen weiterer Werkzeuge. Was ein Werkzeug tut, weiß die Schleife nicht: jede App reicht ihre
Werkzeuge als `Werkzeug` herein (eigene, die eines Dienstes wie Fundus, die der Leitstelle).

    schleife = Schleife(runden=8)
    async for e in schleife.laufen(leitstelle, nachrichten, [uhrzeit, bild_lesen], modell="qwen/qwen3-next-80b",
                                   titel="Frage"):
        if isinstance(e, TextStueck): ...        # Text der laufenden Runde anhängen
        if isinstance(e, RundeEnde): ...         # e.aufrufe: diese Runde ruft Werkzeuge, der Text davor war Vorrede
        if isinstance(e, Aufruf): ...            # Schritt anzeigen
        if isinstance(e, Ergebnis): ...         # Schritt fertig (e.ergebnis.fehler: rot)
        if isinstance(e, Antwort): ...           # fertig

Abgebrochen wird von außen über die Aufgabe (asyncio): der Strom zur Leitstelle schließt, laufende Werkzeuge enden an
ihren Haltepunkten. Ein Werkzeug, das auf einen Menschen wartet (Freigabe), wartet in seinem `ausfuehren` ohne Uhr.
Jede Anfrage trägt die laufende Arbeit (`X-Leitstelle-Arbeit`), wenn die App sie setzt (Aufträge tun das von selbst).
"""

from __future__ import annotations

import asyncio
import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from .modelle import Ende, Nachricht, Prioritaet, Stueck, Verbrauch, Wartet, Werkzeugaufruf
from .zugang import Leitstelle

NACHLADEN = "weitere_werkzeuge"


class WerkzeugErgebnis(BaseModel):
    """Was ein Werkzeug zurückgibt. `text` geht an das Modell; `rat` wird angehängt; `daten` sind strukturierte Angaben
    für die App (Belege, Kurznamen, erzeugte Gegenstände), die das Modell nicht sieht."""

    model_config = ConfigDict(frozen=True)

    text: str
    fehler: bool = False
    rat: str = ""
    daten: JsonValue = None

    def fuer_modell(self, grenze: int) -> str:
        text = self.text + (f"\nRat: {self.rat}" if self.rat else "")
        if len(text) <= grenze:
            return text
        return text[:grenze] + f"\n[gekürzt: {len(text) - grenze} weitere Zeichen; bei Bedarf gezielt nachlesen]"


class Werkzeug(ABC):
    """Ein Werkzeug, wie das Modell es sieht (Name, Beschreibung, JSON-Schema der Argumente) und wie die App es
    ausführt. `nur_lesend`: darf neben anderen laufen (ändert nichts, fragt keinen Menschen)."""

    name: str
    beschreibung: str
    nur_lesend: bool = True

    @abstractmethod
    def schema(self) -> dict[str, Any]:
        """JSON-Schema der Argumente (ein Objekt)."""

    @abstractmethod
    async def ausfuehren(self, argumente: dict[str, Any]) -> WerkzeugErgebnis:
        """Ausführen; ein erwarteter Fehlschlag kommt als Ergebnis mit `fehler`, nie als Ausnahme."""

    def fuer_fassade(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.beschreibung, "parameters": self.schema()}}


class ModellWerkzeug(Werkzeug):
    """Ein Werkzeug mit einem Pydantic-Modell als Argumenten: das Schema kommt aus dem Modell, falsche Argumente gehen
    mit dem Grund an das Gesprächsmodell zurück (es berichtigt sie in der nächsten Runde)."""

    def __init__(self, name: str, beschreibung: str, argumente: type[BaseModel],
                 ausfuehren: Callable[[Any], Awaitable[WerkzeugErgebnis]], *, nur_lesend: bool = True) -> None:
        self.name, self.beschreibung, self.nur_lesend = name, beschreibung, nur_lesend
        self._modell = argumente
        self._ausfuehren = ausfuehren

    def schema(self) -> dict[str, Any]:
        schema = self._modell.model_json_schema()
        schema.pop("title", None)
        return schema

    async def ausfuehren(self, argumente: dict[str, Any]) -> WerkzeugErgebnis:
        try:
            werte = self._modell.model_validate(argumente)
        except ValidationError as f:
            gruende = "; ".join(f"{'.'.join(str(t) for t in e['loc']) or 'Argumente'}: {e['msg']}" for e in f.errors())
            return WerkzeugErgebnis(text=f"{self.name}: Argumente passen nicht ({gruende})", fehler=True)
        return await self._ausfuehren(werte)


# --- Ereignisse ------------------------------------------------------------------------------------------------------


class _Ereignis(BaseModel):
    model_config = ConfigDict(frozen=True)
    runde: int


class RundeBeginnt(_Ereignis):
    art: Literal["runde"] = "runde"
    werkzeuge: list[str] = Field(default_factory=list)


class Warten(_Ereignis):
    """Die Leitstelle lässt den Auftrag warten (Modell wird geladen, Platz belegt, Rechner schläft)."""

    art: Literal["wartet"] = "wartet"
    grund: str
    sekunden: int | None = None


class TextStueck(_Ereignis):
    art: Literal["text"] = "text"
    text: str


class RundeEnde(_Ereignis):
    """Eine Runde endet mit Werkzeugaufrufen; `text` war die Vorrede dazu (nicht die Antwort)."""

    art: Literal["runde_ende"] = "runde_ende"
    text: str
    aufrufe: list[Werkzeugaufruf]


class Aufruf(_Ereignis):
    art: Literal["aufruf"] = "aufruf"
    nr: int
    aufruf_id: str
    werkzeug: str
    argumente: dict[str, JsonValue]


class Ergebnis(_Ereignis):
    art: Literal["ergebnis"] = "ergebnis"
    nr: int
    aufruf_id: str
    werkzeug: str
    ergebnis: WerkzeugErgebnis
    dauer_ms: int


class Antwort(_Ereignis):
    art: Literal["antwort"] = "antwort"
    text: str
    abgebrochen: bool = False             # in der Leitstelle abgebrochen; `text` ist das Bisherige
    modell: str | None = None
    verbrauch: Verbrauch | None = None


class Grenze(_Ereignis):
    """Die Rundengrenze ist erreicht, ohne dass eine Antwort kam."""

    art: Literal["grenze"] = "grenze"


Schleifenereignis = RundeBeginnt | Warten | TextStueck | RundeEnde | Aufruf | Ergebnis | Antwort | Grenze


class _NachladenArgumente(BaseModel):
    namen: list[str] = Field(..., min_length=1, max_length=10, description="Namen der Werkzeuge aus dem Verzeichnis.")


def _argumente(roh: str) -> tuple[dict[str, Any], str]:
    if not roh.strip():
        return {}, ""
    try:
        werte = json.loads(roh)
    except ValueError as f:
        return {}, f"Die Argumente sind kein gültiges JSON: {f}"
    return (werte, "") if isinstance(werte, dict) else ({}, "Die Argumente müssen ein JSON-Objekt sein")


class Schleife:
    def __init__(self, *, runden: int = 8, gleichzeitig: int = 3, ergebnis_zeichen: int = 14000) -> None:
        """`runden`: höchstens so viele Aufrufe des Modells; `gleichzeitig`: so viele lesende Werkzeuge nebeneinander;
        `ergebnis_zeichen`: so viel eines Ergebnisses sieht das Modell."""
        self.runden = runden
        self.gleichzeitig = gleichzeitig
        self.ergebnis_zeichen = ergebnis_zeichen

    async def laufen(self, leitstelle: Leitstelle, nachrichten: Sequence[Nachricht], werkzeuge: Sequence[Werkzeug], *,
                     modell: str | None = None, titel: str = "", prioritaet: Prioritaet | None = None,
                     nachladbar: Sequence[Werkzeug] = (), runden: int | None = None,
                     **optionen: Any) -> AsyncIterator[Schleifenereignis]:
        """`nachrichten`: System, Verlauf und Frage; die Schleife hängt Aufrufe und Ergebnisse an eine eigene Kopie.
        `nachladbar`: Werkzeuge, die das Modell bei Bedarf über `weitere_werkzeuge` dazuholt (spart Kontext).
        `optionen` gehen an jeden Aufruf des Modells (temperature, max_tokens ...)."""
        verlauf = list(nachrichten)
        aktiv: dict[str, Werkzeug] = {w.name: w for w in werkzeuge}
        vorrat: dict[str, Werkzeug] = {w.name: w for w in nachladbar if w.name not in aktiv}
        nr = 0
        grenze = runden or self.runden
        for runde in range(1, grenze + 1):
            schemata = [w.fuer_fassade() for w in aktiv.values()]
            if vorrat:
                schemata.append(self._nachladen_schema(vorrat))
            yield RundeBeginnt(runde=runde, werkzeuge=list(aktiv))
            text, ende = "", Ende()
            async for e in leitstelle.chat_strom(verlauf, modell=modell, titel=titel, prioritaet=prioritaet,
                                                 **({"tools": schemata} if schemata else {}), **optionen):
                if isinstance(e, Wartet):
                    yield Warten(runde=runde, grund=e.grund, sekunden=e.sekunden)
                elif isinstance(e, Stueck):
                    text += e.text
                    yield TextStueck(runde=runde, text=e.text)
                else:
                    ende = e
            if ende.abgebrochen or not ende.werkzeugaufrufe:
                yield Antwort(runde=runde, text=text, abgebrochen=ende.abgebrochen, modell=ende.modell, verbrauch=ende.verbrauch)
                return
            yield RundeEnde(runde=runde, text=text, aufrufe=ende.werkzeugaufrufe)
            verlauf.append(Nachricht.assistent(text, ende.werkzeugaufrufe))
            nummern = {a.id: (nr := nr + 1) for a in ende.werkzeugaufrufe}
            for a in ende.werkzeugaufrufe:
                args, _ = _argumente(a.argumente)
                yield Aufruf(runde=runde, nr=nummern[a.id], aufruf_id=a.id, werkzeug=a.name, argumente=args)
            async for aufruf, ergebnis, dauer in self._ausfuehren(ende.werkzeugaufrufe, aktiv, vorrat):
                yield Ergebnis(runde=runde, nr=nummern[aufruf.id], aufruf_id=aufruf.id, werkzeug=aufruf.name,
                               ergebnis=ergebnis, dauer_ms=dauer)
                verlauf.append(Nachricht.ergebnis(aufruf.id, ergebnis.fuer_modell(self.ergebnis_zeichen)))
        yield Grenze(runde=grenze)

    @staticmethod
    def _nachladen_schema(vorrat: dict[str, Werkzeug]) -> dict[str, Any]:
        verzeichnis = "; ".join(f"{w.name}: {w.beschreibung.split('. ')[0]}" for w in vorrat.values())
        return {"type": "function", "function": {
            "name": NACHLADEN,
            "description": ("Lädt weitere Werkzeuge in dieses Gespräch, wenn die gezeigten nicht reichen. Verfügbar: "
                            f"{verzeichnis}."),
            "parameters": _NachladenArgumente.model_json_schema()}}

    async def _ausfuehren(self, aufrufe: Sequence[Werkzeugaufruf], aktiv: dict[str, Werkzeug],
                          vorrat: dict[str, Werkzeug]) -> AsyncIterator[tuple[Werkzeugaufruf, WerkzeugErgebnis, int]]:
        """Lesende nebeneinander (höchstens `gleichzeitig`), die übrigen der Reihe nach; geliefert wird in der
        Reihenfolge der Aufrufe, sobald ein Ergebnis und alle davor da sind."""
        platz = asyncio.Semaphore(self.gleichzeitig)
        reihe = asyncio.Lock()

        async def einer(a: Werkzeugaufruf) -> tuple[WerkzeugErgebnis, int]:
            beginn = time.monotonic()
            args, grund = _argumente(a.argumente)
            if grund:
                return WerkzeugErgebnis(text=f"{a.name}: {grund}", fehler=True), 0
            if a.name == NACHLADEN:
                return self._nachladen(args, aktiv, vorrat), 0
            w = aktiv.get(a.name)
            if w is None:
                bekannt = ", ".join(aktiv) or "keine"
                hinweis = " (erst mit weitere_werkzeuge laden)" if a.name in vorrat else ""
                return WerkzeugErgebnis(text=f"Ein Werkzeug {a.name} gibt es hier nicht{hinweis}. Verfügbar: {bekannt}.",
                                        fehler=True), 0
            async with platz if w.nur_lesend else reihe:
                ergebnis = await w.ausfuehren(args)
            return ergebnis, int((time.monotonic() - beginn) * 1000)

        aufgaben = [asyncio.create_task(einer(a)) for a in aufrufe]
        try:
            for a, aufgabe in zip(aufrufe, aufgaben, strict=True):
                ergebnis, dauer = await aufgabe
                yield a, ergebnis, dauer
        finally:
            for aufgabe in aufgaben:
                aufgabe.cancel()
            await asyncio.gather(*aufgaben, return_exceptions=True)

    @staticmethod
    def _nachladen(args: dict[str, Any], aktiv: dict[str, Werkzeug], vorrat: dict[str, Werkzeug]) -> WerkzeugErgebnis:
        namen = [n for n in (args.get("namen") or []) if isinstance(n, str)]
        neu = [n for n in namen if n in vorrat]
        for n in neu:
            aktiv[n] = vorrat.pop(n)
        unbekannt = [n for n in namen if n not in aktiv]
        teile = [f"Geladen: {', '.join(neu)}." if neu else "Nichts Neues geladen."]
        if unbekannt:
            teile.append(f"Nicht verfügbar: {', '.join(unbekannt)}.")
        return WerkzeugErgebnis(text=" ".join(teile) + " Die geladenen Werkzeuge stehen ab der nächsten Runde bereit.")
