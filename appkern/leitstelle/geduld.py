"""Geduldig: ein Aufruf über die Leitstelle, der wiederholt wird, solange sie sagt, dass es gerade nicht geht.

Gerade nicht heißt: Halt oder Wartung (503), Dienst weg oder noch nicht gemeldet (503, etwa nach einem Neustart der
Leitstelle oder des Maschinenraums), Leitstelle nicht erreichbar. Gewartet wird so lange, wie sie es sagt
(Retry-After), sonst `WARTEN_S`, höchstens die Geduld lang; dann gilt der Fehler. Die Geduld setzt die App aus ihrer
Einstellung "Geduld bei Ausfall" (`geduld_setzen`); ohne sie gilt `GEDULD_S`.

Schläft der Rechner mit dem Dienst (503 `rechner_schlaeft`), wartet `geduldig` ohne Grenze, bis er wach ist, und meldet
das einmal ("wartet, bis Mac Studio wach ist"); diese Zeit zählt nicht zur Geduld, und nach dem Schlaf beginnt sie neu.
Alles andere (abgelehnt, gesperrt, unbekannt, Fehler des Dienstes) geht sofort an den Aufrufer. `aufruf` ist eine
Fabrik: jeder Versuch baut seine Anfrage neu (hochgeladene Dateien werden neu geöffnet). Apps mit Aufträgen geben
`melden` (der Mensch sieht, worauf gewartet wird; gleiche Meldungen nur einmal) und `pruefen` (Abbrechen geht jede
Sekunde, auch während des Wartens).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .fehler import DienstWeg, Halt, NichtErreichbar, RechnerSchlaeft

T = TypeVar("T")
log = logging.getLogger("appkern.leitstelle")
WARTEN_BEI: tuple[type[Exception], ...] = (Halt, DienstWeg, NichtErreichbar)
WARTEN_S = 30
GEDULD_S = 30 * 60                    # Vorgabe, bis die App ihre Einstellung setzt
_geduld_s: float = GEDULD_S


def geduld_setzen(s: float) -> None:
    """Geduld bei Ausfall für alle Aufrufe dieser App (aus der Einstellung "Geduld bei Ausfall")."""
    global _geduld_s
    _geduld_s = s


def geduld() -> float:
    return _geduld_s


def _wer(f: RechnerSchlaeft) -> str:
    return " oder ".join(f.rechner) if f.rechner else "der Rechner"


async def geduldig(aufruf: Callable[[], Awaitable[T]], *, was: str, geduld_s: float | None = None,
                   warten_bei: tuple[type[Exception], ...] = WARTEN_BEI,
                   melden: Callable[[str], Awaitable[None]] | None = None,
                   pruefen: Callable[[], Awaitable[None]] | None = None,
                   uhr: Callable[[], float] | None = None,
                   schlafen: Callable[[float], Awaitable[None]] | None = None) -> T:
    """`geduld_s` None: die Geduld der App. `uhr` und `schlafen` nur für Tests (Vorgabe: time.monotonic, asyncio.sleep)."""
    jetzt = uhr or time.monotonic
    ruhen = schlafen or asyncio.sleep
    seit: float | None = None         # Beginn der laufenden Wartezeit ohne Schlaf
    zuletzt = ""
    while True:
        try:
            return await aufruf()
        except RechnerSchlaeft as f:
            seit = None                   # der Schlaf zählt nicht zur Geduld; danach beginnt sie neu
            pause = f.nochmal_in or WARTEN_S
            text = f"{was}: wartet, bis {_wer(f)} wach ist"
        except warten_bei as f:
            seit = jetzt() if seit is None else seit
            if jetzt() - seit > (geduld_s if geduld_s is not None else _geduld_s):
                raise
            pause = getattr(f, "nochmal_in", None) or WARTEN_S
            text = f"{was}: {getattr(f, 'meldung', f)}; neuer Versuch in {pause} s"
        if text != zuletzt:
            zuletzt = text
            log.info(text)
            if melden is not None:
                await melden(text)
        for _ in range(int(pause)):
            if pruefen is not None:
                await pruefen()
            await ruhen(1)
