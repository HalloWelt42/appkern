"""Die eigene Datenbank einer App: eine SQLite-Datei für Verzeichnis, Zustand und Index (Inhalte liegen in der
Kellerwolke). Ohne Server, ohne zusätzliches Paket.

Geschrieben wird nacheinander über eine Verbindung (`ausfuehren`, `transaktion`, `einrichten`), gelesen (`zeile`,
`zeilen`) über einen kleinen Vorrat eigener Verbindungen, die nur lesen dürfen. Im WAL-Modus sieht jedes Lesen den
zuletzt bestätigten Stand: ein langes Lesen hält weder anderes Lesen noch das Schreiben auf, und eine laufende
Schreibtransaktion hält kein Lesen auf (gemessen in Fundus: vorher wartete jede Seite auf die langsamste Abfrage).
Jede Verbindung arbeitet in einem Faden, immer nur einer zugleich; die Ereignisschleife wartet nie auf die Platte. Wer
nicht mehr wartet (abgebrochene Anfrage), bricht sein Lesen in SQLite ab, statt die Verbindung weiter zu belegen.

Eine Datenbank im Speicher (":memory:", für Tests) lässt sich nicht teilen: dort läuft alles über die eine Verbindung,
ebenso, wenn das Dateisystem kein WAL erlaubt.

Jeder Baustein des Appkerns (Aufträge, Protokoll, Einstellungen) und die App selbst bringen ihr Schema als Stufen mit;
`einrichten` spielt nur die noch fehlenden ein und merkt sich den Stand je Baustein.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")
logger = logging.getLogger("appkern.datenbank")

LESER = 4            # Leseverbindungen einer Datei, also so viele Lesungen zugleich
WARTEN_MS = 5000     # so lange wartet eine Verbindung, wenn SQLite gerade sperrt


class Datenbank:
    def __init__(self, pfad: Path | str, *, leser: int = LESER) -> None:
        """`pfad` einer Datei (der Ordner entsteht bei Bedarf) oder ":memory:" für Tests. `leser`: so viele Lesungen
        laufen gleichzeitig, jede in ihrer eigenen Verbindung (im Speicher gibt es nur die eine)."""
        self.pfad = str(pfad)
        self.leser = max(1, leser)
        self._schreiber: sqlite3.Connection | None = None
        self._sperre = asyncio.Lock()                    # eine Schreibarbeit zugleich
        self._lesende: list[sqlite3.Connection] = []     # alle Leseverbindungen
        self._frei: list[sqlite3.Connection] = []        # die gerade niemand nutzt
        self._plaetze = asyncio.Semaphore(0)             # so viele wie frei sind

    def __repr__(self) -> str:
        return f"Datenbank({self.pfad!r})"

    @property
    def im_speicher(self) -> bool:
        return self.pfad in (":memory:", "")

    async def oeffnen(self) -> Datenbank:
        if self._schreiber is None:
            self._schreiber, wal = await asyncio.to_thread(self._verbinden)
            if wal and not self.im_speicher:
                self._lesende = [await asyncio.to_thread(self._lesend_verbinden) for _ in range(self.leser)]
                self._frei = list(self._lesende)
                self._plaetze = asyncio.Semaphore(len(self._lesende))
            elif not self.im_speicher:
                logger.warning("%s: kein WAL möglich; Lesen und Schreiben gehen nacheinander über eine Verbindung", self.pfad)
        return self

    def _verbinden(self) -> tuple[sqlite3.Connection, bool]:
        if not self.im_speicher:
            Path(self.pfad).parent.mkdir(parents=True, exist_ok=True)
        v = sqlite3.connect(self.pfad, check_same_thread=False, isolation_level=None)
        v.row_factory = sqlite3.Row
        modus = v.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        v.execute("PRAGMA foreign_keys=ON")
        v.execute(f"PRAGMA busy_timeout={WARTEN_MS}")
        v.execute("CREATE TABLE IF NOT EXISTS appkern_schema (baustein TEXT PRIMARY KEY, stufe INTEGER NOT NULL)")
        return v, str(modus).lower() == "wal"

    def _lesend_verbinden(self) -> sqlite3.Connection:
        v = sqlite3.connect(self.pfad, check_same_thread=False, isolation_level=None)
        v.row_factory = sqlite3.Row
        v.execute(f"PRAGMA busy_timeout={WARTEN_MS}")
        v.execute("PRAGMA query_only=ON")           # wer hier schreiben will, bekommt einen Fehler statt eines Rennens
        return v

    async def schliessen(self) -> None:
        """Wartet auf die laufende Schreibarbeit, bricht laufendes Lesen ab und schließt alle Verbindungen."""
        async with self._sperre:
            if self._schreiber is None:
                return
            lesende, plaetze = self._lesende, self._plaetze
            for v in lesende:
                if v not in self._frei:
                    v.interrupt()
            for _ in lesende:
                await plaetze.acquire()                 # jedes Lesen ist fertig
            for v in lesende:
                await asyncio.to_thread(v.close)
            await asyncio.to_thread(self._schreiber.close)
            self._schreiber, self._lesende, self._frei = None, [], []
            for _ in lesende:
                plaetze.release()                       # Wartende wecken; sie finden die Datenbank geschlossen

    async def __aenter__(self) -> Datenbank:
        return await self.oeffnen()

    async def __aexit__(self, *_: object) -> None:
        await self.schliessen()

    # --- Fäden ----------------------------------------------------------------------------------------------------

    def _offen(self) -> sqlite3.Connection:
        if self._schreiber is None:
            raise RuntimeError("Datenbank ist nicht geöffnet")
        return self._schreiber

    async def _schreiben(self, arbeit: Callable[[sqlite3.Connection], T]) -> T:
        self._offen()
        await self._sperre.acquire()
        try:
            v = self._offen()
        except RuntimeError:
            self._sperre.release()
            raise
        return await _im_faden(v, arbeit, self._sperre.release, unterbrechen=False)

    async def _lesen(self, arbeit: Callable[[sqlite3.Connection], T]) -> T:
        self._offen()
        if not self._lesende:                           # im Speicher oder ohne WAL
            return await self._schreiben(arbeit)
        plaetze = self._plaetze
        await plaetze.acquire()
        if plaetze is not self._plaetze or not self._frei:
            plaetze.release()
            raise RuntimeError("Datenbank ist nicht geöffnet")
        v = self._frei.pop()

        def zurueck() -> None:
            self._frei.append(v)
            plaetze.release()

        return await _im_faden(v, arbeit, zurueck, unterbrechen=True)

    # --- Für die Bausteine und die App ----------------------------------------------------------------------------

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

        return await self._schreiben(arbeit)

    async def ausfuehren(self, sql: str, werte: Sequence[Any] = ()) -> int:
        """Ein schreibender Satz; liefert die Zahl betroffener Zeilen."""
        return await self._schreiben(lambda v: v.execute(sql, werte).rowcount)

    async def zeile(self, sql: str, werte: Sequence[Any] = ()) -> dict[str, Any] | None:
        """Erste Zeile einer Abfrage, nur lesend (schreiben geht über `ausfuehren` oder `transaktion`)."""

        def arbeit(v: sqlite3.Connection) -> dict[str, Any] | None:
            zeiger = v.execute(sql, werte)
            try:
                z = zeiger.fetchone()
            finally:
                zeiger.close()                          # gibt den Lesestand sofort frei
            return dict(z) if z else None

        return await self._lesen(arbeit)

    async def zeilen(self, sql: str, werte: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """Alle Zeilen einer Abfrage, nur lesend."""
        return await self._lesen(lambda v: [dict(z) for z in v.execute(sql, werte).fetchall()])

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

        return await self._schreiben(huelle)


async def _im_faden(v: sqlite3.Connection, arbeit: Callable[[sqlite3.Connection], T], freigeben: Callable[[], None], *,
                    unterbrechen: bool) -> T:
    """`arbeit` im Faden; die Verbindung wird erst freigegeben, wenn der Faden wirklich fertig ist, auch wenn der
    Aufrufer vorher aufgibt (sonst arbeiteten zwei Fäden auf einer Verbindung). Mit `unterbrechen` bricht ein
    Aufgeben die laufende Abfrage in SQLite ab."""
    zukunft = asyncio.ensure_future(asyncio.to_thread(arbeit, v))

    def fertig(z: asyncio.Future) -> None:
        if not z.cancelled():
            z.exception()                               # gilt als abgeholt, auch wenn niemand mehr wartet
        freigeben()

    zukunft.add_done_callback(fertig)
    try:
        return await asyncio.shield(zukunft)
    except asyncio.CancelledError:
        if unterbrechen and not zukunft.done():
            v.interrupt()
        raise


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
