"""Vorlesen: der eine Weg jeder App zur Sprachausgabe. Gesprochen wird von der Vertonung, die die Stimmen und ihre
Freigaben hält (HELF-73, vorher eine eigene App Vorlesen): ihr Strom `POST /api/v1/sprechen/strom` liefert Satz für
Satz, das Sprechmodell bleibt im Klangwerk hinter der Leitstelle. Eine App ruft die Vertonung mit ihrem App-Schlüssel
der Kellerwolke und im Auftrag der Person (über `geruest.verbund`).

    class AppEinstellungen(Grundeinstellungen, VorlesenEinstellungen): ...   # Vertonung und Vorlesestimme (Verbindungen)

    vorlesen = Vorlesen(geruest)            # Angebote für beide Felder, Verbindung in der Fußleiste
    app.include_router(vorlesen.router())   # POST /api/v1/vorlesen für den Vorleser der Oberfläche, GET: ist es da?

    # mit eigener Prüfung vorher (etwa Rechte an einer Karte):
    return await vorlesen.antwort(vorlesen.zeilen(text, sitzung=sitzung))

Die Vertonung nimmt je Aufruf höchstens 8000 Zeichen; längere Texte teilt der Baustein an Satzgrenzen (`appkern.saetze`)
und zählt die Sätze über alle Teile durch. Das Format des Stroms (NDJSON, je Zeile `art` satz, ende oder fehler; `satz`
mit `nr`, `text` und dem Ton als Base64-WAV in `ton`) liest der Vorleser der Oberfläche (`vorleser`, mit Vorlauf). Was
vor dem ersten Satz scheitert, ist ein `VorlesenFehler` mit Grund und Status, danach kommt eine Zeile `fehler`.

Die Vorlesestimme wählt jede App für sich (Feld `vorlesen_stimme`) aus dem, was die Vertonung ihr gerade anbietet: ihr
Katalog und die privaten Stimmen, die sie genau dieser App freigibt. Die Auswahl kommt jedes Mal aus der Vertonung, nie
aus einer festen Liste; ohne Wahl spricht die Stimme ab Werk der Vertonung."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from appkern.app.einstellungen import VERBINDUNGEN
from appkern.einstellungen import Angebot, Option
from appkern.saetze import saetze, stuecke
from appkern.verbund import ABFRAGE, SITZUNG, VerbundFehler

if TYPE_CHECKING:
    from appkern.app import Geruest

#: der Strom der Vertonung, Satz für Satz
STROM = "/api/v1/sprechen/strom"
#: so viel Text nimmt der Baustein am Stück; was länger ist, lehnt er ab
TEXT_HOECHSTENS = 100_000
#: so groß ist ein Teil für einen Aufruf der Vertonung (sie nimmt bis 8000 Zeichen)
TEIL_HOECHSTENS = 7_500
#: so beginnt der Wert einer Katalogstimme (wie die Vertonung ihre Kennungen schreibt)
KATALOG = "katalog:"
NDJSON = "application/x-ndjson"


class VorlesenEinstellungen(BaseModel):
    """Adresse der Vertonung und Vorlesestimme; eine App erbt das zusätzlich zu `Grundeinstellungen`."""
    vertonung_adresse: str = Field("", title="Vertonung", json_schema_extra=VERBINDUNGEN,
                                   description="Adresse der Vertonung: sie liest vor (Lautsprecher) und hält die Stimmen "
                                               "samt Freigaben. Leer: ohne Vorlesen.")
    vorlesen_stimme: str = Field("", title="Vorlesestimme", json_schema_extra=VERBINDUNGEN,
                                 description="Mit dieser Stimme liest die Vertonung für diese App: aus ihrem Katalog oder "
                                             "eine private Stimme, die sie dieser App freigibt. Leer: die Stimme ab Werk "
                                             "der Vertonung.")


class Vorlesetext(BaseModel):
    text: str = Field(min_length=1, max_length=TEXT_HOECHSTENS)


class VorlesenFehler(Exception):
    """Vorlesen ging nicht, bevor etwas gesprochen war; `meldung` in Worten, `status` für die Antwort der App."""

    def __init__(self, meldung: str, status: int) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        self.status = status


def fehler_aus(f: VerbundFehler) -> VorlesenFehler:
    """Ein Fehler des Verbunds als Grund für die Person. Eine 401 der Vertonung geht nie als 401 weiter (sonst meldete
    die Oberfläche die Person ab, Lehre 39 des Appkerns)."""
    if f.status is None:
        if f.meldung == "nicht eingerichtet":
            return VorlesenFehler("Vorlesen ist nicht eingerichtet (Einstellungen, Verbindungen, Vertonung)", 503)
        return VorlesenFehler(f"Die Vertonung ist gerade nicht erreichbar ({f.meldung})", 503)
    if f.status in (401, 403):
        return VorlesenFehler(f"Die Vertonung lässt das nicht zu: {f.meldung}", 403)
    if f.status in (400, 413, 422):
        return VorlesenFehler(f"Die Vertonung lehnt den Text ab: {f.meldung}", 400)
    return VorlesenFehler(f"Die Vertonung meldet: {f.meldung}", 502)


def fehlerzeile(meldung: str) -> bytes:
    return json.dumps({"art": "fehler", "meldung": meldung}, ensure_ascii=False).encode() + b"\n"


def stimmwahl(stimme: str) -> dict[str, str] | None:
    """Die Wahl im Format der Vertonung: `katalog:<name>` oder die Kennung einer privaten Stimme; leer: keine."""
    if not stimme:
        return None
    if stimme.startswith(KATALOG):
        return {"art": "katalog", "name": stimme.removeprefix(KATALOG)}
    return {"art": "klon", "knoten_id": stimme}


def teile(text: str, hoechstens: int = TEIL_HOECHSTENS) -> list[str]:
    """Der Text in Teilen bis `hoechstens` Zeichen, an Satzgrenzen; ein überlanger Satz an Teilsatz- und Wortgrenzen.
    Absätze bleiben als Leerzeile erhalten."""
    stuecke_: list[str] = []
    for s in saetze(text):
        for st in stuecke(s.text, hoechstens):
            stuecke_.append(st + ("\n\n" if s.absatz_ende else " "))
    ergebnis: list[str] = []
    for st in stuecke_:
        if ergebnis and len(ergebnis[-1]) + len(st) <= hoechstens:
            ergebnis[-1] += st
        else:
            ergebnis.append(st)
    return [e.strip() for e in ergebnis if e.strip()]


class Vorlesen:
    def __init__(self, geruest: Geruest, *, name: str = "Vertonung") -> None:
        """Bietet für die Adresse die Apps des Verzeichnisses an, für die Vorlesestimme die Stimmen der Vertonung, und
        stellt die Vertonung zu den Verbindungen. Die Einstellungen der App müssen `VorlesenEinstellungen` erben."""
        felder = geruest.einstellungen.modell.model_fields
        if "vertonung_adresse" not in felder or "vorlesen_stimme" not in felder:
            raise TypeError("Die Einstellungen der App erben VorlesenEinstellungen nicht")
        self.g = geruest
        geruest.einstellungen.anbieten("vertonung_adresse", geruest.verbund.angebot(name, "vertonung", self.adresse))
        geruest.einstellungen.anbieten("vorlesen_stimme", self.stimmen_angebot)
        geruest.verbund.anmelden(name, self.adresse)

    def adresse(self) -> str:
        return str(self.g.einstellungen.stand.vertonung_adresse).strip().rstrip("/")

    def stimme(self) -> str:
        return str(self.g.einstellungen.stand.vorlesen_stimme).strip()

    @property
    def da(self) -> bool:
        """Ist eine Vertonung eingetragen? (Ob sie gerade antwortet, sagen die Verbindungen.)"""
        return bool(self.adresse())

    async def stimmen_angebot(self) -> Angebot:
        """Auswahl für die Vorlesestimme, jedes Mal aus der Vertonung (`GET /api/v1/stimmen`, mit dem App-Schlüssel
        dieser App): ihr Katalog und die privaten Stimmen, die sie dieser App freigibt; dazu leer für die Stimme ab
        Werk."""
        optionen = [Option(wert="", titel="Stimme ab Werk", hinweis="wie in der Vertonung eingestellt")]
        if not self.da:
            return Angebot(optionen=optionen, eigener_wert=False, stand="erst die Adresse der Vertonung eintragen")
        anzahl, stand = 0, ""
        for bereich, hinweis in (("privat", "private Stimme, für diese App freigegeben"), ("katalog", "Katalog")):
            try:
                antwort = await self.g.verbund.anfrage("GET", self.adresse(), "/api/v1/stimmen", timeout=ABFRAGE,
                                                       params={"bereich": bereich})
            except VerbundFehler as f:
                if f.status in (401, 403):           # private Stimmen gibt die Vertonung dieser App nicht frei
                    continue
                stand = f"Vertonung antwortet nicht: {f.meldung}"
                break
            stimmen = antwort.json()
            optionen += [Option(wert=str(s["id"]), titel=str(s["name"]), hinweis=hinweis) for s in stimmen]
            anzahl += len(stimmen)
        return Angebot(optionen=optionen, eigener_wert=False, stand=stand or f"{anzahl} Stimmen")

    async def zeilen(self, text: str, *, sitzung: str | None = None) -> AsyncIterator[bytes]:
        """Die Zeilen der Vertonung für `text`, je Zeile mit Zeilenende, die Sätze über alle Teile durchgezählt, am Ende
        eine Zeile `ende`. Lehnt sie ab oder ist sie nicht erreichbar, bevor ein Satz kam: `VorlesenFehler`. Scheitert
        es danach: eine Zeile `fehler`. Bricht der Leser ab, endet die Anfrage und die Vertonung spricht nicht weiter."""
        if not self.da:
            raise VorlesenFehler("Vorlesen ist nicht eingerichtet (Einstellungen, Verbindungen, Vertonung)", 503)
        if len(text) > TEXT_HOECHSTENS:
            raise VorlesenFehler(f"Der Text ist länger als {TEXT_HOECHSTENS} Zeichen", 400)
        nr, dauer_ms = 0, 0
        koerper: dict[str, Any] = {"ausschreiben": True}
        if (wahl := stimmwahl(self.stimme())) is not None:
            koerper["stimme"] = wahl
        try:
            for teil in teile(text):
                async with self.g.verbund.strom("POST", self.adresse(), STROM, sitzung=sitzung,
                                                json={**koerper, "text": teil}) as antwort:
                    async for roh in antwort.aiter_lines():
                        if not roh.strip():
                            continue
                        z = json.loads(roh)
                        if z.get("art") == "satz":
                            yield json.dumps({**z, "nr": nr}, ensure_ascii=False).encode() + b"\n"
                            nr += 1
                            dauer_ms += int(z.get("dauer_ms") or 0)
                        elif z.get("art") == "fehler":
                            yield fehlerzeile(str(z.get("meldung") or "Vorlesen brach ab"))
                            return
            yield json.dumps({"art": "ende", "saetze": nr, "dauer_ms": dauer_ms}).encode() + b"\n"
        except VerbundFehler as f:
            if not nr:
                raise fehler_aus(f) from f
            yield fehlerzeile(f"Vorlesen brach ab: {f.meldung}")

    async def antwort(self, zeilen: AsyncIterator[bytes]) -> StreamingResponse:
        """Der Strom als Antwort an den Browser. Die erste Zeile wird abgewartet: was vorher scheitert, ist noch eine
        Antwort mit Grund und Status (`HTTPException`), kein abgebrochener Strom."""
        try:
            erste = await anext(zeilen)
        except StopAsyncIteration:
            erste = b""
        except VorlesenFehler as f:
            raise HTTPException(f.status, f.meldung) from f

        async def alles() -> AsyncIterator[bytes]:
            yield erste
            async for z in zeilen:
                yield z

        return StreamingResponse(alles(), media_type=NDJSON, headers={"Cache-Control": "no-cache"})

    def router(self) -> APIRouter:
        """`POST /api/v1/vorlesen` mit `{"text": ...}`: der Strom für den Vorleser der Oberfläche, im Auftrag der
        angemeldeten Person; `GET /api/v1/vorlesen`: `{"da": true}`, wenn eine Vertonung eingetragen ist."""
        r = APIRouter(prefix="/api/v1", tags=["vorlesen"], dependencies=[self.g.pflicht])

        @r.get("/vorlesen")
        async def da() -> dict[str, bool]:
            return {"da": self.da}

        @r.post("/vorlesen", response_class=StreamingResponse)
        async def vorlesen(e: Vorlesetext, request: Request) -> StreamingResponse:
            return await self.antwort(self.zeilen(e.text, sitzung=request.headers.get(SITZUNG)))

        return r
