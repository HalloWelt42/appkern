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
                                                                     heap_frei=100 * MB, eigene_seiten=0),
                          zurueckgeben=lambda: False)
    caplog.set_level(logging.WARNING)
    for _ in range(5):
        await wache.blick()
    zeilen = await db.zeilen("SELECT text, daten FROM protokoll WHERE ereignis = 'app.speicher' ORDER BY zeit")
    await db.schliessen()
    # unter 1 GB still; 1,1 GB meldet, 1,2 GB nicht (gleiche Stufe), 1,6 GB über 1,5 GB wieder, das Sinken nie
    assert [json.loads(z["daten"])["gesamt_mb"] for z in zeilen] == [1124, 1624]
    assert zeilen[0]["text"].startswith("Speicher gewachsen auf 1,1 GB") and "frei gehalten 0,1 GB" in zeilen[0]["text"]
    assert sum("Speicher gewachsen" in r.getMessage() for r in caplog.records) == 2


async def test_wache_gibt_frei_gehaltenes_zurueck(tmp_path: Path):
    """Wie im Fundus: nach einer Spitze hält der Heap viel frei. Die Wache gibt es zurück, misst danach und zählt die
    Stufen von dort; erneut erst, wenn der Prozess seither wieder um so viel gewachsen ist (der Speicherverwalter zählt
    Zurückgegebenes weiter als frei)."""
    db = await Datenbank(tmp_path / "probe.sqlite").oeffnen()
    protokoll = Protokoll(db)
    await protokoll.starten()
    bilder = iter([
        Speicherbild(arbeitsspeicher=5 * GB + 700 * MB, ausgelagert=0, heap_belegt=200 * MB, heap_frei=5 * GB + 500 * MB),
        Speicherbild(arbeitsspeicher=400 * MB, ausgelagert=0, heap_belegt=200 * MB, heap_frei=5 * GB + 500 * MB),   # danach
        Speicherbild(arbeitsspeicher=500 * MB, ausgelagert=0, heap_belegt=300 * MB, heap_frei=5 * GB + 400 * MB),   # kaum gewachsen
        Speicherbild(arbeitsspeicher=900 * MB, ausgelagert=0, heap_belegt=300 * MB, heap_frei=5 * GB + 500 * MB),   # 500 MB mehr
        Speicherbild(arbeitsspeicher=450 * MB, ausgelagert=0, heap_belegt=300 * MB, heap_frei=5 * GB + 500 * MB),   # danach
    ])
    rueckgaben = []
    wache = Speicherwache(protokoll, messen=lambda: next(bilder), zurueckgeben=lambda: rueckgaben.append(1) or True)
    assert (await wache.blick()).arbeitsspeicher == 400 * MB
    assert (await wache.blick()).arbeitsspeicher == 500 * MB
    assert (await wache.blick()).arbeitsspeicher == 450 * MB
    zeilen = await db.zeilen("SELECT ereignis, text, daten FROM protokoll ORDER BY zeit")
    await db.schliessen()
    assert len(rueckgaben) == 2
    assert [z["ereignis"] for z in zeilen] == ["app.speicher", "app.speicher_zurueck", "app.speicher_zurueck"]
    assert zeilen[1]["text"].startswith("Speicher zurückgegeben: 5,3 GB weniger, jetzt 0,4 GB")
    assert [json.loads(z["daten"])["zurueck_mb"] for z in zeilen[1:]] == [5420, 450]
    assert wache._naechste == GB                              # nach dem Zurückgeben zählen die Stufen wieder ab 1 GB


async def test_wache_ohne_rueckgabe_bleibt_beim_bild(tmp_path: Path):
    db = await Datenbank(tmp_path / "probe.sqlite").oeffnen()
    protokoll = Protokoll(db)
    await protokoll.starten()
    bild = Speicherbild(arbeitsspeicher=800 * MB, ausgelagert=0, heap_belegt=100 * MB, heap_frei=600 * MB)
    wache = Speicherwache(protokoll, messen=lambda: bild, zurueckgeben=lambda: False)
    assert await wache.blick() is bild
    assert not await db.zeilen("SELECT 1 FROM protokoll")
    await db.schliessen()


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
