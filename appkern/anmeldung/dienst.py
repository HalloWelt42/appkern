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

Ist die Kellerwolke gerade nicht erreichbar, gilt eine Anmeldung, die sie früher bestätigt hat, aus dem Merker weiter,
bis `ausfall_s` nach der letzten Bestätigung (Vorgabe 24 Stunden); nachgefragt wird dann im Hintergrund, keine Anfrage
wartet darauf. So bleibt die App bedienbar, und man kann etwa die Adresse der Kellerwolke berichtigen, statt
ausgesperrt zu sein. Eine nie bestätigte Anmeldung und jede neue Anmeldung brauchen die Kellerwolke.

Andere Apps (App zu App, Entscheidung des Nutzers, 17.10.2026) melden sich mit ihrem App-Schlüssel der Kellerwolke an
(`kw_app_...`). Die App fragt die Kellerwolke, wem der Schlüssel gehört (`/api/v1/ablage/ich`), und lässt dieselben
Konten zu wie in der Oberfläche; das Konto trägt dann den Namen der rufenden App. Abmelden beendet einen App-Schlüssel
nie (er gehört der anderen App).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

import httpx
from pydantic import BaseModel

logger = logging.getLogger("appkern.anmeldung")

GERAET_PRAEFIX = "kw_geraet_"
APP_PRAEFIX = "kw_app_"
AUSFALL_S = 24 * 3600     # so lange trägt eine Bestätigung der Kellerwolke durch ihren Ausfall
_HOECHSTENS = 2000


class Konto(BaseModel):
    id: str
    name: str
    kuerzel: str | None = None
    rolle: str = "mitglied"
    geraet: bool = False             # mit einem gekoppelten Gerät angemeldet
    app: str | None = None           # eine andere App, angemeldet mit ihrem App-Schlüssel der Kellerwolke
    im_auftrag: str | None = None    # ein Mensch, dessen Sitzung eine andere App auf seinen Klick mitschickt

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


@dataclass
class _Gemerkt:
    """Eine geprüfte Anmeldung: gilt bis `frisch_bis` ohne Rückfrage; `bestaetigt` ist die letzte Bestätigung durch
    die Kellerwolke, `ausfall` sagt, dass die letzte Rückfrage sie nicht erreichte."""

    konto: Konto
    frisch_bis: float
    bestaetigt: float
    ausfall: bool = False


def _meldung(antwort: httpx.Response, sonst: str) -> str:
    try:
        detail = antwort.json().get("detail")
        return detail if isinstance(detail, str) else sonst
    except ValueError:
        return sonst


