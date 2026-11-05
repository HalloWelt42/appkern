"""Anmeldung mit dem Kellerwolke-Konto: Name und Passwort gehen an die Kellerwolke, sie gibt eine Sitzung zurück, die nur
für den Posten gilt (`fuer_app`, die Kellerwolke gibt mit ihr keine Dateien heraus). Jede Anfrage prüft der Posten mit
dieser Sitzung bei der Kellerwolke; das Ergebnis gilt eine Weile (`merken_s`). Ist die Kellerwolke nicht erreichbar, trägt
eine früher bestätigte Sitzung bis `ausfall_s` nach der letzten Bestätigung weiter, damit man nicht ausgesperrt ist,
solange die Kellerwolke neu startet. Eine nie bestätigte Sitzung und jede neue Anmeldung brauchen die Kellerwolke.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

_HOECHSTENS = 500          # so viele Sitzungen merkt sich der Posten höchstens


class Konto(BaseModel):
    id: str
    name: str
    rolle: str = "mitglied"


class KellerwolkeWeg(RuntimeError):
    """Die Kellerwolke antwortet nicht oder mit einem Fehler."""


@dataclass
class _Gemerkt:
    konto: Konto
    frisch_bis: float
    bestaetigt: float


class Kellerwolke:
    def __init__(self, adresse: str, ca_datei: str | None, app: str, merken_s: float = 60.0, ausfall_s: float = 24 * 3600,
                 client: httpx.AsyncClient | None = None, uhr: Callable[[], float] = time.monotonic) -> None:
        self.adresse = adresse.rstrip("/")
        self.app = app
        self.merken_s, self.ausfall_s = merken_s, ausfall_s
        self._client = client or httpx.AsyncClient(base_url=self.adresse, verify=ca_datei or True, timeout=httpx.Timeout(10.0))
        self._uhr = uhr
        self._gemerkt: dict[str, _Gemerkt] = {}

    async def schliessen(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _schluessel(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    async def _senden(self, methode: str, pfad: str, **kw) -> httpx.Response:
        try:
            return await self._client.request(methode, pfad, **kw)
        except httpx.HTTPError as f:
            raise KellerwolkeWeg(f"Kellerwolke nicht erreichbar: {type(f).__name__}") from f

    async def anmelden(self, kennung: str, passwort: str) -> tuple[str, Konto] | None:
        """Sitzung und Konto, oder None bei falschem Namen oder Passwort."""
        r = await self._senden("POST", "/api/v1/auth/login", json={"kennung": kennung, "passwort": passwort, "fuer_app": self.app})
        if r.status_code == 401:
            return None
        if r.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {r.status_code}")
        daten = r.json()
        b = daten["benutzer"]
        konto = Konto(id=str(b["id"]), name=b["name"], rolle=b.get("rolle") or "mitglied")
        self._ablegen(daten["token"], konto)
        return daten["token"], konto

    async def pruefen(self, token: str) -> Konto | None:
        """Das Konto zur Sitzung, oder None (unbekannt, abgelaufen, für eine andere App). `KellerwolkeWeg`, wenn sie
        nicht erreichbar ist und keine frühere Bestätigung trägt."""
        if not token:
            return None
        schluessel = self._schluessel(token)
        gemerkt = self._gemerkt.get(schluessel)
        jetzt = self._uhr()
        if gemerkt and gemerkt.frisch_bis > jetzt:
            return gemerkt.konto
        try:
            r = await self._senden("GET", "/api/v1/auth/status", headers={"X-Kellerwolke-Sitzung": token})
            if r.status_code >= 400:
                raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {r.status_code}")
        except KellerwolkeWeg:
            if gemerkt and jetzt - gemerkt.bestaetigt <= self.ausfall_s:
                gemerkt.frisch_bis = jetzt + self.merken_s     # erst nach merken_s wieder nachfragen
                return gemerkt.konto
            raise
        daten = r.json()
        b = daten.get("benutzer")
        # nur eine Sitzung, die die Kellerwolke für genau diesen Posten ausgestellt hat
        if not daten.get("angemeldet") or not b or (daten.get("app") or "").lower() != self.app.lower():
            self._gemerkt.pop(schluessel, None)
            return None
        konto = Konto(id=str(b["id"]), name=b["name"], rolle=b.get("rolle") or "mitglied")
        self._ablegen(token, konto)
        return konto

    def _ablegen(self, token: str, konto: Konto) -> None:
        schluessel = self._schluessel(token)
        if schluessel not in self._gemerkt and len(self._gemerkt) >= _HOECHSTENS:
            self._gemerkt.pop(next(iter(self._gemerkt)))
        jetzt = self._uhr()
        self._gemerkt[schluessel] = _Gemerkt(konto, jetzt + self.merken_s, jetzt)

    async def abmelden(self, token: str) -> None:
        self._gemerkt.pop(self._schluessel(token), None)
        if token:
            try:
                await self._senden("POST", "/api/v1/auth/logout", headers={"X-Kellerwolke-Sitzung": token})
            except KellerwolkeWeg:
                pass          # die Sitzung ist hier vergessen; in der Kellerwolke läuft sie von selbst ab
