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
import base64
import contextlib
import json
import os
import re
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from .fehler import LeitstellenFehler, NichtErreichbar, fehler_aus
from .modelle import (
    Bild, Bilder, Bildereignis, ChatAntwort, DienstEintrag, Einbettungen, Ende, Ereignis, Modell, Nachricht, Prioritaet, Rechnet,
    Stueck, Verbrauch, Wartet, Werkzeugaufruf,
)
from .arbeit import KOPF as ARBEIT_KOPF, LAUFENDE_ARBEIT
from .bindung import GEBUNDEN, KOPF as INSTANZ_KOPF, Bindung

# Arbeit hat keine Lese-Zeitgrenze; eine Abfrage (Modellliste) schon.
ARBEIT = httpx.Timeout(10.0, read=None, write=None, pool=None)
ABFRAGE = httpx.Timeout(10.0)
ABBRUCH = "leitstelle_abbruch"
_WARTET = re.compile(r"^:\s*wartet,\s*(?P<grund>.*?)(?:,\s*etwa\s+(?P<s>\d+)\s*s)?\s*$")
_RECHNET = re.compile(r"^:\s*rechnet seit\s+(?P<s>\d+)\s*s\s*$")


def _verbrauch(roh: dict[str, Any] | None) -> Verbrauch | None:
    if not roh:
        return None
    return Verbrauch(eingabe=roh.get("prompt_tokens", 0), ausgabe=roh.get("completion_tokens", 0),
                     gesamt=roh.get("total_tokens", 0))


def _aufrufe(roh: list[dict[str, Any]] | None) -> list[Werkzeugaufruf]:
    """`tool_calls` einer fertigen Antwort."""
    return [Werkzeugaufruf(id=a.get("id") or f"aufruf-{n}", name=(a.get("function") or {}).get("name") or "",
                           argumente=(a.get("function") or {}).get("arguments") or "")
            for n, a in enumerate(roh or [])]


class _Aufrufsammler:
    """Setzt die Werkzeugaufrufe eines Stroms zusammen: je `index` kommen Kennung, Name und Argumente in Stücken."""

    def __init__(self) -> None:
        self._teile: dict[int, dict[str, str]] = {}

    def aufnehmen(self, delta: list[dict[str, Any]] | None) -> None:
        for n, d in enumerate(delta or []):
            teil = self._teile.setdefault(int(d.get("index", n)), {"id": "", "name": "", "argumente": ""})
            funktion = d.get("function") or {}
            teil["id"] = d.get("id") or teil["id"]
            teil["name"] += funktion.get("name") or ""
            teil["argumente"] += funktion.get("arguments") or ""

    def aufrufe(self) -> list[Werkzeugaufruf]:
        return [Werkzeugaufruf(id=t["id"] or f"aufruf-{i}", name=t["name"], argumente=t["argumente"])
                for i, t in sorted(self._teile.items())]


def _nachrichten(nachrichten: Sequence[Nachricht | str]) -> list[dict[str, Any]]:
    """Ein bloßer Text ist eine Nachricht des Nutzers."""
    return [(n if isinstance(n, Nachricht) else Nachricht.nutzer(n)).fuer_fassade() for n in nachrichten]


def _rechner(fehler: dict[str, Any]) -> list[str]:
    """Die Rechner, die die Leitstelle zum Fehler nennt (`error.x-leitstelle.rechner`, etwa schlafende)."""
    zusatz = fehler.get("x-leitstelle")
    rechner = zusatz.get("rechner") if isinstance(zusatz, dict) else None
    return [str(r) for r in rechner] if isinstance(rechner, list) else []


def _fehler(antwort: httpx.Response, text: str | None = None) -> LeitstellenFehler:
    roh = text if text is not None else antwort.text
    grund, meldung, rechner = "", roh[:300] or antwort.reason_phrase, []
    try:
        daten = json.loads(roh)
        if isinstance(daten.get("error"), dict):
            grund = daten["error"].get("code") or ""
            meldung = daten["error"].get("message") or meldung
            rechner = _rechner(daten["error"])
        elif isinstance(daten.get("detail"), str):
            meldung = daten["detail"]
    except (ValueError, AttributeError):
        pass
    nochmal = antwort.headers.get("retry-after", "")
    return fehler_aus(antwort.status_code, grund, meldung, int(nochmal) if nochmal.isdigit() else None, rechner)


