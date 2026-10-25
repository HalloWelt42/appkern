"""Mitteilungen aufs Gerät (Web Push): ein Schlüsselpaar je App (VAPID), entstanden beim ersten Bedarf in ihrer
Datenbank; Abos je Konto und Gerät; Versand an alle Geräte einer Person, verschlüsselt nach RFC 8291 (aes128gcm) und
unterschrieben nach RFC 8292. Gesendet wird über httpx wie jede Verbindung der App (in Tests über den Transport des
Gerüsts). Ein Abo, das der Push-Dienst nicht mehr kennt (404, 410), geht von selbst."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlsplit

import http_ece
import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02
from pydantic import BaseModel, Field

from ..datenbank import Datenbank

log = logging.getLogger(__name__)

BAUSTEIN = "appkern_push"
STUFEN = ["""
CREATE TABLE appkern_push_schluessel (id INTEGER PRIMARY KEY CHECK (id = 1), privat TEXT NOT NULL);
CREATE TABLE appkern_push_abos (
  endpunkt TEXT PRIMARY KEY, konto TEXT NOT NULL, p256dh TEXT NOT NULL, auth TEXT NOT NULL, geraet TEXT NOT NULL,
  angelegt TEXT NOT NULL, zuletzt TEXT
);
CREATE INDEX appkern_push_abos_konto ON appkern_push_abos(konto);
"""]
#: so lange gilt die Unterschrift eines Versands (höchstens 24 Stunden erlaubt)
UNTERSCHRIFT_S = 12 * 3600
ZEITGRENZE_S = 20.0


class AboSchluessel(BaseModel):
    p256dh: str = Field(min_length=20, max_length=200)
    auth: str = Field(min_length=8, max_length=100)


class Abo(BaseModel):
    """Ein Abo, wie der Browser es mit `PushSubscription.toJSON()` liefert."""

    endpoint: str = Field(pattern=r"^https://[^\s]+$", max_length=2000)
    keys: AboSchluessel


class Geraet(BaseModel):
    """Ein Gerät, das Mitteilungen bekommt (ohne den Endpunkt, der ist ein Geheimnis des Abos)."""

    id: str
    name: str
    angelegt: str
    zuletzt: str | None = None


class Mitteilung(BaseModel):
    titel: str
    text: str = ""
    #: wohin ein Tippen führt (ein Weg der App)
    url: str = "/"
    #: gleiche Kennung ersetzt eine noch sichtbare Mitteilung, statt eine zweite zu zeigen
    tag: str | None = None
    dringend: bool = False
    #: so lange hebt der Push-Dienst die Mitteilung für ein Gerät auf, das gerade nicht erreichbar ist
    ttl: int = 24 * 3600


class Versand(BaseModel):
    zugestellt: int = 0
    #: Abos, die es nicht mehr gibt (abbestellt, Gerät weg): entfernt
    entfernt: int = 0
    fehler: int = 0


def _b64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def geraet_id(endpunkt: str) -> str:
    return hashlib.sha256(endpunkt.encode()).hexdigest()[:16]


def _thema(tag: str) -> str:
    """Topic-Kopf (höchstens 32 Zeichen base64url): eine noch nicht zugestellte Mitteilung gleichen Themas ersetzt der
    Push-Dienst."""
    return base64.urlsafe_b64encode(hashlib.sha256(tag.encode()).digest()).rstrip(b"=").decode()[:32]


def verschluesseln(nutzlast: bytes, p256dh: str, auth: str) -> bytes:
    """Inhalt für ein Abo nach RFC 8291: mit einem Schlüssel nur für diese Nachricht, lesbar nur für das Gerät."""
    return http_ece.encrypt(nutzlast, salt=os.urandom(16), private_key=ec.generate_private_key(ec.SECP256R1()),
                            dh=_b64(p256dh), auth_secret=_b64(auth), version="aes128gcm")


class Push:
    def __init__(self, db: Datenbank, absender: Callable[[], str], *, transport: httpx.AsyncBaseTransport | None = None,
                 jetzt: Callable[[], str] | None = None) -> None:
        """`absender`: Adresse, unter der der Betreiber der App erreichbar ist (die Adresse der App oder mailto:), der
        Push-Dienst verlangt sie in der Unterschrift."""
        self.db = db
        self.absender = absender
        self.transport = transport
        self.jetzt = jetzt or (lambda: datetime.now().astimezone().replace(microsecond=0, tzinfo=None).isoformat())
        self._eingerichtet = False
        self._vapid: Vapid02 | None = None
        self._sperre = asyncio.Lock()

    async def _bereit(self) -> None:
        if not self._eingerichtet:
            await self.db.einrichten(BAUSTEIN, STUFEN)
            self._eingerichtet = True

    async def _schluessel(self) -> Vapid02:
        if self._vapid is not None:
            return self._vapid
        async with self._sperre:
            if self._vapid is None:
                await self._bereit()
                zeile = await self.db.zeile("SELECT privat FROM appkern_push_schluessel WHERE id = 1")
                if zeile is None:
                    neu = Vapid02()
                    neu.generate_keys()
                    await self.db.ausfuehren("INSERT INTO appkern_push_schluessel (id, privat) VALUES (1, ?)",
                                             (neu.private_pem().decode(),))
                    log.info("Neues Schlüsselpaar für Mitteilungen angelegt")
                    zeile = {"privat": neu.private_pem().decode()}
                self._vapid = Vapid02.from_pem(zeile["privat"].encode())
        return self._vapid

    async def oeffentlich(self) -> str:
        """Öffentlicher Schlüssel als base64url: der `applicationServerKey`, mit dem die Oberfläche das Abo anlegt."""
        punkt = (await self._schluessel()).public_key.public_bytes(serialization.Encoding.X962,
                                                                   serialization.PublicFormat.UncompressedPoint)
        return base64.urlsafe_b64encode(punkt).rstrip(b"=").decode()

    async def abo_setzen(self, konto: str, abo: Abo, geraet: str) -> Geraet:
        """Ein Gerät meldet sein Abo; ein Endpunkt gehört immer nur einem Konto (meldet sich auf dem Gerät jemand
        anderes an, geht das Abo an ihn über)."""
        await self._bereit()
        name = " ".join(geraet.split())[:80] or "Gerät"
        jetzt = self.jetzt()
        await self.db.ausfuehren(
            "INSERT INTO appkern_push_abos (endpunkt, konto, p256dh, auth, geraet, angelegt) VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(endpunkt) DO UPDATE SET konto=excluded.konto, p256dh=excluded.p256dh, auth=excluded.auth, "
            "geraet=excluded.geraet", (abo.endpoint, konto, abo.keys.p256dh, abo.keys.auth, name, jetzt))
        zeile = await self.db.zeile("SELECT angelegt, zuletzt FROM appkern_push_abos WHERE endpunkt = ?", (abo.endpoint,))
        return Geraet(id=geraet_id(abo.endpoint), name=name, angelegt=zeile["angelegt"] if zeile else jetzt,
                      zuletzt=zeile["zuletzt"] if zeile else None)

    async def geraete(self, konto: str) -> list[Geraet]:
        await self._bereit()
        zeilen = await self.db.zeilen("SELECT endpunkt, geraet, angelegt, zuletzt FROM appkern_push_abos WHERE konto = ? "
                                      "ORDER BY angelegt", (konto,))
        return [Geraet(id=geraet_id(z["endpunkt"]), name=z["geraet"], angelegt=z["angelegt"], zuletzt=z["zuletzt"])
                for z in zeilen]

    async def entfernen(self, konto: str, *, endpunkt: str | None = None, geraet: str | None = None) -> bool:
        """Ein Abo der Person entfernen, über seinen Endpunkt (das Gerät selbst) oder die Kennung (aus der Liste)."""
        await self._bereit()
        for z in await self.db.zeilen("SELECT endpunkt FROM appkern_push_abos WHERE konto = ?", (konto,)):
            if z["endpunkt"] == endpunkt or geraet_id(z["endpunkt"]) == geraet:
                await self.db.ausfuehren("DELETE FROM appkern_push_abos WHERE endpunkt = ?", (z["endpunkt"],))
                return True
        return False

    async def senden(self, konto: str, m: Mitteilung) -> Versand:
        """An alle Geräte der Person. Scheitert nie: Fehler stehen im Ergebnis und im Protokoll der App."""
        await self._bereit()
        abos = await self.db.zeilen("SELECT endpunkt, p256dh, auth FROM appkern_push_abos WHERE konto = ?", (konto,))
        ergebnis = Versand()
        if not abos:
            return ergebnis
        nutzlast = json.dumps(m.model_dump(exclude_none=True), ensure_ascii=False).encode()
        schluessel = await self._schluessel()
        async with httpx.AsyncClient(transport=self.transport, timeout=ZEITGRENZE_S) as client:
            for a in abos:
                stand = await self._einmal(client, schluessel, a, nutzlast, m)
                if stand == "ok":
                    ergebnis.zugestellt += 1
                    await self.db.ausfuehren("UPDATE appkern_push_abos SET zuletzt = ? WHERE endpunkt = ?",
                                             (self.jetzt(), a["endpunkt"]))
                elif stand == "weg":
                    ergebnis.entfernt += 1
                    await self.db.ausfuehren("DELETE FROM appkern_push_abos WHERE endpunkt = ?", (a["endpunkt"],))
                else:
                    ergebnis.fehler += 1
        return ergebnis

    async def _einmal(self, client: httpx.AsyncClient, schluessel: Vapid02, abo: dict, nutzlast: bytes,
                      m: Mitteilung) -> str:
        teile = urlsplit(abo["endpunkt"])
        unterschrift = schluessel.sign({"sub": self.absender(), "aud": f"{teile.scheme}://{teile.netloc}",
                                        "exp": int(time.time()) + UNTERSCHRIFT_S})
        kopf = {**unterschrift, "TTL": str(m.ttl), "Content-Encoding": "aes128gcm",
                "Content-Type": "application/octet-stream", "Urgency": "high" if m.dringend else "normal"}
        if m.tag:
            kopf["Topic"] = _thema(m.tag)
        try:
            antwort = await client.post(abo["endpunkt"], content=verschluesseln(nutzlast, abo["p256dh"], abo["auth"]),
                                        headers=kopf)
        except httpx.HTTPError as f:
            log.warning("Mitteilung an %s nicht gesendet: %s", teile.netloc, f)
            return "fehler"
        if antwort.status_code in (404, 410):
            return "weg"
        if antwort.status_code >= 300:
            log.warning("Mitteilung an %s abgelehnt: %s %s", teile.netloc, antwort.status_code, antwort.text[:200])
            return "fehler"
        return "ok"
