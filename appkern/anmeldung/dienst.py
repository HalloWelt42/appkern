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

Die Sitzung oder der Geräteschlüssel, die eine App so erhält, gilt nur für diese App (Entscheidung 17.10.2026, kein
Dauerrecht über das Konto; Kellerwolke ab 0.81): die App nennt beim Anmelden und Koppeln ihren Namen, und die
Kellerwolke gibt mit einer solchen Anmeldung keine Dateien heraus. Eine Anmeldung, die nicht für diese App gilt (etwa
eine ältere volle Sitzung), beendet die App sofort; dann meldet man sich einmal neu an.

Andere Apps (App zu App, Entscheidung des Nutzers, 17.10.2026) melden sich mit ihrem App-Schlüssel der Kellerwolke an
(`kw_app_...`). Die App fragt die Kellerwolke, wem der Schlüssel gehört (`/api/v1/ablage/ich`), und lässt dieselben
Konten zu wie in der Oberfläche; das Konto trägt dann den Namen der rufenden App. Abmelden beendet einen App-Schlüssel
nie (er gehört der anderen App).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections.abc import Awaitable, Callable
from typing import Literal

import httpx
from pydantic import BaseModel

GERAET_PRAEFIX = "kw_geraet_"
APP_PRAEFIX = "kw_app_"
_HOECHSTENS = 2000


