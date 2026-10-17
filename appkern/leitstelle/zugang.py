"""Zugang einer App zur Leitstelle über ihre Fassade (ANBINDUNG.md Stufe 1).

Sprachmodelle im OpenAI-Format (`/v1/chat/completions` mit und ohne Strom, `/v1/embeddings`, `/v1/models`) und
Dienste mit eigener Schnittstelle (Sprechen, Hören, Bild) unter `/v1/dienste/<name>/...`. Jeder Auftrag trägt einen
Titel ("Transkription: Folge 12") und auf Wunsch eine Priorität; die Leitstelle wählt Dienst, Modell und Rechner.

Regeln aus der Anbindung, hier an einer Stelle umgesetzt:
- keine Lese-Zeitgrenze für Arbeit (nur 10 s für den Verbindungsaufbau); ein wartender Auftrag meldet sich im Strom
  mit `Wartet`, abbrechen ist Sache des Menschen oder der Leitstelle;
- keine Wiederholung von selbst; Fehler kommen als eigene Arten (siehe fehler.py) mit dem Wortlaut der Leitstelle;
- ein in der Leitstelle abgebrochener Auftrag liefert seinen bisherigen Text (`abgebrochen=True`), nie nichts;
- Gesundheitsprüfung nur über `modelle()`, das lädt nie ein Modell.

Der Schlüssel erscheint nie in Ausgaben (auch nicht in `repr`).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .fehler import LeitstellenFehler, NichtErreichbar, fehler_aus
from .modelle import ChatAntwort, Einbettungen, Ende, Ereignis, Modell, Nachricht, Prioritaet, Stueck, Verbrauch, Wartet

# Arbeit hat keine Lese-Zeitgrenze; eine Abfrage (Modellliste) schon.
ARBEIT = httpx.Timeout(10.0, read=None, write=None, pool=None)
ABFRAGE = httpx.Timeout(10.0)
ABBRUCH = "leitstelle_abbruch"
_WARTET = re.compile(r"^:\s*wartet,\s*(?P<grund>.*?)(?:,\s*etwa\s+(?P<s>\d+)\s*s)?\s*$")


def _verbrauch(roh: dict[str, Any] | None) -> Verbrauch | None:
    if not roh:
        return None
    return Verbrauch(eingabe=roh.get("prompt_tokens", 0), ausgabe=roh.get("completion_tokens", 0),
                     gesamt=roh.get("total_tokens", 0))


def _nachrichten(nachrichten: Sequence[Nachricht | str]) -> list[dict[str, Any]]:
    """Ein bloßer Text ist eine Nachricht des Nutzers."""
    return [(n if isinstance(n, Nachricht) else Nachricht.nutzer(n)).fuer_fassade() for n in nachrichten]


def _fehler(antwort: httpx.Response, text: str | None = None) -> LeitstellenFehler:
    roh = text if text is not None else antwort.text
    grund, meldung = "", roh[:300] or antwort.reason_phrase
    try:
        daten = json.loads(roh)
        if isinstance(daten.get("error"), dict):
            grund = daten["error"].get("code") or ""
            meldung = daten["error"].get("message") or meldung
        elif isinstance(daten.get("detail"), str):
            meldung = daten["detail"]
    except (ValueError, AttributeError):
        pass
    nochmal = antwort.headers.get("retry-after", "")
    return fehler_aus(antwort.status_code, grund, meldung, int(nochmal) if nochmal.isdigit() else None)


class Leitstelle:
    def __init__(self, adresse: str, schluessel: str, app: str, *, client: httpx.AsyncClient | None = None) -> None:
        """`adresse` mit oder ohne `/v1`; `app` steht vor jedem Titel, damit Aufträge in der Leitstelle erkennbar sind."""
        adresse = adresse.rstrip("/")
        self.adresse = adresse[:-3] if adresse.endswith("/v1") else adresse
        self.app = app
        self._schluessel_kopf = {"Authorization": f"Bearer {schluessel}"}
        self._client = client or httpx.AsyncClient(timeout=ARBEIT)
        self._eigener_client = client is None

    def __repr__(self) -> str:
        return f"Leitstelle({self.adresse!r}, app={self.app!r})"

    async def schliessen(self) -> None:
        if self._eigener_client:
            await self._client.aclose()

    async def __aenter__(self) -> Leitstelle:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.schliessen()

    def koepfe(self, titel: str = "", prioritaet: Prioritaet | None = None) -> dict[str, str]:
        """Schlüssel, Titel (prozentkodiert, Köpfe tragen nur ASCII) und Priorität eines Auftrags."""
        kopf = dict(self._schluessel_kopf)
        kopf["X-Leitstelle-Titel"] = quote(f"{self.app}: {titel}" if titel else self.app, safe="")
        if prioritaet:
            kopf["X-Leitstelle-Prioritaet"] = prioritaet
        return kopf

    async def _senden(self, methode: str, pfad: str, *, kopf: dict[str, str], timeout: httpx.Timeout = ARBEIT,
                      **art: Any) -> httpx.Response:
        try:
            antwort = await self._client.request(methode, f"{self.adresse}{pfad}", headers=kopf, timeout=timeout, **art)
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Leitstelle nicht erreichbar: {type(f).__name__}") from f
        if antwort.status_code >= 400:
            raise _fehler(antwort)
        return antwort

    # --- Sprachmodelle ---------------------------------------------------------------------------------------------

    async def modelle(self) -> list[Modell]:
        """Was die App nutzen darf, mit Ladezustand. Lädt nichts; dient auch als Gesundheitsprüfung."""
        antwort = await self._senden("GET", "/v1/models", kopf=dict(self._schluessel_kopf), timeout=ABFRAGE)
        return [Modell(id=m["id"], **(m.get("x-leitstelle") or {})) for m in antwort.json().get("data", [])]

    def _chat_koerper(self, nachrichten, modell, optionen, strom: bool) -> dict[str, Any]:
        koerper: dict[str, Any] = {"messages": _nachrichten(nachrichten), **optionen}
        if modell:
            koerper["model"] = modell
        if strom:
            koerper["stream"] = True
            koerper.setdefault("stream_options", {"include_usage": True})
        return koerper

    async def chat(self, nachrichten: Sequence[Nachricht | str], *, modell: str | None = None, titel: str = "",
                   prioritaet: Prioritaet | None = None, **optionen: Any) -> ChatAntwort:
        """Eine Antwort am Stück. Ohne `modell` gilt die Kette der App; `optionen` gehen unverändert mit
        (temperature, max_tokens, response_format ...)."""
        antwort = await self._senden("POST", "/v1/chat/completions", kopf=self.koepfe(titel, prioritaet),
                                     json=self._chat_koerper(nachrichten, modell, optionen, False))
        daten = antwort.json()
        wahl = (daten.get("choices") or [{}])[0]
        ende = wahl.get("finish_reason")
        return ChatAntwort(text=(wahl.get("message") or {}).get("content") or "", ende=ende, abgebrochen=ende == ABBRUCH,
                           modell=antwort.headers.get("x-leitstelle-modell") or daten.get("model"),
                           knoten=antwort.headers.get("x-leitstelle-knoten"),
                           auftrag=antwort.headers.get("x-leitstelle-auftrag"), verbrauch=_verbrauch(daten.get("usage")))

    async def chat_strom(self, nachrichten: Sequence[Nachricht | str], *, modell: str | None = None, titel: str = "",
                         prioritaet: Prioritaet | None = None, **optionen: Any) -> AsyncIterator[Ereignis]:
        """Stücke, solange gerechnet wird, `Wartet`, solange der Auftrag wartet, zuletzt `Ende`. Ein Fehler mitten
        im Strom kommt als Fehlerart; der Text bis dahin ist beim Aufrufer."""
        koerper = self._chat_koerper(nachrichten, modell, optionen, True)
        try:
            async with self._client.stream("POST", f"{self.adresse}/v1/chat/completions", json=koerper,
                                           headers=self.koepfe(titel, prioritaet), timeout=ARBEIT) as antwort:
                if antwort.status_code >= 400:
                    raise _fehler(antwort, (await antwort.aread()).decode("utf-8", "replace"))
                auftrag = antwort.headers.get("x-leitstelle-auftrag")
                ende, modell_name, verbrauch = None, None, None
                async for zeile in antwort.aiter_lines():
                    if zeile.startswith(":"):
                        treffer = _WARTET.match(zeile)
                        if treffer:
                            s = treffer.group("s")
                            yield Wartet(grund=treffer.group("grund"), sekunden=int(s) if s else None)
                        continue
                    if not zeile.startswith("data:"):
                        continue
                    daten = zeile[5:].strip()
                    if daten == "[DONE]":
                        break
                    teil = json.loads(daten)
                    if isinstance(teil.get("error"), dict):
                        f = teil["error"]
                        raise fehler_aus(502, f.get("code") or "", f.get("message") or "Fehler im Strom")
                    modell_name = teil.get("model") or modell_name
                    verbrauch = _verbrauch(teil.get("usage")) or verbrauch
                    for wahl in teil.get("choices") or []:
                        text = (wahl.get("delta") or {}).get("content")
                        if text:
                            yield Stueck(text=text)
                        ende = wahl.get("finish_reason") or ende
                yield Ende(ende=ende, abgebrochen=ende == ABBRUCH, modell=modell_name, auftrag=auftrag,
                           verbrauch=verbrauch)
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Leitstelle nicht erreichbar: {type(f).__name__}") from f

    async def einbetten(self, texte: Sequence[str], *, modell: str | None = None, titel: str = "",
                        prioritaet: Prioritaet | None = None) -> Einbettungen:
        koerper: dict[str, Any] = {"input": list(texte)}
        if modell:
            koerper["model"] = modell
        antwort = await self._senden("POST", "/v1/embeddings", kopf=self.koepfe(titel, prioritaet), json=koerper)
        daten = antwort.json()
        reihe = sorted(daten.get("data") or [], key=lambda d: d.get("index", 0))
        return Einbettungen(vektoren=[d["embedding"] for d in reihe], modell=daten.get("model"),
                            verbrauch=_verbrauch(daten.get("usage")))

    # --- Dienste mit eigener Schnittstelle -----------------------------------------------------------------------

    def dienst(self, name: str) -> Dienst:
        """Ein Dienst wie `klangwerk-hoeren`; jeder Aufruf ist ein Auftrag der Leitstelle."""
        return Dienst(self, name)


class Dienst:
    """Ein Dienst hinter der Leitstelle: `/v1/dienste/<name>/<pfad>`. Anfrage und Antwort gehen unverändert durch;
    die Leitstelle startet den Dienst bei Bedarf und plant seinen Speicher ein."""

    def __init__(self, leitstelle: Leitstelle, name: str) -> None:
        self._ls = leitstelle
        self.name = name

    def __repr__(self) -> str:
        return f"Dienst({self.name!r})"

    def _pfad(self, pfad: str) -> str:
        return f"/v1/dienste/{quote(self.name, safe='')}/{pfad.lstrip('/')}"

    async def anfrage(self, methode: str, pfad: str, *, titel: str = "", prioritaet: Prioritaet | None = None,
                      **art: Any) -> httpx.Response:
        """Rohe Anfrage (json, data, files, params wie bei httpx); die Antwort ist vollständig gelesen."""
        return await self._ls._senden(methode, self._pfad(pfad), kopf=self._ls.koepfe(titel, prioritaet), **art)

    async def json(self, methode: str, pfad: str, *, titel: str = "", prioritaet: Prioritaet | None = None,
                   **art: Any) -> Any:
        return (await self.anfrage(methode, pfad, titel=titel, prioritaet=prioritaet, **art)).json()

    async def strom(self, pfad: str, *, titel: str = "", prioritaet: Prioritaet | None = None,
                    **art: Any) -> AsyncIterator[bytes]:
        """Eine große Antwort (etwa eine Tondatei) stückweise lesen."""
        try:
            async with self._ls._client.stream("GET", f"{self._ls.adresse}{self._pfad(pfad)}", timeout=ARBEIT,
                                               headers=self._ls.koepfe(titel, prioritaet), **art) as antwort:
                if antwort.status_code >= 400:
                    raise _fehler(antwort, (await antwort.aread()).decode("utf-8", "replace"))
                async for daten in antwort.aiter_bytes():
                    yield daten
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Leitstelle nicht erreichbar: {type(f).__name__}") from f

    async def herunterladen(self, pfad: str, ziel: Path, *, titel: str = "", prioritaet: Prioritaet | None = None,
                            **art: Any) -> Path:
        """In eine Datei, nie halb: erst vollständig unter einem Zwischennamen, dann an ihren Platz."""
        ziel = Path(ziel)
        teil = ziel.with_name(f".{ziel.name}.teil")
        try:
            with open(teil, "wb") as datei:
                async for daten in self.strom(pfad, titel=titel, prioritaet=prioritaet, **art):
                    await asyncio.to_thread(datei.write, daten)
            os.replace(teil, ziel)
        finally:
            teil.unlink(missing_ok=True)
        return ziel
