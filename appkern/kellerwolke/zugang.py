"""Zugang einer App zur Kellerwolke: Ablage-Schnittstelle mit App-Schlüssel (Bearer).

Inhalte gehen immer stückweise: Hochladen aus einer Datei oder einem Strom ohne Gesamtpuffer, Lesen als Strom oder
direkt in eine Datei (erst vollständig, dann an ihren Platz). Überschreiben nur mit dem zuletzt gelesenen Stand
(`stand` = ETag des Knotens); so gewinnt von zwei gleichzeitigen Schreibern genau einer, der andere bekommt
`StandVeraltet`. Änderungen unter einem Ordner kommen als Ereignisstrom; `beobachten` verbindet sich nach einem
Abbruch selbst neu und setzt am letzten Stand fort.

Der Schlüssel erscheint nie in Ausgaben (auch nicht in `repr`).
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

from .fehler import KellerwolkeFehler, NichtErreichbar, NichtGefunden, fehler_aus
from .modelle import Aenderungen, Herkunft, Ich, Knoten, Sperre

# Was als Inhalt geschrieben werden kann.
Inhalt = bytes | Path | AsyncIterable[bytes]

_STUECK = 1024 * 1024
_SEITE = 500


def pfad_aus(*teile: str) -> str:
    """Pfad aus Teilen, ohne leere Teile und ohne Ausbruch ("." oder ".."); Schrägstriche in Teilen trennen weiter."""
    sauber: list[str] = []
    for teil in teile:
        for stueck in str(teil).split("/"):
            stueck = stueck.strip()
            if not stueck:
                continue
            if stueck in (".", ".."):
                raise ValueError(f"Unerlaubter Pfadteil: {stueck!r}")
            sauber.append(stueck)
    if not sauber:
        raise ValueError("Leerer Pfad")
    return "/".join(sauber)


async def _aus_datei(pfad: Path, stueck: int) -> AsyncIterator[bytes]:
    with open(pfad, "rb") as datei:
        while True:
            daten = await asyncio.to_thread(datei.read, stueck)
            if not daten:
                return
            yield daten


def _meldung(antwort: httpx.Response) -> str:
    try:
        detail = antwort.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, str):
        return detail
    return antwort.text[:300] or antwort.reason_phrase


class Kellerwolke:
    def __init__(self, adresse: str, schluessel: str, *, client: httpx.AsyncClient | None = None,
                 stueck: int = _STUECK) -> None:
        self.adresse = adresse.rstrip("/")
        self._basis = f"{self.adresse}/api/v1/ablage"
        self._kopf = {"Authorization": f"Bearer {schluessel}"}
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=300.0))
        self._eigener_client = client is None
        self._stueck = stueck

    def __repr__(self) -> str:
        return f"Kellerwolke({self.adresse!r})"

    async def __aenter__(self) -> Kellerwolke:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.schliessen()

    async def schliessen(self) -> None:
        if self._eigener_client:
            await self._client.aclose()

    # --- Anfragen -------------------------------------------------------------------------------------------------

    async def _anfrage(self, methode: str, pfad: str, *, kopf: dict[str, str] | None = None, **weiter: Any) -> httpx.Response:
        try:
            antwort = await self._client.request(methode, self._basis + pfad, headers={**self._kopf, **(kopf or {})},
                                                 **weiter)
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Kellerwolke nicht erreichbar: {f}") from f
        if antwort.status_code >= 400:
            raise fehler_aus(antwort.status_code, _meldung(antwort))
        return antwort

    def _koerper(self, inhalt: Inhalt) -> tuple[Any, dict[str, str]]:
        """Inhalt für einen Upload und die passende Länge (Datei und Bytes mit, Ströme ohne)."""
        if isinstance(inhalt, bytes):
            return inhalt, {}
        if isinstance(inhalt, Path):
            return _aus_datei(inhalt, self._stueck), {"Content-Length": str(inhalt.stat().st_size)}
        return inhalt, {}

    # --- Lesen ----------------------------------------------------------------------------------------------------

    async def ich(self) -> Ich:
        return Ich.model_validate((await self._anfrage("GET", "/ich")).json())

    async def knoten(self, knoten_id: UUID | str) -> Knoten:
        return Knoten.model_validate((await self._anfrage("GET", f"/knoten/{knoten_id}")).json())

    async def pfad(self, pfad: str) -> Knoten:
        """Knoten unter einem Pfad; `NichtGefunden`, wenn es ihn nicht gibt oder er für die App unsichtbar ist."""
        return Knoten.model_validate((await self._anfrage("GET", "/pfad", params={"pfad": pfad})).json())

    async def finden(self, pfad: str) -> Knoten | None:
        try:
            return await self.pfad(pfad)
        except NichtGefunden:
            return None

    async def kinder(self, ordner_id: UUID | str, ab: int = 0, anzahl: int = 200) -> list[Knoten]:
        antwort = await self._anfrage("GET", f"/knoten/{ordner_id}/kinder", params={"ab": ab, "anzahl": anzahl})
        return [Knoten.model_validate(k) for k in antwort.json()]

    async def alle_kinder(self, ordner_id: UUID | str) -> AsyncIterator[Knoten]:
        """Alle Kinder Seite für Seite (Ordner vor Dateien, nach Namen)."""
        ab = 0
        while True:
            seite = await self.kinder(ordner_id, ab, _SEITE)
            for k in seite:
                yield k
            if len(seite) < _SEITE:
                return
            ab += _SEITE

    async def lesen(self, knoten_id: UUID | str, *, start: int | None = None,
                    ende: int | None = None) -> AsyncIterator[bytes]:
        """Inhalt stückweise; mit start (und ende, einschließlich) nur ein Bereich."""
        kopf = dict(self._kopf)
        if start is not None:
            kopf["Range"] = f"bytes={start}-{'' if ende is None else ende}"
        try:
            async with self._client.stream("GET", f"{self._basis}/knoten/{knoten_id}/inhalt", headers=kopf) as antwort:
                if antwort.status_code >= 400:
                    await antwort.aread()
                    raise fehler_aus(antwort.status_code, _meldung(antwort))
                async for daten in antwort.aiter_bytes(self._stueck):
                    yield daten
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Kellerwolke nicht erreichbar: {f}") from f

    async def lesen_ganz(self, knoten_id: UUID | str) -> bytes:
        """Nur für kleine Inhalte (Texte, Einstellungen); Großes mit `lesen` oder `herunterladen`."""
        return b"".join([d async for d in self.lesen(knoten_id)])

    async def herunterladen(self, knoten_id: UUID | str, ziel: Path) -> Path:
        """In eine Datei: erst vollständig unter vorläufigem Namen, dann an ihren Platz - nie halb."""
        ziel.parent.mkdir(parents=True, exist_ok=True)
        vorlaeufig = ziel.with_name(f".{ziel.name}.teil")
        try:
            with open(vorlaeufig, "wb") as datei:
                async for daten in self.lesen(knoten_id):
                    await asyncio.to_thread(datei.write, daten)
            os.replace(vorlaeufig, ziel)
        finally:
            vorlaeufig.unlink(missing_ok=True)
        return ziel

    # --- Schreiben ------------------------------------------------------------------------------------------------

    async def ordner(self, pfad: str) -> Knoten:
        """Ordnerpfad anlegen (fehlende Teile mit), vorhandene Ordner bleiben."""
        return Knoten.model_validate((await self._anfrage("POST", "/ordner", json={"pfad": pfad})).json())

    async def schreiben(self, pfad: str, inhalt: Inhalt, *, stand: str | None = None, nur_neu: bool = False,
                        inhaltstyp: str | None = None) -> Knoten:
        """Datei anlegen oder überschreiben. Vorhandene nur mit `stand` (ETag zuletzt gelesen), sonst `StandFehlt`;
        `nur_neu` legt nur an und wirft `StandVeraltet`, wenn es die Datei schon gibt."""
        koerper, kopf = self._koerper(inhalt)
        if stand is not None:
            kopf["If-Match"] = f'"{stand}"'
        if nur_neu:
            kopf["If-None-Match"] = "*"
        if inhaltstyp:
            kopf["Content-Type"] = inhaltstyp
        antwort = await self._anfrage("PUT", "/datei", params={"pfad": pfad}, content=koerper, kopf=kopf)
        return Knoten.model_validate(antwort.json())

    async def neue_version(self, knoten_id: UUID | str, inhalt: Inhalt, *, stand: str,
                           inhaltstyp: str | None = None) -> Knoten:
        """Neue Version einer Datei per Kennung (bleibt beim Umbenennen und Verschieben gleich)."""
        koerper, kopf = self._koerper(inhalt)
        kopf["If-Match"] = f'"{stand}"'
        if inhaltstyp:
            kopf["Content-Type"] = inhaltstyp
        antwort = await self._anfrage("PUT", f"/knoten/{knoten_id}/inhalt", content=koerper, kopf=kopf)
        return Knoten.model_validate(antwort.json())

    async def loeschen(self, knoten_id: UUID | str) -> None:
        """In den Papierkorb des Kontos (wiederherstellbar). Freigegebene Ordner selbst und von anderen Apps gesperrte
        Dateien bleiben (`KeinRecht`, `Gesperrt`)."""
        await self._anfrage("DELETE", f"/knoten/{knoten_id}")

    async def felder_setzen(self, knoten_id: UUID | str, aenderung: dict[str, Any]) -> Knoten:
        """Freie Felder einmischen; ein Feld mit None wird entfernt."""
        antwort = await self._anfrage("PATCH", f"/knoten/{knoten_id}/felder", json={"felder": aenderung})
        return Knoten.model_validate(antwort.json())

    async def suchen(self, felder: dict[str, Any], anzahl: int = 100) -> list[Knoten]:
        """Dateien des Kontos, deren Felder diese Werte enthalten, neueste zuerst."""
        antwort = await self._anfrage("POST", "/suche", json={"felder": felder, "anzahl": anzahl})
        return [Knoten.model_validate(k) for k in antwort.json()]

    # --- Herkunft ---------------------------------------------------------------------------------------------------

    async def herkunft(self, knoten_id: UUID | str) -> list[Herkunft]:
        antwort = await self._anfrage("GET", f"/knoten/{knoten_id}/herkunft")
        return [Herkunft.model_validate(h) for h in antwort.json()]

    async def herkunft_setzen(self, zu_id: UUID | str, von_id: UUID | str, art: str) -> list[Herkunft]:
        """`zu` entstand aus `von`, etwa art="transkript_zu" oder "abgeleitet_von"."""
        antwort = await self._anfrage("POST", f"/knoten/{zu_id}/herkunft", json={"von_id": str(von_id), "art": art})
        return [Herkunft.model_validate(h) for h in antwort.json()]

    async def herkunft_entfernen(self, zu_id: UUID | str, von_id: UUID | str, art: str) -> None:
        await self._anfrage("DELETE", f"/knoten/{zu_id}/herkunft", params={"von_id": str(von_id), "art": art})

    # --- Bearbeitungssperre -----------------------------------------------------------------------------------------

    async def sperren(self, knoten_id: UUID | str, dauer_s: int, grund: str = "") -> Sperre:
        """Andere Apps schreiben bis zum Ablauf nicht; erneuern, solange die Arbeit läuft."""
        antwort = await self._anfrage("POST", f"/knoten/{knoten_id}/sperre", json={"dauer_s": dauer_s, "grund": grund})
        return Sperre.model_validate(antwort.json())

    async def entsperren(self, knoten_id: UUID | str) -> None:
        await self._anfrage("DELETE", f"/knoten/{knoten_id}/sperre")

    # --- Änderungen -------------------------------------------------------------------------------------------------

    async def aenderungen(self, ordner_id: UUID | str, seit: int = 0, anzahl: int = 500) -> Aenderungen:
        antwort = await self._anfrage("GET", "/aenderungen", params={"ordner": str(ordner_id), "seit": seit,
                                                                       "anzahl": anzahl})
        return Aenderungen.model_validate(antwort.json())

    async def ereignisse(self, ordner_id: UUID | str, seit: int = 0) -> AsyncIterator[Aenderungen]:
        """Eine Verbindung zum Ereignisstrom: je neuem Stand unter dem Ordner ein `Aenderungen`. Endet, wenn die
        Verbindung endet; `beobachten` verbindet sich selbst neu."""
        url = f"{self._basis}/ereignisse"
        try:
            async with self._client.stream("GET", url, params={"ordner": str(ordner_id), "seit": seit},
                                           headers=self._kopf, timeout=httpx.Timeout(30.0, read=60.0)) as antwort:
                if antwort.status_code >= 400:
                    await antwort.aread()
                    raise fehler_aus(antwort.status_code, _meldung(antwort))
                art, daten = "", []
                async for zeile in antwort.aiter_lines():
                    if zeile.startswith(":"):
                        continue  # Lebenszeichen
                    if zeile:
                        feld, _, wert = zeile.partition(":")
                        wert = wert.removeprefix(" ")
                        if feld == "event":
                            art = wert
                        elif feld == "data":
                            daten.append(wert)
                        continue
                    if art == "aenderungen" and daten:
                        yield Aenderungen.model_validate(json.loads("\n".join(daten)))
                    elif art == "ende":
                        raise KellerwolkeFehler("\n".join(daten) or "Ereignisstrom beendet")
                    art, daten = "", []
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Kellerwolke nicht erreichbar: {f}") from f

    async def beobachten(self, ordner_id: UUID | str, seit: int = 0, *, pause_max: float = 30.0) -> AsyncIterator[Aenderungen]:
        """Wie `ereignisse`, aber dauerhaft: nach einem Abbruch neu verbinden (Wartezeit verdoppelt sich bis
        `pause_max`) und am letzten Stand fortsetzen. Ein entzogenes Recht oder ein verschwundener Ordner beendet."""
        pause = 1.0
        while True:
            try:
                async for stand in self.ereignisse(ordner_id, seit):
                    seit = stand.bis
                    pause = 1.0
                    yield stand
            except NichtErreichbar:
                await asyncio.sleep(pause)
                pause = min(pause * 2, pause_max)
