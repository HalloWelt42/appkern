"""Anmeldung mit dem Kellerwolke-Konto: Name und Passwort gehen an die Kellerwolke, sie gibt eine Sitzung zurück, die nur
für den Posten gilt (`fuer_app`, die Kellerwolke gibt mit ihr keine Dateien heraus). Jede Anfrage prüft der Posten mit
dieser Sitzung bei der Kellerwolke; das Ergebnis gilt eine Weile (`merken_s`). Ist die Kellerwolke nicht erreichbar, trägt
eine früher bestätigte Sitzung bis `ausfall_s` nach der letzten Bestätigung weiter, damit man nicht ausgesperrt ist,
solange die Kellerwolke neu startet. Eine nie bestätigte Sitzung und jede neue Anmeldung brauchen die Kellerwolke.

Programme kommen ohne Sitzung durch: mit dem App-Schlüssel der Kellerwolke ihrer App (`kw_app_...`, Kopf Authorization),
wie überall im Verbund (HELF-169). Die Kellerwolke nennt Konto und Rolle des Schlüssels (`/api/v1/ablage/ich`); gemerkt
und im Ausfall getragen wird er wie eine Sitzung.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

_HOECHSTENS = 500          # so viele Sitzungen und App-Schlüssel merkt sich der Posten höchstens
APP_PRAEFIX = "kw_app_"    # App-Schlüssel der Kellerwolke


class Konto(BaseModel):
    id: str
    name: str
    rolle: str = "mitglied"
    app: str | None = None   # mit dem App-Schlüssel dieser App gekommen (kein Mensch)


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
        return await self._bestaetigt(token, self._sitzung_fragen)

    async def app_pruefen(self, schluessel: str) -> Konto | None:
        """Konto und App zu einem App-Schlüssel der Kellerwolke, oder None (kein App-Schlüssel, unbekannt, gesperrt).
        `KellerwolkeWeg` wie bei `pruefen`."""
        if not schluessel.startswith(APP_PRAEFIX):
            return None
        return await self._bestaetigt(schluessel, self._app_fragen)

    async def _bestaetigt(self, token: str, fragen: Callable[[str], Awaitable[Konto | None]]) -> Konto | None:
        """Gemerkt, sonst die Kellerwolke gefragt; im Ausfall trägt eine frühere Bestätigung bis `ausfall_s`."""
        if not token:
            return None
        schluessel = self._schluessel(token)
        gemerkt = self._gemerkt.get(schluessel)
        jetzt = self._uhr()
        if gemerkt and gemerkt.frisch_bis > jetzt:
            return gemerkt.konto
        try:
            konto = await fragen(token)
        except KellerwolkeWeg:
            if gemerkt and jetzt - gemerkt.bestaetigt <= self.ausfall_s:
                gemerkt.frisch_bis = jetzt + self.merken_s     # erst nach merken_s wieder nachfragen
                return gemerkt.konto
            raise
        if konto is None:
            self._gemerkt.pop(schluessel, None)
            return None
        self._ablegen(token, konto)
        return konto

    async def _sitzung_fragen(self, token: str) -> Konto | None:
        r = await self._senden("GET", "/api/v1/auth/status", headers={"X-Kellerwolke-Sitzung": token})
        if r.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {r.status_code}")
        daten = r.json()
        b = daten.get("benutzer")
        # nur eine Sitzung, die die Kellerwolke für genau diesen Posten ausgestellt hat
        if not daten.get("angemeldet") or not b or (daten.get("app") or "").lower() != self.app.lower():
            return None
        return Konto(id=str(b["id"]), name=b["name"], rolle=b.get("rolle") or "mitglied")

    async def _app_fragen(self, schluessel: str) -> Konto | None:
        r = await self._senden("GET", "/api/v1/ablage/ich", headers={"Authorization": f"Bearer {schluessel}"})
        if r.status_code in (401, 403):
            return None
        if r.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {r.status_code}")
        ich = r.json()
        # ohne Rolle (Kellerwolke vor 0.95.1) gilt das Konto als Mitglied: dann lässt nur eine Liste erlaubter Konten durch
        return Konto(id=str(ich.get("konto_id") or ich["konto"]), name=ich["konto"], rolle=ich.get("rolle") or "mitglied",
                     app=ich.get("app") or "")

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
