"""Die Sicherung im Gerüst: regelmäßig als Begleiter, nach der Regel aus `appkern.sicherung` mit den Einstellungen
der App (Gruppe Sicherung). Dieselben Einstellungen gelten für die Sicherung vor dem Ausrollen
(`python -m appkern.sicherung vor-ausrollen`, aufgerufen vom Ausrollen im Abbild der App).

Der Begleiter schaut alle `TAKT_S` Sekunden, ob eine Sicherung fällig ist; der erste Blick kommt nach einem Takt,
nicht beim Start (ein Start ist meist ein Ausrollen, das eben selbst nach der Regel gesichert hat, und eine App im
Test sichert so nie). Ein Blick ohne Fälligkeit liest nur Änderungszeiten. Ergebnisse stehen im Log, nicht im
Protokoll der App: jeder Eintrag dort wäre selbst eine Änderung der Datenbank.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

from appkern.sicherung import Ablage, Ergebnis, Regel, regelmaessig

from .begleiter import Begleiter
from .einstellungen import Grundeinstellungen

logger = logging.getLogger("appkern.sicherung")

TAKT_S = 600.0
ORDNER = "sicherungen"       # Ordner der Sicherungen neben dem Datenordner (im Container /app/sicherungen)


def regel_aus(stand: Grundeinstellungen) -> Regel:
    """Die Regel aus den Einstellungen einer App."""
    return Regel(abstand_tage=stand.sicherung_abstand_tage, vor_ausrollen_ab_stunden=stand.sicherung_vor_ausrollen_ab_stunden,
                 behalten=stand.sicherung_behalten)


def ablage_der_app(daten: Path, kennung: str, sicherungen: Path | None = None) -> Ablage:
    """Wo die Sicherungen einer App liegen: ihre Datenbank `<daten>/<kennung>.sqlite`, die Kopien in `sicherungen`,
    ohne Angabe im Ordner `sicherungen` neben dem Datenordner (so auch auf dem Pi, wohin das Ausrollen sichert)."""
    return Ablage(Path(daten) / f"{kennung}.sqlite", Path(sicherungen) if sicherungen else Path(daten).parent / ORDNER, kennung)


class RegelmaessigeSicherung(Begleiter):
    def __init__(self, ablage: Ablage, regel: Callable[[], Regel], *, takt_s: float = TAKT_S,
                 jetzt: Callable[[], float] = time.time) -> None:
        """`regel` liefert die Regel bei jedem Blick neu (geänderte Einstellungen gelten sofort); `jetzt` nur für Tests."""
        self.ablage = ablage
        self.regel = regel
        self.takt_s = takt_s
        self.jetzt = jetzt
        self._aufgabe: asyncio.Task[None] | None = None

    async def starten(self) -> None:
        self._aufgabe = asyncio.create_task(self._laufen(), name=f"{self.ablage.kennung}-sicherung")

    async def stoppen(self) -> None:
        if self._aufgabe:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def pruefen(self) -> Ergebnis:
        """Ein Blick: sichern, wenn fällig und geändert; höchstens so viele behalten, wie eingestellt."""
        ergebnis = await asyncio.to_thread(regelmaessig, self.ablage, self.regel(), self.jetzt())
        if ergebnis.angelegt or ergebnis.entfernt:
            logger.info("Sicherung %s: %s", self.ablage.kennung, ergebnis.zeile())
        return ergebnis

    async def _laufen(self) -> None:
        while True:
            await asyncio.sleep(self.takt_s)
            try:
                await self.pruefen()
            except Exception:  # noqa: BLE001 - der nächste Blick versucht es wieder
                logger.exception("Sicherung %s", self.ablage.kennung)
