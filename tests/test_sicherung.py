"""Regel der Sicherung (appkern.sicherung): regelmäßig nach Abstand, vor dem Ausrollen nach Stunden, nie ohne Änderung,
höchstens so viele Stände wie eingestellt; der Aufruf vor dem Ausrollen liest die Einstellungen der App nur, der
Begleiter im Gerüst nutzt dieselben. Alles in Wegwerf-Ordnern."""

import asyncio
import json
import os
import sqlite3
import time
from pathlib import Path

import pytest
from pydantic import ValidationError

from appkern.app import Geruest, Grundeinstellungen
from appkern.app.sicherung import RegelmaessigeSicherung, ablage_der_app, regel_aus
from appkern.einstellungen import nur_lesen
from appkern.sicherung import VORGABE, Ablage, Regel, regelmaessig, vor_ausrollen
from appkern.sicherung.__main__ import main as sicherung_aufrufen

TAG = 24 * 3600
STUNDE = 3600


def datenbank(pfad: Path, zeilen: int = 1) -> sqlite3.Connection:
    """Eine Datenbank im WAL-Modus wie die der Apps; die Verbindung bleibt offen (die App läuft)."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    v = sqlite3.connect(pfad, isolation_level=None)
    v.execute("PRAGMA journal_mode=WAL")
    v.execute("CREATE TABLE IF NOT EXISTS ding (wert TEXT)")
    for i in range(zeilen):
        v.execute("INSERT INTO ding VALUES (?)", (f"wert {i}",))
    return v


def zurueckdatieren(pfad: Path, um_s: float) -> None:
    """Datenbank und WAL so alt machen, als wären sie vor `um_s` Sekunden zuletzt geschrieben worden."""
    for p in (pfad, pfad.with_name(pfad.name + "-wal")):
        if p.exists():
            alt = time.time() - um_s
            os.utime(p, (alt, alt))


def sicherung_von_frueher(ordner: Path, kennung: str, alter_s: float) -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    zeit = time.time() - alter_s
    p = ordner / f"{kennung}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(zeit))}.sqlite"
    p.write_bytes(b"alt")
    os.utime(p, (zeit, zeit))
    return p


@pytest.fixture
def ablage(tmp_path):
    return Ablage(tmp_path / "daten" / "probe.sqlite", tmp_path / "sicherungen", "probe")


def test_erste_sicherung_ist_eine_stimmige_kopie_mit_dem_beginn_als_aenderungszeit(ablage):
    v = datenbank(ablage.datenbank, zeilen=3)
    beginn = time.time()
    e = regelmaessig(ablage, VORGABE, beginn)
    assert e.angelegt and e.grund == "noch keine Sicherung" and e.staende == 1
    kopie = ablage.ordner / e.angelegt
    assert kopie.stat().st_mtime == pytest.approx(beginn, abs=1e-3)
    assert sqlite3.connect(kopie).execute("SELECT count(*) FROM ding").fetchone()[0] == 3   # auch was nur im WAL stand
    assert not list(ablage.ordner.glob(".*")), "keine Teildatei bleibt liegen"
    v.close()


def test_regelmaessig_erst_nach_dem_abstand_und_nur_mit_aenderung(ablage):
    v = datenbank(ablage.datenbank)
    zurueckdatieren(ablage.datenbank, 10 * TAG)
    sicherung_von_frueher(ablage.ordner, "probe", 6 * TAG)
    e = regelmaessig(ablage, VORGABE, time.time())
    assert e.angelegt is None and "6 Tage alt" in e.grund

    juengste = sicherung_von_frueher(ablage.ordner, "probe", 8 * TAG)
    ablage.ordner.joinpath(ablage.staende()[0].name).unlink()      # nur noch die acht Tage alte
    assert ablage.staende() == [juengste]
    e = regelmaessig(ablage, VORGABE, time.time())
    assert e.angelegt is None and e.grund == "die Datenbank ist seit der jüngsten unverändert"

    v.execute("INSERT INTO ding VALUES ('neu')")                    # die App schreibt (ins WAL)
    e = regelmaessig(ablage, VORGABE, time.time())
    assert e.angelegt and e.staende == 2
    v.close()


def test_vor_dem_ausrollen_nur_ab_der_eingestellten_stundenzahl(ablage):
    v = datenbank(ablage.datenbank)
    sicherung_von_frueher(ablage.ordner, "probe", 23 * STUNDE)
    e = vor_ausrollen(ablage, VORGABE, time.time())
    assert e.angelegt is None and "23 Stunden alt" in e.grund
    e = vor_ausrollen(ablage, Regel(abstand_tage=7, vor_ausrollen_ab_stunden=0, behalten=3), time.time())
    assert e.angelegt, "0 Stunden: vor jedem Ausrollen, sofern geändert"
    v.close()


def test_hoechstens_behalten_auch_ohne_neue_und_nur_das_eigene_muster(ablage):
    v = datenbank(ablage.datenbank)
    zurueckdatieren(ablage.datenbank, 30 * TAG)
    alte = [sicherung_von_frueher(ablage.ordner, "probe", (20 - i) * TAG) for i in range(10)]
    fremd = [ablage.ordner / "nachts-20261001.sqlite", ablage.ordner / "andere-20261001-030000.sqlite",
             ablage.ordner / "probe-liesmich.txt"]
    for f in fremd:
        f.write_text("fremd")
    frische_teil = ablage.ordner / ".probe-20261027-120000.sqlite.teil"
    frische_teil.write_text("läuft gerade")
    verwaiste_teil = ablage.ordner / ".probe-20261001-120000.sqlite.teil"
    verwaiste_teil.write_text("abgebrochen")
    os.utime(verwaiste_teil, (time.time() - 2 * TAG,) * 2)

    e = regelmaessig(ablage, VORGABE, time.time())
    assert e.angelegt is None and e.grund == "die Datenbank ist seit der jüngsten unverändert"
    assert ablage.staende() == alte[-3:][::-1]
    assert e.staende == 3 and len(e.entfernt) == 8
    assert all(f.exists() for f in fremd) and frische_teil.exists() and not verwaiste_teil.exists()
    v.close()


def test_ohne_datenbank_keine_sicherung(ablage):
    e = vor_ausrollen(ablage, VORGABE, time.time())
    assert e.angelegt is None and e.grund == "noch keine Datenbank" and not ablage.ordner.exists()


def test_eine_gescheiterte_kopie_hinterlaesst_nichts(ablage, monkeypatch):
    v = datenbank(ablage.datenbank)

    def kaputt(quelle, ziel):
        Path(ziel).write_text("halb")
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr("appkern.sicherung.regel.kopieren", kaputt)
    with pytest.raises(sqlite3.OperationalError):
        regelmaessig(ablage, VORGABE, time.time())
    assert list(ablage.ordner.iterdir()) == []
    v.close()


def test_werte_aus_den_einstellungen_der_app_gespeichert_vor_umgebung_vor_vorgabe(tmp_path):
    pfad = tmp_path / "probe.sqlite"
    assert regel_aus(nur_lesen(pfad, Grundeinstellungen, umgebung_praefix="PROBE_", umgebung={})) == VORGABE
    v = datenbank(pfad)
    v.execute("CREATE TABLE einstellung (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL, geaendert_am TEXT NOT NULL)")
    v.execute("INSERT INTO einstellung VALUES ('sicherung_behalten', ?, 'x')", (json.dumps(5),))
    v.execute("INSERT INTO einstellung VALUES ('fremdes_feld_der_app', '\"egal\"', 'x')")
    umgebung = {"PROBE_SICHERUNG_BEHALTEN": "9", "PROBE_SICHERUNG_ABSTAND_TAGE": "14"}
    regel = regel_aus(nur_lesen(pfad, Grundeinstellungen, umgebung_praefix="PROBE_", umgebung=umgebung))
    assert regel == Regel(abstand_tage=14, vor_ausrollen_ab_stunden=24, behalten=5)
    with pytest.raises(ValidationError):
        nur_lesen(pfad, Grundeinstellungen, umgebung_praefix="PROBE_", umgebung={"PROBE_SICHERUNG_ABSTAND_TAGE": "0"})
    v.close()


def test_aufruf_vor_dem_ausrollen_schreibt_nie_in_die_datenbank(tmp_path, monkeypatch, capsys):
    pfad = tmp_path / "daten" / "probe.sqlite"
    v = datenbank(pfad)
    v.close()                                       # die App läuft nicht: nichts hält die Datei offen
    vorher = pfad.read_bytes()
    monkeypatch.setenv("PROBE_SICHERUNG_BEHALTEN", "1")
    ordner = tmp_path / "sicherungen"
    for alter in (3 * TAG, 2 * TAG):
        sicherung_von_frueher(ordner, "probe", alter)
    rueck = sicherung_aufrufen(["vor-ausrollen", "--kennung", "probe", "--datenbank", str(pfad), "--ordner", str(ordner)])
    zeile = capsys.readouterr().out
    assert rueck == 0 and zeile.startswith("gesichert: probe-") and "1 Stand im Ordner" in zeile
    assert len(list(ordner.glob("probe-*.sqlite"))) == 1
    assert pfad.read_bytes() == vorher
    con = sqlite3.connect(pfad)
    assert con.execute("SELECT name FROM sqlite_master WHERE name IN ('einstellung', 'appkern_schema')").fetchall() == []
    con.close()

    rueck = sicherung_aufrufen(["vor-ausrollen", "--kennung", "probe", "--datenbank", str(pfad), "--ordner", str(ordner)])
    assert rueck == 0 and "keine neue Sicherung" in capsys.readouterr().out


def test_aufruf_meldet_fehler_mit_rueckgabe_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PROBE_SICHERUNG_BEHALTEN", "0")
    rueck = sicherung_aufrufen(["vor-ausrollen", "--kennung", "probe", "--datenbank", str(tmp_path / "x.sqlite"),
                                "--ordner", str(tmp_path / "s")])
    assert rueck == 1 and "Sicherung gescheitert" in capsys.readouterr().err


async def test_begleiter_schaut_im_takt_und_nimmt_geaenderte_werte_sofort(tmp_path):
    ablage = ablage_der_app(tmp_path / "daten", "probe")
    assert ablage.ordner == tmp_path / "sicherungen"
    v = datenbank(ablage.datenbank)
    regel = {"wert": VORGABE}
    begleiter = RegelmaessigeSicherung(ablage, lambda: regel["wert"], takt_s=0.05)
    await begleiter.starten()
    assert ablage.staende() == [], "der erste Blick kommt erst nach einem Takt"
    for _ in range(100):
        if ablage.staende():
            break
        await asyncio.sleep(0.02)
    assert len(ablage.staende()) == 1
    for alter in (9 * TAG, 8 * TAG):
        sicherung_von_frueher(ablage.ordner, "probe", alter)
    regel["wert"] = Regel(abstand_tage=7, vor_ausrollen_ab_stunden=24, behalten=1)
    for _ in range(100):
        if len(ablage.staende()) == 1:
            break
        await asyncio.sleep(0.02)
    await begleiter.stoppen()
    assert len(ablage.staende()) == 1
    v.close()


async def test_das_geruest_bringt_die_sicherung_mit(tmp_path):
    geruest = Geruest(name="Probe", kennung="probe", rolle="probt", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=Grundeinstellungen)
    assert geruest.sicherung in geruest._begleiter
    assert geruest.sicherung.ablage.datenbank == Path(geruest.db.pfad)
    assert geruest.sicherung.ablage.ordner == tmp_path / "sicherungen"
    await geruest.starten()
    try:
        await geruest.einstellungen.aendern({"sicherung_behalten": 2})
        assert geruest.sicherung.regel().behalten == 2
        felder = {f.name: f for f in geruest.einstellungen.felder()}
        assert felder["sicherung_abstand_tage"].gruppe == "Sicherung" and felder["sicherung_abstand_tage"].vorgabe == 7
    finally:
        await geruest.stoppen()
    eigen = Geruest(name="Probe", kennung="probe", rolle="probt", fassung="0.1.0", daten=tmp_path / "d2",
                    einstellungen=Grundeinstellungen, sicherungen=tmp_path / "anderswo")
    assert eigen.sicherung.ablage.ordner == tmp_path / "anderswo"
