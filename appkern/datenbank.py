"""Die eigene Datenbank einer App: eine SQLite-Datei für Verzeichnis, Zustand und Index (Inhalte liegen in der
Kellerwolke). Ohne Server, ohne zusätzliches Paket.

Alle Zugriffe laufen nacheinander über eine Verbindung in einem Faden; die Ereignisschleife wartet nie auf die
Platte. Jeder Baustein des Appkerns (Aufträge, Protokoll, Einstellungen) und die App selbst bringen ihr Schema als
Stufen mit; `einrichten` spielt nur die noch fehlenden ein und merkt sich den Stand je Baustein.
"""

from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


class Datenbank:
    def __init__(self, pfad: Path | str) -> None:
        """`pfad` einer Datei (der Ordner entsteht bei Bedarf) oder ":memory:" für Tests."""
        self.pfad = str(pfad)
        self._verbindung: sqlite3.Connection | None = None
        self._sperre = asyncio.Lock()

    def __repr__(self) -> str:
        return f"Datenbank({self.pfad!r})"

    async def oeffnen(self) -> Datenbank:
        if self._verbindung is None:
            self._verbindung = await asyncio.to_thread(self._verbinden)
        return self

    def _verbinden(self) -> sqlite3.Connection:
        if self.pfad != ":memory:":
            Path(self.pfad).parent.mkdir(parents=True, exist_ok=True)
        v = sqlite3.connect(self.pfad, check_same_thread=False, isolation_level=None)
        v.row_factory = sqlite3.Row
        v.execute("PRAGMA journal_mode=WAL")
        v.execute("PRAGMA foreign_keys=ON")
        v.execute("PRAGMA busy_timeout=5000")
        v.execute("CREATE TABLE IF NOT EXISTS appkern_schema (baustein TEXT PRIMARY KEY, stufe INTEGER NOT NULL)")
        return v

    async def schliessen(self) -> None:
        async with self._sperre:
            if self._verbindung is not None:
                await asyncio.to_thread(self._verbindung.close)
                self._verbindung = None

    async def __aenter__(self) -> Datenbank:
        return await self.oeffnen()

    async def __aexit__(self, *_: object) -> None:
        await self.schliessen()

    async def _im_faden(self, arbeit: Callable[[sqlite3.Connection], T]) -> T:
        if self._verbindung is None:
            raise RuntimeError("Datenbank ist nicht geöffnet")
        verbindung = self._verbindung
        async with self._sperre:
            return await asyncio.to_thread(arbeit, verbindung)

    async def einrichten(self, baustein: str, stufen: Sequence[str]) -> int:
        """Spielt die Stufen ab der gemerkten ein (jede in einer Transaktion). Liefert den neuen Stand."""

        def arbeit(v: sqlite3.Connection) -> int:
            zeile = v.execute("SELECT stufe FROM appkern_schema WHERE baustein=?", (baustein,)).fetchone()
            stand = zeile["stufe"] if zeile else 0
            for nummer, sql in enumerate(stufen[stand:], start=stand + 1):
                v.execute("BEGIN IMMEDIATE")
                try:
                    for satz in _saetze(sql):
                        v.execute(satz)
                    v.execute("INSERT INTO appkern_schema (baustein, stufe) VALUES (?, ?) "
                              "ON CONFLICT(baustein) DO UPDATE SET stufe=excluded.stufe", (baustein, nummer))
                    v.execute("COMMIT")
                except BaseException:
                    v.execute("ROLLBACK")
                    raise
            return max(stand, len(stufen))

        return await self._im_faden(arbeit)

    async def ausfuehren(self, sql: str, werte: Sequence[Any] = ()) -> int:
        """Ein schreibender Satz; liefert die Zahl betroffener Zeilen."""
        return await self._im_faden(lambda v: v.execute(sql, werte).rowcount)

    async def zeile(self, sql: str, werte: Sequence[Any] = ()) -> dict[str, Any] | None:
        def arbeit(v: sqlite3.Connection) -> dict[str, Any] | None:
            z = v.execute(sql, werte).fetchone()
            return dict(z) if z else None

        return await self._im_faden(arbeit)

    async def zeilen(self, sql: str, werte: Sequence[Any] = ()) -> list[dict[str, Any]]:
        return await self._im_faden(lambda v: [dict(z) for z in v.execute(sql, werte).fetchall()])

    async def transaktion(self, arbeit: Callable[[sqlite3.Connection], T]) -> T:
        """`arbeit` läuft im Faden in einer Transaktion (alles oder nichts) und bekommt die rohe Verbindung."""

        def huelle(v: sqlite3.Connection) -> T:
            v.execute("BEGIN IMMEDIATE")
            try:
                ergebnis = arbeit(v)
                v.execute("COMMIT")
                return ergebnis
            except BaseException:
                v.execute("ROLLBACK")
                raise

        return await self._im_faden(huelle)


def _saetze(sql: str) -> list[str]:
    """Ein Skript in einzelne Sätze (executescript würde die Transaktion beenden)."""
    saetze, puffer = [], ""
    for zeile in sql.splitlines(keepends=True):
        puffer += zeile
        if sqlite3.complete_statement(puffer):
            if puffer.strip():
                saetze.append(puffer.strip())
            puffer = ""
    if puffer.strip():
        saetze.append(puffer.strip())
    return saetze