class Anmeldung:
    def __init__(self, adresse: str, erlaubt: Callable[[], set[str]] | None = None, *,
                 client: httpx.AsyncClient | None = None, merken_s: float = 60.0, ausfall_s: float = AUSFALL_S,
                 app_name: Callable[[], Awaitable[str | None]] | None = None,
                 uhr: Callable[[], float] = time.monotonic) -> None:
        """`erlaubt()` liefert die Namen der Konten, die die App nutzen dürfen (klein geschrieben verglichen);
        None heißt: jedes aktive Konto der Kellerwolke. `app_name()` ist der Name der App in der Kellerwolke (der ihres
        Zugangs); Anmeldungen gelten dann nur für sie, und ohne bekannten Namen gibt es keine Anmeldung. `merken_s`:
        so lange gilt eine Prüfung ohne Rückfrage; `ausfall_s`: so lange nach der letzten Bestätigung gilt eine
        Anmeldung weiter, wenn die Kellerwolke nicht erreichbar ist (0: gar nicht)."""
        self.adresse = adresse.rstrip("/")
        self.erlaubt = erlaubt
        self._app_name = app_name
        self.merken_s = merken_s
        self.ausfall_s = ausfall_s
        self._uhr = uhr
        self._eigener_client = client is None and bool(self.adresse)
        self._client = client or (httpx.AsyncClient(timeout=httpx.Timeout(10.0)) if self.adresse else None)
        self._geheim = secrets.token_bytes(32)
        self._gemerkt: dict[str, _Gemerkt] = {}
        self._nachfragen: dict[str, asyncio.Task] = {}
        self._im_ausfall = False

    def verbinden(self, adresse: str, client: httpx.AsyncClient | None) -> None:
        """Neue Kellerwolke (etwa nach geänderten Einstellungen); den Client verwaltet der Aufrufer. Gemerkte
        Prüfungen werden neu gefragt; ihre letzte Bestätigung trägt weiter durch einen Ausfall (etwa wenn die neue
        Adresse auch nicht stimmt)."""
        self.adresse = adresse.rstrip("/")
        self._client = client
        self._eigener_client = False
        self._nachfragen_beenden()
        for g in self._gemerkt.values():
            g.frisch_bis, g.ausfall = 0.0, False

    def __repr__(self) -> str:
        return f"Anmeldung({self.adresse!r})"

    async def schliessen(self) -> None:
        self._nachfragen_beenden()
        if self._eigener_client and self._client is not None:
            await self._client.aclose()

    def _nachfragen_beenden(self) -> None:
        for aufgabe in self._nachfragen.values():
            aufgabe.cancel()
        self._nachfragen.clear()

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
        self._ablegen(self._schluessel(token), konto)

    def _ablegen(self, schluessel: str, konto: Konto) -> None:
        if schluessel not in self._gemerkt and len(self._gemerkt) >= _HOECHSTENS:
            self._gemerkt.pop(next(iter(self._gemerkt)))
        jetzt = self._uhr()
        self._gemerkt[schluessel] = _Gemerkt(konto, jetzt + self.merken_s, jetzt)
        if self._im_ausfall:
            self._im_ausfall = False
            logger.info("Kellerwolke wieder erreichbar: Anmeldungen werden wieder bei ihr geprüft")

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
                            f"{self.adresse} stammen, mit der diese App verbunden ist; ein Code aus einer anderen "
                            "Kellerwolke gilt hier nie.")
        if antwort.status_code >= 400:
            raise AnmeldungsFehler(_meldung(antwort, "Koppeln fehlgeschlagen"))
        daten = antwort.json()
        schluessel = daten["schluessel"]
        konto = Konto(**{**daten["benutzer"], "id": str(daten["benutzer"]["id"])}, geraet=True)
        return schluessel, await self._nur_erlaubt(schluessel, konto)

    async def pruefen(self, token: str) -> Konto | None:
        """Das Konto zum Token, oder None (unbekannt, abgelaufen, getrennt, nicht erlaubt). Ist die Kellerwolke nicht
        erreichbar, gilt eine früher bestätigte Anmeldung bis `ausfall_s` weiter; sonst `KellerwolkeWeg`."""
        if not token:
            return None
        schluessel = self._schluessel(token)
        gemerkt = self._gemerkt.get(schluessel)
        jetzt = self._uhr()
        if gemerkt and gemerkt.frisch_bis > jetzt:
            return self._erlaubtes(gemerkt.konto)
        if gemerkt and gemerkt.ausfall and self._traegt(gemerkt, jetzt):
            self._spaeter_fragen(token, schluessel)     # im Ausfall wartet keine Anfrage auf die Kellerwolke
            return self._erlaubtes(gemerkt.konto)
        try:
            konto = await self._fragen(token)
        except KellerwolkeWeg:
            if gemerkt is None or not self._traegt(gemerkt, jetzt):
                raise
            self._ausfall(gemerkt)
            return self._erlaubtes(gemerkt.konto)
        return self._uebernehmen(token, schluessel, konto)

    def _erlaubtes(self, konto: Konto) -> Konto | None:
        return konto if self._darf(konto) else None

    def _traegt(self, gemerkt: _Gemerkt, jetzt: float) -> bool:
        return jetzt - gemerkt.bestaetigt <= self.ausfall_s

    def _ausfall(self, gemerkt: _Gemerkt) -> None:
        """Die Kellerwolke war weg: aus dem Merker antworten, frühestens nach `merken_s` wieder nachfragen."""
        gemerkt.ausfall, gemerkt.frisch_bis = True, self._uhr() + self.merken_s
        if not self._im_ausfall:
            self._im_ausfall = True
            logger.warning("Kellerwolke nicht erreichbar: bestätigte Anmeldungen gelten aus dem Merker weiter "
                           "(bis %.0f h nach der letzten Bestätigung)", self.ausfall_s / 3600)

    async def _fragen(self, token: str) -> Konto | None:
        return await (self._app_pruefen(token) if token.startswith(APP_PRAEFIX) else self._sitzung_pruefen(token))

    def _uebernehmen(self, token: str, schluessel: str, konto: Konto | None) -> Konto | None:
        if konto is None or not self._darf(konto):
            self._gemerkt.pop(schluessel, None)
            return None
        self._merken(token, konto)
        return konto

    def _spaeter_fragen(self, token: str, schluessel: str) -> None:
        """Eine Rückfrage je Anmeldung im Hintergrund; ihr Ergebnis gilt für die nächsten Anfragen."""
        if schluessel in self._nachfragen:
            return

        async def fragen() -> None:
            try:
                self._uebernehmen(token, schluessel, await self._fragen(token))
            except KellerwolkeWeg:
                if (gemerkt := self._gemerkt.get(schluessel)) is not None:
                    self._ausfall(gemerkt)
            except Exception:  # noqa: BLE001 - die Rückfrage im Hintergrund darf nie ins Leere fallen
                logger.exception("Anmeldung im Hintergrund nicht prüfbar")
            finally:
                self._nachfragen.pop(schluessel, None)

        self._nachfragen[schluessel] = asyncio.create_task(fragen(), name="anmeldung-nachfragen")

    async def _app_pruefen(self, schluessel: str) -> Konto | None:
        antwort = await self._senden("GET", "/api/v1/ablage/ich", headers={"Authorization": f"Bearer {schluessel}"})
        if antwort.status_code in (401, 403):
            return None
        if antwort.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {antwort.status_code}")
        ich = antwort.json()
        return Konto(id=str(ich.get("konto_id") or ich["konto"]), name=ich["konto"], app=ich["app"])

    async def _status(self, token: str) -> tuple[Konto, str | None] | None:
        """Konto und App-Bindung einer Sitzung laut Kellerwolke; None, wenn sie nicht (mehr) gilt. Die Bindung ist ""
        für eine volle Sitzung und None, wenn die Kellerwolke keine Bindung kennt (vor 0.81)."""
        antwort = await self._senden("GET", "/api/v1/auth/status", headers={"X-Kellerwolke-Sitzung": token})
        if antwort.status_code >= 400:
            raise KellerwolkeWeg(f"Die Kellerwolke antwortet mit {antwort.status_code}")
        daten = antwort.json()
        if not daten.get("angemeldet") or not daten.get("benutzer"):
            return None
        b = daten["benutzer"]
        return Konto(**{**b, "id": str(b["id"])}, geraet=token.startswith(GERAET_PRAEFIX)), (
            (daten.get("app") or "") if "app" in daten else None)

    async def _sitzung_pruefen(self, token: str) -> Konto | None:
        stand = await self._status(token)
        if stand is None:
            return None
        konto, gebunden = stand
        eigene = await self._eigener_name()
        if eigene and gebunden is not None and gebunden.lower() != eigene.lower():
            if not gebunden:
                await self.abmelden(token)     # volle Sitzung der Kellerwolke: gehört in keine App
            return None                        # Sitzung einer anderen App: gilt hier nicht und bleibt dort gültig
        return konto

    async def im_auftrag(self, token: str, app: str) -> Konto | None:
        """Die Sitzung eines Menschen, die die App `app` (mit ihrem App-Schlüssel angemeldet) auf seinen Klick
        mitschickt: gilt, wenn die Kellerwolke sie für genau diese App bestätigt und das Konto die App hier nutzen
        darf. Gemerkt wie jede Prüfung; beendet wird sie hier nie."""
        if not token or not app or token.startswith(APP_PRAEFIX):
            return None
        schluessel = self._schluessel(f"{app.lower()}\n{token}")
        gemerkt = self._gemerkt.get(schluessel)
        if gemerkt and gemerkt.frisch_bis > self._uhr():
            return self._erlaubtes(gemerkt.konto)
        stand = await self._status(token)
        if stand is None or (stand[1] or "").lower() != app.lower() or not self._darf(stand[0]):
            self._gemerkt.pop(schluessel, None)
            return None
        konto = stand[0].model_copy(update={"im_auftrag": app})
        self._ablegen(schluessel, konto)
        return konto

    async def abmelden(self, token: str) -> None:
        schluessel = self._schluessel(token)
        self._gemerkt.pop(schluessel, None)
        nachfrage = self._nachfragen.pop(schluessel, None)
        if nachfrage is not None and nachfrage is not asyncio.current_task():
            nachfrage.cancel()
        if token and not token.startswith(APP_PRAEFIX):
            try:
                await self._senden("POST", "/api/v1/auth/logout", headers={"X-Kellerwolke-Sitzung": token})
            except KellerwolkeWeg:
                pass   # beim nächsten Prüfen ist der Token ohnehin nicht mehr gemerkt
