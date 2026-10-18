"""Der Tondienst: Protokoll der Tonarbeit über HTTP, beide Seiten an einem Ort.

- `TonDienst` (hier): die Tonarbeit für die Apps, über die Leitstelle (`/v1/dienste/<name>/ton/...`).
- `routen(hier, ablage)` (`gegenseite.py`): die Gegenseite, läuft im Tondienst auf dem Mac (Wirt: Klangwerk, Dienst `ton`).

Jeder Arbeitsschritt ist ein POST mit seinen Dateien und dem Auftrag als JSON; die Antwort nennt Messwerte und die
erzeugten Dateien. Die holt der Aufrufer einmal ab (`GET /ton/ergebnis/<name>`), danach sind sie weg; was niemand
abholt, verfällt nach einer Stunde. Tonfehler (Datei nicht lesbar, übersteuert ...) kommen als 422 mit dem Grundwort
`ton_fehler` und werden beim Aufrufer wieder zum `TonFehler`.
"""

from __future__ import annotations

import contextlib
import mimetypes
import re
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel

from ..leitstelle import Leitstelle, LeitstellenFehler
from ..leitstelle.modelle import Prioritaet
from .arbeit import Aufbereiten, Aufbereitet, Blenden, Datei, Gelegt, Legen, Tonarbeit
from .ton import TonFehler

GRUND = "ton_fehler"
ERGEBNIS = re.compile(r"^[0-9a-f]{32}\.[a-z0-9]{2,5}$")
EINGANG = re.compile(r"^\.[a-z0-9]{2,5}$")
VERFALL_S = 3600.0


def typ(datei: Path) -> str:
    return mimetypes.guess_type(datei.name)[0] or "application/octet-stream"


class TonDienst(Tonarbeit):
    """Tonarbeit über die Leitstelle; `leitstelle` und `name` werden bei jedem Aufruf gefragt (Einstellungen)."""

    def __init__(self, leitstelle: Callable[[], Leitstelle | None], name: Callable[[], str]) -> None:
        self._leitstelle = leitstelle
        self._name = name

    def _dienst(self):
        ls = self._leitstelle()
        if ls is None:
            raise TonFehler("Keine Leitstelle eingerichtet: ohne sie gibt es keine Tonarbeit")
        return ls.dienst(self._name())

    @contextlib.asynccontextmanager
    async def _uebersetzt(self):
        try:
            yield
        except LeitstellenFehler as f:
            if f.grund == GRUND:
                raise TonFehler(f.meldung) from None
            raise

    async def _abholen(self, dateien: Sequence[Datei], ziele: Sequence[Path], titel: str, prioritaet: Prioritaet | None) -> None:
        for d, ziel in zip(dateien, ziele, strict=True):
            ziel.parent.mkdir(parents=True, exist_ok=True)
            await self._dienst().herunterladen(f"/ton/ergebnis/{d.name}", ziel, titel=titel, prioritaet=prioritaet)

    async def _senden(self, pfad: str, dateien: Sequence[tuple[str, Path]], auftrag: BaseModel, titel: str,
                      prioritaet: Prioritaet | None) -> dict:
        with contextlib.ExitStack() as stapel:
            teile = [(feld, (d.name, stapel.enter_context(open(d, "rb")), typ(d))) for feld, d in dateien]
            return await self._dienst().json("POST", pfad, titel=titel, prioritaet=prioritaet,
                                             data={"auftrag": auftrag.model_dump_json()}, files=teile)

    async def aufbereiten(self, quelle: Path, auftrag: Aufbereiten, ziele: Sequence[Path], *, titel: str = "",
                          prioritaet: Prioritaet | None = None) -> Aufbereitet:
        if len(ziele) != len(auftrag.ausgaben):
            raise ValueError(f"{len(auftrag.ausgaben)} Ausgaben, aber {len(ziele)} Ziele")
        async with self._uebersetzt(), self._dienst().gebunden():   # Abholen bei derselben Instanz
            erg = Aufbereitet.model_validate(await self._senden("/ton/aufbereiten", [("datei", quelle)], auftrag, titel, prioritaet))
            await self._abholen(erg.ausgaben, ziele, titel, prioritaet)
        return erg

    async def blenden(self, dateien: Sequence[Path], auftrag: Blenden, ziel: Path, *, titel: str = "",
                      prioritaet: Prioritaet | None = None) -> Datei:
        async with self._uebersetzt(), self._dienst().gebunden():   # Abholen bei derselben Instanz
            d = Datei.model_validate(await self._senden("/ton/blenden", [("dateien", p) for p in dateien], auftrag, titel, prioritaet))
            await self._abholen([d], [ziel], titel, prioritaet)
        return d

    async def legen(self, dateien: Sequence[Path], auftrag: Legen, ziel: Path, *, titel: str = "",
                    prioritaet: Prioritaet | None = None) -> Gelegt:
        async with self._uebersetzt(), self._dienst().gebunden():   # Abholen bei derselben Instanz
            g = Gelegt.model_validate(await self._senden("/ton/legen", [("dateien", p) for p in dateien], auftrag, titel, prioritaet))
            await self._abholen([g.datei], [ziel], titel, prioritaet)
        return g
