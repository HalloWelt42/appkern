"""Geduldig: ein Aufruf über die Leitstelle, der wiederholt wird, solange sie sagt, dass es gerade nicht geht.

Gerade nicht heißt: Halt oder Wartung (503), Dienst weg oder noch nicht gemeldet (503, etwa nach einem Neustart der
Leitstelle oder des Maschinenraums), Leitstelle nicht erreichbar. Gewartet wird so lange, wie sie es sagt
(Retry-After), sonst `WARTEN_S`, höchstens `geduld_s` lang; dann gilt der Fehler. Alles andere (abgelehnt, gesperrt,
unbekannt, Fehler des Dienstes) geht sofort an den Aufrufer. `aufruf` ist eine Fabrik: jeder Versuch baut seine
Anfrage neu (hochgeladene Dateien werden neu geöffnet). Apps mit Aufträgen geben `melden` (der Mensch sieht, worauf
gewartet wird) und `pruefen` (Abbrechen geht auch während des Wartens).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from .fehler import DienstWeg, Halt, NichtErreichbar

T = TypeVar("T")
log = logging.getLogger("appkern.leitstelle")
WARTEN_BEI: tuple[type[Exception], ...] = (Halt, DienstWeg, NichtErreichbar)
WARTEN_S = 30
GEDULD_S = 30 * 60


async def geduldig(aufruf: Callable[[], Awaitable[T]], *, was: str, geduld_s: float = GEDULD_S,
                   warten_bei: tuple[type[Exception], ...] = WARTEN_BEI,
                   melden: Callable[[str], Awaitable[None]] | None = None,
                   pruefen: Callable[[], Awaitable[None]] | None = None) -> T:
    beginn = time.monotonic()
    while True:
        try:
            return await aufruf()
        except warten_bei as f:
            if time.monotonic() - beginn > geduld_s:
                raise
            pause = getattr(f, "nochmal_in", None) or WARTEN_S
            text = f"{was}: {getattr(f, 'meldung', f)}; neuer Versuch in {pause} s"
            log.info(text)
            if melden is not None:
                await melden(text)
            for _ in range(int(pause)):
                if pruefen is not None:
                    await pruefen()
                await asyncio.sleep(1)