class Konto(BaseModel):
    id: str
    name: str
    kuerzel: str | None = None
    rolle: str = "mitglied"
    geraet: bool = False             # mit einem gekoppelten Gerät angemeldet
    app: str | None = None           # eine andere App, angemeldet mit ihrem App-Schlüssel der Kellerwolke

    @property
    def mensch(self) -> bool:
        return self.app is None


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
                 client: httpx.AsyncClient | None = None, merken_s: float = 60.0,
                 app_name: Callable[[], Awaitable[str | None]] | None = None) -> None:
        """`erlaubt()` liefert die Namen der Konten, die die App nutzen dürfen (klein geschrieben verglichen);
        None heißt: jedes aktive Konto der Kellerwolke. `app_name()` ist der Name der App in der Kellerwolke (der ihres
        Zugangs); Anmeldungen gelten dann nur für sie, und ohne bekannten Namen gibt es keine Anmeldung."""
        self.adresse = adresse.rstrip("/")
        self.erlaubt = erlaubt
        self._app_name = app_name
        self.merken_s = merken_s
        self._eigener_client = client is None and bool(self.adresse)
        self._client = client or (httpx.AsyncClient(timeout=httpx.Timeout(10.0)) if self.adresse else None)
        self._geheim = secrets.token_bytes(32)
        self._gemerkt: dict[str, tuple[Konto, float]] = {}

    def verbinden(self, adresse: str, client: httpx.AsyncClient | None) -> None:
        """Neue Kellerwolke (etwa nach geänderten Einstellungen); den Client verwaltet der Aufrufer. Gemerkte
        Prüfungen verfallen."""
        self.adresse = adresse.rstrip("/")
        self._client = client
        self._eigener_client = False
        self._gemerkt.clear()

    def __repr__(self) -> str:
        return f"Anmeldung({self.adresse!r})"

    async def schliessen(self) -> None:
        if self._eigener_client and self._client is not None:
            await self._client.aclose()

    def _schluessel(self, token: str) -> str:
        return hmac.new(self._geheim, token.encode("utf-8"), hashlib.sha256).hexdigest()

    async def _senden(self, methode: str, pfad: str, **art) -> httpx.Response:
        if self._client is None or not self.adresse:
            raise KellerwolkeWeg("Keine Kellerwolke eingerichtet")
        try:
            return await self._client.request(methode, f"{self.adresse}{pfad}", **art)
        except httpx.TransportError as f:
            raise KellerwolkeWeg("Die Kellerwolke ist gerade nicht erreichbar") from f

    async def _eigener_name(self) -> str | None:
        """Name der App in der Kellerwolke; None ohne Namensquelle (Anmeldung ohne App-Bindung, etwa in Tests)."""
        if self._app_name is None:
            return None
        name = await self._app_name()
        if not name:
            raise KellerwolkeWeg("Die App kennt ihren Zugang in der Kellerwolke gerade nicht (Einstellungen, Verbindungen)")
        return name

    async def _fuer_app(self) -> dict[str, str]:
        name = await self._eigener_name()
        return {"fuer_app": name} if name else {}

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
        antwort = await self._senden("POST", "/api/v1/auth/login",
                                     json={"kennung": kennung, "passwort": passwort, **await self._fuer_app()})
        if antwort.status_code == 401:
            raise Abgelehnt("Anmeldung fehlgeschlagen")
        if antwort.status_code >= 400:
            raise AnmeldungsFehler(_meldung(antwort, "Anmeldung fehlgeschlagen"))
        daten = antwort.json()
        token = daten["token"]
        return token, await self._nur_erlaubt(token, Konto(**{**daten["benutzer"], "id": str(daten["benutzer"]["id"])}))

    async def koppeln(self, code: str, name: str, art: Literal["webapp", "browser"]) -> tuple[str, Konto]:
        antwort = await self._senden("POST", "/api/v1/geraete/koppeln",
                                     json={"code": code, "name": name, "art": art, **await self._fuer_app()})
        if antwort.status_code == 429:
            nochmal = antwort.headers.get("retry-after", "")
            raise ZuVieleVersuche(_meldung(antwort, "Zu viele falsche Codes"), int(nochmal) if nochmal.isdigit() else None)
        if antwort.status_code in (404, 422):
            # Häufigster Grund außer Ablauf: der Code stammt aus einer anderen Kellerwolke als der dieser App.
            raise Abgelehnt(f"{_meldung(antwort, 'Dieser Code gilt nicht (mehr).')} Er muss aus der Kellerwolke unter "
                            f"{self.adresse} stammen, mit der diese App verbunden ist.")
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
        konto = await (self._app_pruefen(token) if token.startswith(APP_PRAEFIX) else self._sitzung_pruefen(token))
        if konto is None or not self._darf(konto):
            return None
        self._merken(token, konto)
        return konto

    async def _app_pruefen(self, schluessel: str) -> Konto | None:
        antwort = await self._senden("GET", "/api/v1/ablage/ich", headers={"Authorization": f"Bearer {schluessel}"})
        if antwort.status_code in (401, 403):
            return None
        if antwort.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {antwort.status_code}")
        ich = antwort.json()
        return Konto(id=str(ich.get("konto_id") or ich["konto"]), name=ich["konto"], app=ich["app"])

    async def _sitzung_pruefen(self, token: str) -> Konto | None:
        antwort = await self._senden("GET", "/api/v1/auth/status", headers={"X-Kellerwolke-Sitzung": token})
        if antwort.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {antwort.status_code}")
        daten = antwort.json()
        if not daten.get("angemeldet") or not daten.get("benutzer"):
            return None
        eigene = await self._eigener_name()
        if eigene and "app" in daten and (daten.get("app") or "").lower() != eigene.lower():
            # Gilt nicht für diese App (eine volle Sitzung der Kellerwolke oder die einer anderen App): beenden.
            await self.abmelden(token)
            return None
        b = daten["benutzer"]
        return Konto(**{**b, "id": str(b["id"])}, geraet=token.startswith(GERAET_PRAEFIX))

    async def abmelden(self, token: str) -> None:
        self._gemerkt.pop(self._schluessel(token), None)
        if token and not token.startswith(APP_PRAEFIX):
            try:
                await self._senden("POST", "/api/v1/auth/logout", headers={"X-Kellerwolke-Sitzung": token})
            except KellerwolkeWeg:
                pass   # beim nächsten Prüfen ist der Token ohnehin nicht mehr gemerkt
