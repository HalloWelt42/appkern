"""Vorlesen: der Anschluss jeder App an die App Vorlesen, die eine Stelle für Sprachausgabe im Verbund. Die App
Vorlesen nimmt Text, teilt ihn an Satzgrenzen und liefert den Ton Satz für Satz als Strom; das Sprechmodell bleibt
isoliert im Klangwerk hinter der Leitstelle, Stimme und Tempo wählt man in der App Vorlesen. Eine App, die vorlesen
will, ruft nur sie: mit ihrem App-Schlüssel der Kellerwolke und im Auftrag der Person (über `geruest.verbund`).

    class AppEinstellungen(Grundeinstellungen, VorlesenEinstellungen): ...   # Adresse und Vorlesestimme (Verbindungen)

    vorlesen = Vorlesen(geruest)            # Angebote für beide Felder, Verbindung in der Fußleiste
    app.include_router(vorlesen.router())   # POST /api/v1/vorlesen für den Vorleser der Oberfläche, GET: ist es da?

    # mit eigener Prüfung vorher (etwa Rechte an einer Karte):
    return await vorlesen.antwort(vorlesen.zeilen(text, sitzung=sitzung))

Das Format des Stroms (NDJSON, je Zeile `art` satz, ende oder fehler; `satz` mit `nr`, `text`, `von_zeichen`,
`bis_zeichen`, `dauer_ms` und dem Ton als Base64-WAV in `ton`) liest der Vorleser der Oberfläche (`vorleser`, mit
Vorlauf). Die Zeilen gehen unverändert durch; was vor der ersten Zeile scheitert, ist ein `VorlesenFehler` mit Grund
und Status, danach kommt eine Zeile `fehler`.

Die Vorlesestimme wählt jede App für sich (Feld `vorlesen_stimme`) aus dem, was die App Vorlesen gerade anbietet: ihr
Katalog und die eigenen Stimmen, die sie freigibt. Die Auswahl kommt jedes Mal aus Vorlesen, nie aus einer festen
Liste; gesendet wird die Wahl bei jedem Aufruf, ohne Wahl gilt die Vorgabe von Vorlesen."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from appkern.app.einstellungen import VERBINDUNGEN
from appkern.einstellungen import Angebot, Option
from appkern.verbund import ABFRAGE, SITZUNG, VerbundFehler

if TYPE_CHECKING:
    from appkern.app import Geruest

#: der Weg der App Vorlesen, der den Strom liefert
STROM = "/api/v1/vorlesen/strom"
#: so viel Text nimmt die App Vorlesen am Stück (Zeichen); was länger ist, lehnt schon diese App ab
TEXT_HOECHSTENS = 100_000
NDJSON = "application/x-ndjson"


class VorlesenEinstellungen(BaseModel):
    """Das Feld der Adresse; eine App erbt es zusätzlich zu `Grundeinstellungen`."""
    vorlesen_adresse: str = Field("", title="Vorlesen", json_schema_extra=VERBINDUNGEN,
                                  description="Adresse der App Vorlesen, der einen Stelle für Sprachausgabe. Stimme und "
                                              "Tempo wählt man dort. Leer: ohne Vorlesen.")
    vorlesen_stimme: str = Field("", title="Vorlesestimme", json_schema_extra=VERBINDUNGEN,
                                 description="Mit dieser Stimme liest die App Vorlesen für diese App: aus ihrem Katalog "
                                             "oder eine eigene Stimme, die sie freigibt. Leer: die Vorgabe von Vorlesen.")


class Vorlesetext(BaseModel):
    text: str = Field(min_length=1, max_length=TEXT_HOECHSTENS)


class VorlesenFehler(Exception):
    """Vorlesen ging nicht, bevor etwas gesprochen war; `meldung` in Worten, `status` für die Antwort der App."""

    def __init__(self, meldung: str, status: int) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        self.status = status


def fehler_aus(f: VerbundFehler) -> VorlesenFehler:
    """Ein Fehler des Verbunds als Grund für die Person. Eine 401 der App Vorlesen geht nie als 401 weiter (sonst
    meldete die Oberfläche die Person ab, Lehre 39 des Appkerns)."""
    if f.status is None:
        if f.meldung == "nicht eingerichtet":
            return VorlesenFehler("Vorlesen ist nicht eingerichtet (Einstellungen, Verbindungen)", 503)
        return VorlesenFehler(f"Die App Vorlesen ist gerade nicht erreichbar ({f.meldung})", 503)
    if f.status in (401, 403):
        return VorlesenFehler(f"Die App Vorlesen lässt das nicht zu: {f.meldung}", 403)
    if f.status in (400, 413, 422):
        return VorlesenFehler(f"Die App Vorlesen lehnt den Text ab: {f.meldung}", 400)
    return VorlesenFehler(f"Die App Vorlesen meldet: {f.meldung}", 502)


def fehlerzeile(meldung: str) -> bytes:
    return json.dumps({"art": "fehler", "meldung": meldung}, ensure_ascii=False).encode() + b"\n"


class Vorlesen:
    def __init__(self, geruest: Geruest, *, name: str = "Vorlesen") -> None:
        """Bietet für das Feld `vorlesen_adresse` die Apps des Verzeichnisses an und stellt die App Vorlesen zu den
        Verbindungen. Die Einstellungen der App müssen `VorlesenEinstellungen` erben."""
        if "vorlesen_adresse" not in geruest.einstellungen.modell.model_fields:
            raise TypeError("Die Einstellungen der App erben VorlesenEinstellungen nicht (Feld vorlesen_adresse fehlt)")
        self.g = geruest
        geruest.einstellungen.anbieten("vorlesen_adresse", geruest.verbund.angebot(name, "vorlesen", self.adresse))
        geruest.einstellungen.anbieten("vorlesen_stimme", self.stimmen_angebot)
        geruest.verbund.anmelden(name, self.adresse)

    def adresse(self) -> str:
        return str(self.g.einstellungen.stand.vorlesen_adresse).strip().rstrip("/")

    def stimme(self) -> str:
        return str(self.g.einstellungen.stand.vorlesen_stimme).strip()

    async def stimmen_angebot(self) -> Angebot:
        """Auswahl für die Vorlesestimme, jedes Mal aus der App Vorlesen (`GET /api/v1/stimmen`): ihr Katalog und die
        eigenen Stimmen, die sie freigibt; dazu leer für ihre Vorgabe."""
        optionen = [Option(wert="", titel="Vorgabe von Vorlesen", hinweis="wie in der App Vorlesen eingestellt")]
        if not self.da:
            return Angebot(optionen=optionen, eigener_wert=False, stand="erst die Adresse der App Vorlesen eintragen")
        try:
            daten = (await self.g.verbund.anfrage("GET", self.adresse(), "/api/v1/stimmen", timeout=ABFRAGE)).json()
        except VerbundFehler as f:
            return Angebot(optionen=optionen, eigener_wert=False, stand=f"Vorlesen antwortet nicht: {f.meldung}")
        stimmen = daten.get("stimmen") or []
        optionen += [Option(wert=str(s["name"]), titel=str(s.get("titel") or s["name"]),
                            hinweis="eigene Stimme" if s.get("art") == "eigen" else "Katalog") for s in stimmen]
        return Angebot(optionen=optionen, eigener_wert=False, stand=str(daten.get("stand") or f"{len(stimmen)} Stimmen"))

    @property
    def da(self) -> bool:
        """Ist eine App Vorlesen eingetragen? (Ob sie gerade antwortet, sagen die Verbindungen.)"""
        return bool(self.adresse())

    async def zeilen(self, text: str, *, sitzung: str | None = None) -> AsyncIterator[bytes]:
        """Die Zeilen der App Vorlesen für `text`, je Zeile mit Zeilenende, sobald sie kommen. Lehnt sie ab oder ist sie
        nicht erreichbar, bevor eine Zeile kam: `VorlesenFehler`. Reißt die Verbindung danach ab: eine Zeile `fehler`.
        Bricht der Leser ab, endet die Anfrage und die App Vorlesen spricht nicht weiter."""
        if not self.da:
            raise VorlesenFehler("Vorlesen ist nicht eingerichtet (Einstellungen, Verbindungen)", 503)
        if len(text) > TEXT_HOECHSTENS:
            raise VorlesenFehler(f"Der Text ist länger als {TEXT_HOECHSTENS} Zeichen", 400)
        gekommen = False
        try:
            koerper = {"text": text, **({"stimme": self.stimme()} if self.stimme() else {})}
            async with self.g.verbund.strom("POST", self.adresse(), STROM, sitzung=sitzung, json=koerper) as antwort:
                async for zeile in antwort.aiter_lines():
                    if zeile.strip():
                        gekommen = True
                        yield zeile.encode() + b"\n"
        except VerbundFehler as f:
            if not gekommen:
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
        angemeldeten Person; `GET /api/v1/vorlesen`: `{"da": true}`, wenn eine App Vorlesen eingetragen ist."""
        r = APIRouter(prefix="/api/v1", tags=["vorlesen"], dependencies=[self.g.pflicht])

        @r.get("/vorlesen")
        async def da() -> dict[str, bool]:
            return {"da": self.da}

        @r.post("/vorlesen", response_class=StreamingResponse)
        async def vorlesen(e: Vorlesetext, request: Request) -> StreamingResponse:
            return await self.antwort(self.zeilen(e.text, sitzung=request.headers.get(SITZUNG)))

        return r
