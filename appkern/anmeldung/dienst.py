"""Anmeldung an einer App mit dem Kellerwolke-Konto (Entscheidung des Nutzers, 17.10.2026).

Die App hat keine eigenen Konten. Sie reicht Anmeldung (Name und Passwort) oder Kopplung (Code vom Rechner) an die
Kellerwolke weiter und gibt deren Token an die Oberfläche; jede Anfrage prüft sie mit diesem Token bei der Kellerwolke,
das Ergebnis gilt `merken_s` Sekunden. Abmelden beendet die Sitzung in der Kellerwolke, auf einem gekoppelten Gerät
trennt es das Gerät.

Wer die App nutzen darf, sagt `erlaubt`: Vorgabe ist das Konto, dem der App-Schlüssel gehört (dort liegen die Dateien
der App), dazu weitere aus den Einstellungen. Ein anderes Konto wird abgewiesen; seine eben entstandene Sitzung oder
Kopplung beendet die App sofort wieder.

Auf dem iPhone hat jede Web-App vom Home-Bildschirm ihren eigenen Speicher: ein Telefon wird je App einmal gekoppelt
(mit einem Code aus der Kellerwolke, Einstellungen, Geräte).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from typing import Literal

import httpx
from pydantic import BaseModel

GERAET_PRAEFIX = "kw_geraet_"
_HOECHSTENS = 2000


class Konto(BaseModel):
    id: str
    name: str
    kuerzel: str | None = None
    rolle: str = "mitglied"
    geraet: bool = False             # mit einem gekoppelten Gerät angemeldet


class AnmeldungsFehler(Exception):
    status = 400

    def __init__(self, meldung: str, nochmal_in: int | None = None) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        self.nochmal_in = nochmal_in


class Abgelehnt(AnmeldungsFehler):
    """Name oder Passwort falsch, Code ungültig, Sitzung vorbei."""

    status = 401


class NichtErlaubt(AnmeldungsFehler):
    """Das Konto darf diese App nicht nutzen."""

    status = 403


class ZuVieleVersuche(AnmeldungsFehler):
    status = 429


class KellerwolkeWeg(AnmeldungsFehler):
    status = 503


def _meldung(antwort: httpx.Response, sonst: str) -> str:
    try:
        detail = antwort.json().get("detail")
        return detail if isinstance(detail, str) else sonst
    except ValueError:
        return sonst


class Anmeldung:
    def __init__(self, adresse: str, erlaubt: Callable[[], set[str]] | None = None, *,
                 client: httpx.AsyncClient | None = None, merken_s: float = 60.0) -> None:
        """`erlaubt()` liefert die Namen der Konten, die die App nutzen dürfen (klein geschrieben verglichen);
        None heißt: jedes aktive Konto der Kellerwolke."""
        self.adresse = adresse.rstrip("/")
        self.erlaubt = erlaubt
        self.merken_s = merken_s
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        self._eigener_client = client is None
        self._geheim = secrets.token_bytes(32)
        self._gemerkt: dict[str, tuple[Konto, float]] = {}

    def __repr__(self) -> str:
        return f"Anmeldung({self.adresse!r})"

    async def schliessen(self) -> None:
        if self._eigener_client:
            await self._client.aclose()

    def _schluessel(self, token: str) -> str:
        return hmac.new(self._geheim, token.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _senden(self, methode: str, pfad: str, **art) -> httpx.Response:
        try:
            return await self._client.request(methode, f"{self.adresse}{pfad}", **art)
        except httpx.TransportError as f:
            raise KellerwolkeWeg("Die Kellerwolke ist gerade nicht erreichbar") from f

    def _darf(self, konto: Konto) -> bool:
        if self.erlaubt is None:
            return True
        return konto.name.lower() in {n.lower() for n in self.erlaubt()}

    async def _nur_erlaubt(self, token: str, konto: Konto) -> Konto:
        if self._darf(konto):
            self._merken(token, konto)
            return konto
        await self.abmelden(token)
        raise NichtErlaubt(f"Das Konto {konto.name} darf diese App nicht nutzen")

    def _merken(self, token: str, konto: Konto) -> None:
        if len(self._gemerkt) >= _HOECHSTENS:
            self._gemerkt.pop(next(iter(self._gemerkt)))
        self._gemerkt[self._schluessel(token)] = (konto, time.monotonic() + self.merken_s)

    async def anmelden(self, kennung: str, passwort: str) -> tuple[str, Konto]:
        antwort = await self._senden("POST", "/api/v1/auth/login", json={"kennung": kennung, "passwort": passwort})
        if antwort.status_code == 401:
            raise Abgelehnt("Anmeldung fehlgeschlagen")
        if antwort.status_code >= 400:
            raise AnmeldungsFehler(_meldung(antwort, "Anmeldung fehlgeschlagen"))
        daten = antwort.json()
        token = daten["token"]
        return token, await self._nur_erlaubt(token, Konto(**{**daten["benutzer"], "id": str(daten["benutzer"]["id"])}))

    async def koppeln(self, code: str, name: str, art: Literal["webapp", "browser"]) -> tuple[str, Konto]:
        antwort = await self._senden("POST", "/api/v1/geraete/koppeln", json={"code": code, "name": name, "art": art})
        if antwort.status_code == 429:
            nochmal = antwort.headers.get("retry-after", "")
            raise ZuVieleVersuche(_meldung(antwort, "Zu viele falsche Codes"), int(nochmal) if nochmal.isdigit() else None)
        if antwort.status_code in (404, 422):
            raise Abgelehnt(_meldung(antwort, "Dieser Code gilt nicht (mehr)"))
        if antwort.status_code >= 400:
            raise AnmeldungsFehler(_meldung(antwort, "Koppeln fehlgeschlagen"))
        daten = antwort.json()
        schluessel = daten["schluessel"]
        konto = Konto(**{**daten["benutzer"], "id": str(daten["benutzer"]["id"])}, geraet=True)
        return schluessel, await self._nur_erlaubt(schluessel, konto)

    async def pruefen(self, token: str) -> Konto | None:
        """Das Konto zum Token, oder None (unbekannt, abgelaufen, getrennt, nicht erlaubt)."""
        if not token:
            return None
        schluessel = self._schluessel(token)
        gemerkt = self._gemerkt.get(schluessel)
        if gemerkt and gemerkt[1] > time.monotonic():
            return gemerkt[0] if self._darf(gemerkt[0]) else None
        self._gemerkt.pop(schluessel, None)
        antwort = await self._senden("GET", "/api/v1/auth/status", headers={"X-Kellerwolke-Sitzung": token})
        if antwort.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {antwort.status_code}")
        daten = antwort.json()
        if not daten.get("angemeldet") or not daten.get("benutzer"):
            return None
        b = daten["benutzer"]
        konto = Konto(**{**b, "id": str(b["id"])}, geraet=token.startswith(GERAET_PRAEFIX))
        if not self._darf(konto):
            return None
        self._merken(token, konto)
        return konto

    async def abmelden(self, token: str) -> None:
        self._gemerkt.pop(self._schluessel(token), None)
        if token:
            try:
                await self._senden("POST", "/api/v1/auth/logout", headers={"X-Kellerwolke-Sitzung": token})
            except KellerwolkeWeg:
                pass   # beim nächsten Prüfen ist der Token ohnehin nicht mehr gemerkt
