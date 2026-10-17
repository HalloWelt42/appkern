"""App-Verzeichnis: wo die Schnittstelle einer anderen App liegt.

Eine eingetragene Adresse (aus den Einstellungen der App) geht vor; sonst fragt das Verzeichnis das Stellwerk dieses
Rechners, das die Apps startet und ihre Ports kennt (Teil `backend`). Die Antwort des Stellwerks gilt `MERKEN_S`
Sekunden. So spricht keine App eine fest verdrahtete Adresse an, und eine App auf einem anderen Rechner trägt man ein.
"""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Literal

import httpx
from pydantic import BaseModel

MERKEN_S = 30.0
BACKEND = "backend"


class AppUnbekannt(LookupError):
    """Weder eingetragen noch im Stellwerk (oder das Stellwerk ist nicht erreichbar)."""


class AppEintrag(BaseModel):
    kennung: str
    name: str
    adresse: str
    quelle: Literal["eingetragen", "stellwerk"]
    laeuft: bool | None = None          # nur aus dem Stellwerk bekannt


class Verzeichnis:
    def __init__(self, *, eingetragen: Mapping[str, str] | None = None,
                 stellwerk: str | None = "http://127.0.0.1:8550", client: httpx.AsyncClient | None = None) -> None:
        self.eingetragen = {k.lower(): v.rstrip("/") for k, v in (eingetragen or {}).items()}
        self.stellwerk = stellwerk.rstrip("/") if stellwerk else None
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(3.0))
        self._eigener_client = client is None
        self._gemerkt: tuple[float, list[AppEintrag]] | None = None

    async def schliessen(self) -> None:
        if self._eigener_client:
            await self._client.aclose()

    def eintragen(self, eingetragen: Mapping[str, str]) -> None:
        """Neue eingetragene Adressen (etwa nach einer Änderung der Einstellungen)."""
        self.eingetragen = {k.lower(): v.rstrip("/") for k, v in eingetragen.items()}

    async def _aus_stellwerk(self) -> list[AppEintrag]:
        if not self.stellwerk:
            return []
        if self._gemerkt and time.monotonic() - self._gemerkt[0] < MERKEN_S:
            return self._gemerkt[1]
        try:
            antwort = await self._client.get(f"{self.stellwerk}/api/stand")
            antwort.raise_for_status()
            apps = antwort.json().get("apps") or []
        except (httpx.HTTPError, ValueError):
            return self._gemerkt[1] if self._gemerkt else []
        eintraege = []
        for app in apps:
            teil = next((t for t in app.get("teile") or [] if t.get("kennung") == BACKEND and t.get("port")), None)
            if teil is None:
                continue
            eintraege.append(AppEintrag(kennung=app["kennung"].lower(), name=app.get("name") or app["kennung"],
                                        adresse=f"http://127.0.0.1:{teil['port']}", quelle="stellwerk",
                                        laeuft=teil.get("zustand") == "laeuft"))
        self._gemerkt = (time.monotonic(), eintraege)
        return eintraege

    async def alle(self) -> list[AppEintrag]:
        gesehen = {k: AppEintrag(kennung=k, name=k, adresse=v, quelle="eingetragen") for k, v in self.eingetragen.items()}
        for e in await self._aus_stellwerk():
            gesehen.setdefault(e.kennung, e)
        return sorted(gesehen.values(), key=lambda e: e.kennung)

    async def adresse(self, app: str) -> str:
        """Basisadresse der Schnittstelle einer App (ohne Schrägstrich am Ende)."""
        kennung = app.lower()
        if kennung in self.eingetragen:
            return self.eingetragen[kennung]
        for e in await self._aus_stellwerk():
            if e.kennung == kennung:
                return e.adresse
        raise AppUnbekannt(f"Die App {app} ist weder eingetragen noch im Stellwerk bekannt")
