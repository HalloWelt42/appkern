"""Speicherwache (HELF-209): sie liest Arbeitsspeicher und Auslagerung des Prozesses, unterscheidet im Heap Belegtes
von nur frei Gehaltenem und meldet erst ab der ersten Stufe, dann bei jedem weiteren Schritt einmal."""

import json
import logging
from pathlib import Path

import httpx

from appkern.app import Geruest
from appkern.app.speicher import GB, MB, Speicherbild, Speicherwache, messen, status_lesen
from appkern.datenbank import Datenbank
from appkern.protokoll import Protokoll

from test_geruest import ProbeEinstellungen, Wolke

STATUS = """Name:\tpython3
VmPeak:\t 7000000 kB
VmRSS:\t 4440864 kB
RssAnon:\t 4406656 kB
VmSwap:\t 1033216 kB
Threads:\t14
"""


def test_status_des_prozesses_lesen():
    assert status_lesen(STATUS) == (4440864 * 1024, 1033216 * 1024)
    assert status_lesen("Name:\tx\nVmRSS:\t 100 kB\n") == (100 * 1024, 0)      # ohne Auslagerung
    assert status_lesen("Name:\tx\n") is None


def test_messen_ohne_proc_misst_nichts(tmp_path: Path):
    assert messen(tmp_path / "fehlt") is None
    datei = tmp_path / "status"
    datei.write_text(STATUS)
    bild = messen(datei)
    assert bild is not None and bild.arbeitsspeicher == 4440864 * 1024 and bild.ausgelagert == 1033216 * 1024
    assert (bild.heap_belegt is None) == (bild.heap_frei is None)            # mit glibc beides, sonst keins


def test_zeile_nennt_belegtes_und_frei_gehaltenes():
    bild = Speicherbild(arbeitsspeicher=4 * GB, ausgelagert=GB, heap_belegt=GB // 2, heap_frei=3 * GB, eigene_seiten=GB // 4)
    assert bild.zeile() == ("5,0 GB (4,0 GB im Arbeitsspeicher, 1,0 GB ausgelagert); im Heap belegt 0,5 GB, frei gehalten "
                            "3,0 GB, große Blöcke 0,2 GB")
    assert bild.daten()["heap_frei_mb"] == 3 * 1024
    assert Speicherbild(arbeitsspeicher=GB, ausgelagert=0).zeile() == "1,0 GB (1,0 GB im Arbeitsspeicher, 0,0 GB ausgelagert)"


async def test_wache_meldet_je_stufe_einmal(tmp_path: Path, caplog):
    db = await Datenbank(tmp_path / "probe.sqlite").oeffnen()
    protokoll = Protokoll(db)
    await protokoll.starten()
    werte = iter([GB // 2, GB + 100 * MB, GB + 200 * MB, GB + 600 * MB, GB])
    wache = Speicherwache(protokoll, messen=lambda: Speicherbild(arbeitsspeicher=next(werte), ausgelagert=0, heap_belegt=MB,
                                                                     heap_frei=GB, eigene_seiten=0))
    caplog.set_level(logging.WARNING)
    for _ in range(5):
        await wache.blick()
    zeilen = await db.zeilen("SELECT text, daten FROM protokoll WHERE ereignis = 'app.speicher' ORDER BY zeit")
    await db.schliessen()
    # unter 1 GB still; 1,1 GB meldet, 1,2 GB nicht (gleiche Stufe), 1,6 GB über 1,5 GB wieder, das Sinken nie
    assert [json.loads(z["daten"])["gesamt_mb"] for z in zeilen] == [1124, 1624]
    assert zeilen[0]["text"].startswith("Speicher gewachsen auf 1,1 GB") and "frei gehalten 1,0 GB" in zeilen[0]["text"]
    assert sum("Speicher gewachsen" in r.getMessage() for r in caplog.records) == 2


async def test_wache_ohne_messung_bleibt_still(tmp_path: Path):
    db = await Datenbank(tmp_path / "probe.sqlite").oeffnen()
    protokoll = Protokoll(db)
    await protokoll.starten()
    assert await Speicherwache(protokoll, messen=lambda: None).blick() is None
    assert not await db.zeilen("SELECT 1 FROM protokoll WHERE ereignis = 'app.speicher'")
    await db.schliessen()


async def test_wache_lebt_mit_dem_geruest(tmp_path: Path):
    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=ProbeEinstellungen, transport=httpx.MockTransport(Wolke()))
    await geruest.starten()
    laeuft = geruest.speicherwache._aufgabe is not None and not geruest.speicherwache._aufgabe.done()
    await geruest.stoppen()
    assert laeuft and geruest.speicherwache._aufgabe is None