class Leitstelle:
    def __init__(self, adresse: str, schluessel: str, app: str, *, client: httpx.AsyncClient | None = None,
                 extern: Sequence[str] = ()) -> None:
        """`adresse` mit oder ohne `/v1`; `app` steht vor jedem Titel, damit Aufträge in der Leitstelle erkennbar sind.
        `extern`: Erlaubnisliste externer Modelle aus den Einstellungen der App; nur dorthin darf die Leitstelle
        ausweichen (Kopf X-Leitstelle-Extern). Leer: nie nach extern, außer ein Aufruf verlangt ein Modell ausdrücklich."""
        adresse = adresse.rstrip("/")
        self.adresse = adresse[:-3] if adresse.endswith("/v1") else adresse
        self.app = app
        self.extern = tuple(extern)
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
        if (arbeit := LAUFENDE_ARBEIT.get()) is not None:
            kopf[ARBEIT_KOPF] = arbeit
        if self.extern:
            kopf["X-Leitstelle-Extern"] = quote(",".join(self.extern), safe=",")
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

    async def steckbriefe(self, *, faehigkeit: str | None = None, eignung: str | None = None, sprache: str | None = None) -> list[Modell]:
        """Wofür welches Modell gemacht ist (PROTOKOLL 4.8), nur was die App nutzen darf; mit `sprache` zuerst die Modelle,
        die sie ausdrücklich können."""
        abfrage = {k: v for k, v in (("faehigkeit", faehigkeit), ("eignung", eignung), ("sprache", sprache)) if v}
        antwort = await self._senden("GET", "/v1/steckbriefe", kopf=dict(self._schluessel_kopf), timeout=ABFRAGE, params=abfrage)
        return [Modell(id=m["id"], name=m.get("name", ""), geladen=m.get("geladen", False), steckbrief=m.get("steckbrief"))
                for m in antwort.json().get("data", [])]

    async def dienste(self) -> list[DienstEintrag]:
        """Die Dienste im Maschinenraum, die die App nutzen darf (PROTOKOLL 6.2): Zustand (aus, startet, bereit ...),
        Zweck, Rechner und bei Bilddiensten ihr Bild-Steckbrief (Größen, Schritte, Anzahl). Startet nichts."""
        antwort = await self._senden("GET", "/v1/dienste", kopf=dict(self._schluessel_kopf), timeout=ABFRAGE)
        return [DienstEintrag.model_validate(d) for d in antwort.json().get("data", [])]

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
        nachricht = wahl.get("message") or {}
        text = nachricht.get("content") or ""
        denken = nachricht.get("reasoning_content") or nachricht.get("reasoning") or ""
        if "response_format" in optionen and not text.strip() and denken.strip():
            # Denkende Modelle (etwa Qwen 3.6 und 3.8 in LM Studio) legen die durch das Schema eingeschränkte Ausgabe
            # ins Denkfeld und lassen das Antwortfeld leer; mit fester Antwortform ist das die Antwort.
            text = denken
        return ChatAntwort(text=text, denken=denken, werkzeugaufrufe=_aufrufe(nachricht.get("tool_calls")), ende=ende,
                           abgebrochen=ende == ABBRUCH, modell=antwort.headers.get("x-leitstelle-modell") or daten.get("model"),
                           knoten=antwort.headers.get("x-leitstelle-knoten"),
                           auftrag=antwort.headers.get("x-leitstelle-auftrag"), lage=antwort.headers.get("x-leitstelle-lage"),
                           verbrauch=_verbrauch(daten.get("usage")))

    async def chat_strom(self, nachrichten: Sequence[Nachricht | str], *, modell: str | None = None, titel: str = "",
                         prioritaet: Prioritaet | None = None, **optionen: Any) -> AsyncIterator[Ereignis]:
        """Stücke, solange gerechnet wird, `Wartet`, solange der Auftrag wartet, zuletzt `Ende` (mit den
        Werkzeugaufrufen, wenn `tools` mitging). Ein Fehler mitten im Strom kommt als Fehlerart; der Text bis dahin ist
        beim Aufrufer."""
        koerper = self._chat_koerper(nachrichten, modell, optionen, True)
        try:
            async with self._client.stream("POST", f"{self.adresse}/v1/chat/completions", json=koerper,
                                           headers=self.koepfe(titel, prioritaet), timeout=ARBEIT) as antwort:
                if antwort.status_code >= 400:
                    raise _fehler(antwort, (await antwort.aread()).decode("utf-8", "replace"))
                auftrag = antwort.headers.get("x-leitstelle-auftrag")
                lage = antwort.headers.get("x-leitstelle-lage")
                ende, modell_name, verbrauch = None, None, None
                aufrufe = _Aufrufsammler()
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
                        raise fehler_aus(502, f.get("code") or "", f.get("message") or "Fehler im Strom", rechner=_rechner(f))
                    modell_name = teil.get("model") or modell_name
                    verbrauch = _verbrauch(teil.get("usage")) or verbrauch
                    for wahl in teil.get("choices") or []:
                        delta = wahl.get("delta") or {}
                        text = delta.get("content")
                        if text:
                            yield Stueck(text=text)
                        aufrufe.aufnehmen(delta.get("tool_calls"))
                        ende = wahl.get("finish_reason") or ende
                yield Ende(ende=ende, abgebrochen=ende == ABBRUCH, werkzeugaufrufe=aufrufe.aufrufe(), modell=modell_name,
                           auftrag=auftrag, lage=lage, verbrauch=verbrauch)
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
                            lage=antwort.headers.get("x-leitstelle-lage"), verbrauch=_verbrauch(daten.get("usage")))

    async def bilder_erzeugen(self, beschreibung: str, *, groesse: str | None = "1024x1024", anzahl: int = 1,
                              startwert: int | None = None, modell: str | None = None, titel: str = "",
                              prioritaet: Prioritaet | None = None, schritte: int | None = None,
                              alternativen: Sequence[str] = ()) -> AsyncIterator[Bildereignis]:
        """Bilder über die Fähigkeit bild_erzeugen (`/v1/images/generations` als Strom): `Wartet`, solange der Auftrag
        wartet (etwa weil der Bilddienst erst startet), `Rechnet`, solange er rechnet, zuletzt `Bilder`. `groesse`
        None und `schritte` None: die Vorgabe des Modells (Steckbrief). `alternativen`: weitere Bildmodelle in der
        Reihenfolge der App, falls das gewählte nicht kann; gewählt wird nur aus dieser Liste."""
        koerper: dict[str, Any] = {"prompt": beschreibung, "n": anzahl, "response_format": "b64_json", "stream": True}
        if groesse:
            koerper["size"] = groesse
        if startwert is not None:
            koerper["seed"] = startwert
        if schritte is not None:
            koerper["steps"] = schritte
        if modell:
            koerper["model"] = modell
        if alternativen:
            koerper["alternativen"] = list(alternativen)
        async for e in self._bildstrom("/v1/images/generations", titel, prioritaet, json=koerper):
            yield e

    async def bilder_bearbeiten(self, beschreibung: str, vorlage: bytes, *, groesse: str | None = None, anzahl: int = 1,
                                startwert: int | None = None, modell: str | None = None, titel: str = "",
                                prioritaet: Prioritaet | None = None, schritte: int | None = None,
                                vorlage_typ: str = "image/png") -> AsyncIterator[Bildereignis]:
        """Bilder mit einer Bildvorlage (`/v1/images/edits`, Formular mit der Datei im Feld image, als Strom): nur für
        Modelle, deren Bild-Steckbrief `kann_bearbeiten` meldet. Ereignisse wie bei `bilder_erzeugen`."""
        felder: dict[str, str] = {"prompt": beschreibung, "n": str(anzahl), "response_format": "b64_json", "stream": "true"}
        for name, wert in (("size", groesse), ("seed", startwert), ("steps", schritte), ("model", modell)):
            if wert is not None and wert != "":
                felder[name] = str(wert)
        async for e in self._bildstrom("/v1/images/edits", titel, prioritaet, data=felder,
                                       files={"image": ("vorlage", vorlage, vorlage_typ)}):
            yield e

    async def _bildstrom(self, pfad: str, titel: str, prioritaet: Prioritaet | None, **art: Any) -> AsyncIterator[Bildereignis]:
        try:
            async with self._client.stream("POST", f"{self.adresse}{pfad}", headers=self.koepfe(titel, prioritaet), timeout=ARBEIT,
                                           **art) as antwort:
                if antwort.status_code >= 400:
                    raise _fehler(antwort, (await antwort.aread()).decode("utf-8", "replace"))
                auftrag = antwort.headers.get("x-leitstelle-auftrag")
                async for zeile in antwort.aiter_lines():
                    if zeile.startswith(":"):
                        treffer = _WARTET.match(zeile)
                        if treffer:
                            s = treffer.group("s")
                            yield Wartet(grund=treffer.group("grund"), sekunden=int(s) if s else None)
                        elif rechnet := _RECHNET.match(zeile):
                            yield Rechnet(seit_s=int(rechnet.group("s")))
                        continue
                    if not zeile.startswith("data:") or zeile[5:].strip() == "[DONE]":
                        continue
                    daten = json.loads(zeile[5:].strip())
                    if isinstance(daten.get("error"), dict):
                        f = daten["error"]
                        raise fehler_aus(502, f.get("code") or "", f.get("message") or "Fehler im Strom", rechner=_rechner(f))
                    zusatz = daten.get("x-leitstelle") or {}
                    yield Bilder(bilder=[Bild(daten=base64.b64decode(b["b64_json"]), beschreibung=b.get("revised_prompt") or "")
                                         for b in daten.get("data") or [] if b.get("b64_json")],
                                 startwert=zusatz.get("seed"), modell=zusatz.get("modell"), dauer_ms=zusatz.get("dauer_ms"),
                                 auftrag=auftrag)
        except httpx.TransportError as f:
            raise NichtErreichbar(f"Leitstelle nicht erreichbar: {type(f).__name__}") from f

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

    @contextlib.asynccontextmanager
    async def gebunden(self) -> AsyncIterator[Bindung]:
        """Alle Aufrufe dieses Dienstes in der Klammer gehen an dieselbe Instanz wie der erste (siehe `bindung`)."""
        b = Bindung(self.name)
        marke = GEBUNDEN.set({**GEBUNDEN.get(), self.name: b})
        try:
            yield b
        finally:
            GEBUNDEN.reset(marke)

    def _koepfe(self, titel: str, prioritaet: Prioritaet | None) -> dict[str, str]:
        kopf = self._ls.koepfe(titel, prioritaet)
        if (b := GEBUNDEN.get().get(self.name)) is not None and b.instanz:
            kopf[INSTANZ_KOPF] = b.instanz
        return kopf

    def _merken(self, antwort: httpx.Response) -> None:
        if (b := GEBUNDEN.get().get(self.name)) is not None and b.instanz is None:
            b.instanz = antwort.headers.get(INSTANZ_KOPF)

    async def anfrage(self, methode: str, pfad: str, *, titel: str = "", prioritaet: Prioritaet | None = None,
                      **art: Any) -> httpx.Response:
        """Rohe Anfrage (json, data, files, params wie bei httpx); die Antwort ist vollständig gelesen."""
        antwort = await self._ls._senden(methode, self._pfad(pfad), kopf=self._koepfe(titel, prioritaet), **art)
        self._merken(antwort)
        return antwort

    async def json(self, methode: str, pfad: str, *, titel: str = "", prioritaet: Prioritaet | None = None,
                   **art: Any) -> Any:
        return (await self.anfrage(methode, pfad, titel=titel, prioritaet=prioritaet, **art)).json()

    async def strom(self, pfad: str, *, titel: str = "", prioritaet: Prioritaet | None = None,
                    **art: Any) -> AsyncIterator[bytes]:
        """Eine große Antwort (etwa eine Tondatei) stückweise lesen."""
        try:
            async with self._ls._client.stream("GET", f"{self._ls.adresse}{self._pfad(pfad)}", timeout=ARBEIT,
                                               headers=self._koepfe(titel, prioritaet), **art) as antwort:
                if antwort.status_code >= 400:
                    raise _fehler(antwort, (await antwort.aread()).decode("utf-8", "replace"))
                self._merken(antwort)
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
