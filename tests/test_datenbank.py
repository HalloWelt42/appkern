"""Datenbank: Lesen über eigene Verbindungen neben der schreibenden (WAL). Eine lange Schreibtransaktion hält kein Lesen
auf, Lesungen laufen nebeneinander (höchstens so viele wie Leseverbindungen), ein aufgegebenes Lesen wird in SQLite
abgebrochen und belegt seine Verbindung nicht weiter, Schreiben über `zeile` scheitert laut, im Speicher geht alles
über eine Verbindung."""

import asyncio
import sqlite3
import threading
import time
from pathlib import Path

import pytest

from appkern.datenbank import Datenbank

ENDLOS = "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT count(*) AS n FROM r"


async def offen(pfad: Path, **art) -> Datenbank:
    db = await Datenbank(pfad, **art).oeffnen()
    await db.einrichten("probe", ["CREATE TABLE t (n INTEGER NOT NULL)"])
    await db.ausfuehren("INSERT INTO t (n) VALUES (1)")
    assert await db.zeile("SELECT count(*) AS n FROM t") == {"n": 1}      # warm: Fäden und Schema geladen
    return db


def warten_lernen(db: Datenbank) -> None:
    """Eine Abfrage, die wartet (`warte(sekunden)`), auf jeder Leseverbindung; time.sleep gibt den Faden frei."""
    for v in db._lesende:
        v.create_function("warte", 1, lambda s: time.sleep(s) or 1)


async def test_lange_schreibtransaktion_haelt_lesen_nicht_auf(tmp_path: Path):
    db = await offen(tmp_path / "d.sqlite")
    begonnen = threading.Event()

    def lang(v: sqlite3.Connection) -> bool:
        v.execute("INSERT INTO t (n) VALUES (2)")
        begonnen.set()
        time.sleep(1.0)
        return True

    schreiben = asyncio.create_task(db.transaktion(lang))
    await asyncio.to_thread(begonnen.wait, 5)
    beginn = time.perf_counter()
    stand = await db.zeile("SELECT count(*) AS n FROM t")
    dauer = time.perf_counter() - beginn
    assert stand == {"n": 1}                     # der zuletzt bestätigte Stand, ohne die laufende Transaktion
    assert dauer < 0.1, f"Lesen wartete {dauer:.3f} s auf die Schreibtransaktion"
    assert not schreiben.done()
    assert await schreiben
    assert await db.zeile("SELECT count(*) AS n FROM t") == {"n": 2}     # nach dem Bestätigen sofort sichtbar
    await db.schliessen()


async def test_lesungen_laufen_nebeneinander_bis_zur_zahl_der_leser(tmp_path: Path):
    db = await offen(tmp_path / "d.sqlite", leser=2)
    warten_lernen(db)
    beginn = time.perf_counter()
    ergebnisse = await asyncio.gather(*(db.zeile("SELECT warte(0.4) AS w") for _ in range(4)))
    dauer = time.perf_counter() - beginn
    assert ergebnisse == [{"w": 1}] * 4
    assert 0.75 < dauer < 1.4, f"4 Lesungen mit 2 Lesern dauerten {dauer:.2f} s (erwartet etwa 0,8 s)"
    viele = await asyncio.gather(*(db.zeilen("SELECT n FROM t WHERE n = ?", (1,)) for _ in range(50)))
    assert viele == [[{"n": 1}]] * 50 and len(db._frei) == 2          # jede Verbindung ist wieder frei
    await db.schliessen()


async def test_langes_lesen_haelt_schreiben_und_lesen_nicht_auf(tmp_path: Path):
    db = await offen(tmp_path / "d.sqlite")
    warten_lernen(db)
    lang = asyncio.create_task(db.zeile("SELECT warte(1.0) AS w"))
    await asyncio.sleep(0.05)
    beginn = time.perf_counter()
    assert await db.ausfuehren("INSERT INTO t (n) VALUES (3)") == 1
    assert await db.zeile("SELECT max(n) AS n FROM t") == {"n": 3}
    assert time.perf_counter() - beginn < 0.2 and not lang.done()
    assert await lang == {"w": 1}
    await db.schliessen()


async def test_aufgegebenes_lesen_wird_abgebrochen_und_gibt_die_verbindung_frei(tmp_path: Path):
    db = await offen(tmp_path / "d.sqlite", leser=1)
    endlos = asyncio.create_task(db.zeile(ENDLOS))
    await asyncio.sleep(0.2)
    endlos.cancel()
    with pytest.raises(asyncio.CancelledError):
        await endlos
    assert await asyncio.wait_for(db.zeile("SELECT count(*) AS n FROM t"), 5) == {"n": 1}
    # beim Schließen wird laufendes Lesen ebenso abgebrochen, statt das Beenden der App aufzuhalten
    noch = asyncio.create_task(db.zeile(ENDLOS))
    await asyncio.sleep(0.2)
    await asyncio.wait_for(db.schliessen(), 5)
    with pytest.raises(sqlite3.OperationalError):
        await noch
    with pytest.raises(RuntimeError):
        await db.zeile("SELECT 1")


async def test_schreiben_ueber_zeile_scheitert_laut(tmp_path: Path):
    db = await offen(tmp_path / "d.sqlite")
    with pytest.raises(sqlite3.OperationalError):
        await db.zeile("INSERT INTO t (n) VALUES (9) RETURNING n")
    assert await db.zeile("SELECT count(*) AS n FROM t") == {"n": 1}
    await db.schliessen()


async def test_im_speicher_eine_verbindung_fuer_alles():
    async with Datenbank(":memory:") as db:
        await db.einrichten("probe", ["CREATE TABLE t (n INTEGER NOT NULL)"])
        assert db._lesende == []
        await db.ausfuehren("INSERT INTO t (n) VALUES (1)")
        assert await asyncio.gather(db.zeile("SELECT n FROM t"), db.zeilen("SELECT n FROM t")) == [{"n": 1}, [{"n": 1}]]
        assert await db.transaktion(lambda v: v.execute("SELECT count(*) FROM t").fetchone()[0]) == 1


async def test_wieder_oeffnen_nach_dem_schliessen(tmp_path: Path):
    db = await offen(tmp_path / "d.sqlite", leser=2)
    await db.schliessen()
    await db.oeffnen()
    assert await asyncio.gather(*(db.zeile("SELECT count(*) AS n FROM t") for _ in range(5))) == [{"n": 1}] * 5
    await db.schliessen()
