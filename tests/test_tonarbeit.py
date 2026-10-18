"""Tonarbeit: Rechnen (numpy), TonHier mit echtem ffmpeg, dasselbe über das Protokoll des Tondienstes (TonDienst gegen
die Routen, über eine Leitstelle im Prozess), Datenarbeit an WAV und Abspielfassungen. Die Tonsignale entstehen hier."""

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import numpy as np
import pytest
from fastapi import FastAPI

from appkern.leitstelle import Leitstelle
from appkern.ton import (
    ABSPIELEN, ARBEIT, HOEREN, Abspielfassungen, Aufbereiten, Ausgabe, Blenden, Lage, LautWahl, Legen, Messen, PausenWahl,
    Stueck, Ton, TonDienst, TonFehler, TonHier, Tonformat, wav,
)
from appkern.ton.gegenseite import routen
from appkern.ton import rechnen

RATE = 24000
S16 = Tonformat(rate=RATE, kanaele=1, kodierung="pcm_s16le")


def sinus(sekunden: float, f: float = 440.0, pegel: float = 0.5, rate: int = RATE) -> np.ndarray:
    t = np.arange(int(sekunden * rate)) / rate
    return (pegel * np.sin(2 * np.pi * f * t)).astype(np.float32)


def stille(sekunden: float, rate: int = RATE) -> np.ndarray:
    return np.zeros(int(sekunden * rate), dtype=np.float32)


async def datei(tmp_path: Path, name: str, werte: np.ndarray, format: Tonformat = S16) -> Path:
    return await Ton().schreiben(werte, RATE, tmp_path / name, format)


# --- Rechnen ---------------------------------------------------------------------------------------------------------

def test_blenden_und_raender():
    a, b = sinus(1.0), sinus(0.5)
    aus = rechnen.blenden([a, b], RATE, 30)
    assert aus.size == a.size + b.size - int(RATE * 0.03)
    glatt = rechnen.raender(np.ones(1000, np.float32), RATE, 5)
    assert glatt[0] == 0.0 and glatt[-1] == 0.0 and glatt[500] == 1.0


def test_laute_spanne_begrenzen_legen():
    w = np.concatenate([stille(0.5), sinus(1.0), stille(0.5)])
    von, bis = rechnen.laute_spanne(w, RATE, -45, 40)
    assert von == pytest.approx(0.46 * RATE, abs=2) and bis == pytest.approx(1.54 * RATE, abs=2)
    assert rechnen.laute_spanne(stille(1.0), RATE, -45, 40) == (0, 0)
    assert rechnen.spitze(rechnen.begrenzen(np.array([0.5, -2.0], np.float32), 0.98)) == pytest.approx(0.98)
    gelegt = rechnen.legen([(sinus(1.0), 2.0)], RATE, mindestens_s=5.0, rand_ms=5)
    assert gelegt.size == 5 * RATE and np.abs(gelegt[: 2 * RATE]).max() == 0.0 and np.abs(gelegt[2 * RATE + 500]) > 0


def test_pegel_stueckweise_wie_am_stueck():
    w = np.concatenate([sinus(1.0, pegel=0.1), sinus(1.0, pegel=0.8)])
    ganz = rechnen.Pegelrechner(RATE, 50)
    ganz.fuettern(w)
    stueckweise = rechnen.Pegelrechner(RATE, 50)
    for teil in np.array_split(w, 7):
        stueckweise.fuettern(teil)
    assert stueckweise.rms == pytest.approx(ganz.rms) and len(ganz.rms) == 40
    assert ganz.rms[5] == pytest.approx(0.1 / np.sqrt(2), rel=0.01) and ganz.spitzen[30] == pytest.approx(0.8, abs=0.01)


# --- TonHier ---------------------------------------------------------------------------------------------------------

async def test_aufbereiten_ausgaben_und_messungen(tmp_path):
    quelle = await datei(tmp_path, "quelle.wav", np.concatenate([stille(0.5), sinus(2.0), stille(1.0), sinus(1.5), stille(0.5)]))
    auftrag = Aufbereiten(
        ausgaben=[Ausgabe(format=HOEREN), Ausgabe(format=ABSPIELEN),
                  Ausgabe(format=S16, beginn_s=0.5, ende_s=2.5, spitze=0.25, blende_ms=10, vorlauf_s=0.1, nachlauf_s=0.2)],
        messen=Messen(pausen=PausenWahl(), wellenform=100, pegel_ms=50, laut=LautWahl()))
    ziele = [tmp_path / "h.wav", tmp_path / "a.wav", tmp_path / "r.wav"]
    erg = await TonHier().aufbereiten(quelle, auftrag, ziele)
    m = erg.messwerte
    assert m.eigenschaften.dauer_s == pytest.approx(5.5, abs=0.01)
    assert [round(p.start, 1) for p in m.pausen] == [0.0, 2.5, 5.0] and len(m.wellenform) == 100
    assert len(m.pegel.rms) == 110 and m.pegel.spitze[20] == pytest.approx(0.5, abs=0.01)
    assert m.laut.von_s == pytest.approx(0.46, abs=0.005) and m.laut.bis_s == pytest.approx(5.04, abs=0.005)
    h, a, r = [await Ton().eigenschaften(z) for z in ziele]
    assert (h.rate, h.kanaele) == (16000, 1) and (a.rate, a.kanaele) == (44100, 1)
    assert erg.ausgaben[2].dauer_s == pytest.approx(2.3, abs=0.001)
    werte = await Ton().lesen(ziele[2], RATE)
    assert np.abs(werte[: int(0.1 * RATE)]).max() == 0.0 and np.abs(werte).max() == pytest.approx(0.25, abs=0.01)


async def test_blenden_und_legen(tmp_path):
    hier = TonHier()
    eins = await datei(tmp_path, "eins.wav", np.concatenate([stille(0.3), sinus(1.0), stille(0.3)]))
    zwei = await datei(tmp_path, "zwei.wav", sinus(0.8, f=660))
    stueck = await hier.blenden([eins, zwei], Blenden(stuecke=[Stueck(datei=0, von_s=0.3, bis_s=1.3), Stueck(datei=1)],
                                                      format=S16), tmp_path / "abschnitt.wav")
    assert stueck.dauer_s == pytest.approx(1.0 + 0.8 - 0.03, abs=0.001)

    laut = await datei(tmp_path, "laut.wav", sinus(2.0, pegel=0.9))
    ziel = tmp_path / "ergebnis.m4a"
    g = await hier.legen([tmp_path / "abschnitt.wav", laut],
                         Legen(lagen=[Lage(datei=0, beginn_s=0.5), Lage(datei=1, beginn_s=1.0, stauchung=2.0)],
                               mindestens_s=6.0, format=Tonformat(rate=48000, kanaele=2, kodierung="aac", bitrate="192k"),
                               endung=".m4a", wellenform=50), ziel)
    assert g.datei.dauer_s == pytest.approx(6.0, abs=0.001) and len(g.wellenform) == 50
    assert g.spitze_vorher > 0.98                    # Überlappung addiert sich, dann wird das Ganze leiser
    e = await Ton().eigenschaften(ziel)
    assert (e.rate, e.kanaele, e.kodierung) == (48000, 2, "aac")
    werte = await Ton().lesen(ziel, RATE)
    assert np.abs(werte[: int(0.4 * RATE)]).max() < 0.01 and np.abs(werte[int(2.4 * RATE):int(5.5 * RATE)]).max() < 0.01


# --- Protokoll: TonDienst gegen die Routen ---------------------------------------------------------------------------

@pytest.fixture
async def tondienst(tmp_path):
    app = FastAPI()
    app.include_router(routen(TonHier(), tmp_path / "ablage"), prefix="/v1/dienste/klangwerk-ton")
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
    ls = Leitstelle("http://leitstelle.test", "probe", "Probe", client=client)
    yield TonDienst(lambda: ls, lambda: "klangwerk-ton"), tmp_path / "ablage"
    await client.aclose()


async def test_ueber_den_dienst_wie_hier(tmp_path, tondienst):
    dienst, ablage = tondienst
    quelle = await datei(tmp_path, "quelle.wav", np.concatenate([stille(0.5), sinus(2.0), stille(0.5)]))
    auftrag = Aufbereiten(ausgaben=[Ausgabe(format=HOEREN)], messen=Messen(pausen=PausenWahl(), laut=LautWahl()))
    ueber = await dienst.aufbereiten(quelle, auftrag, [tmp_path / "ueber.wav"])
    hier = await TonHier().aufbereiten(quelle, auftrag, [tmp_path / "hier.wav"])
    assert ueber.messwerte == hier.messwerte
    assert (tmp_path / "ueber.wav").read_bytes() == (tmp_path / "hier.wav").read_bytes()
    assert not list(ablage.iterdir()), "abgeholt heißt weg"

    d = await dienst.blenden([quelle, quelle], Blenden(stuecke=[Stueck(datei=0), Stueck(datei=1)], format=S16),
                             tmp_path / "doppelt.wav")
    assert d.dauer_s == pytest.approx(6.0 - 0.03, abs=0.001) and wav.dauer(tmp_path / "doppelt.wav") == pytest.approx(d.dauer_s)
    g = await dienst.legen([quelle], Legen(lagen=[Lage(datei=0, beginn_s=1.0)], format=S16, wellenform=20), tmp_path / "g.wav")
    assert g.datei.dauer_s == pytest.approx(4.0, abs=0.001) and len(g.wellenform) == 20
    assert await dienst.dauer(quelle) == pytest.approx(3.0, abs=0.01)


async def test_tonfehler_kommt_als_tonfehler_an(tmp_path, tondienst):
    dienst, _ = tondienst
    kaputt = tmp_path / "kaputt.wav"
    kaputt.write_bytes(b"kein Ton")
    with pytest.raises(TonFehler):
        await dienst.eigenschaften(kaputt)
    quelle = await datei(tmp_path, "q.wav", sinus(1.0))
    with pytest.raises(ValueError):
        await dienst.aufbereiten(quelle, Aufbereiten(ausgaben=[Ausgabe(format=HOEREN)]), [])


# --- Datenarbeit und Abspielfassungen --------------------------------------------------------------------------------

async def test_wav_ausschnitt_ist_bytegenau(tmp_path):
    werte = sinus(2.0)
    quelle = await datei(tmp_path, "q.wav", werte)
    teil = wav.ausschnitt(quelle, 0.5, 1.25, tmp_path / "teil.wav")
    assert wav.dauer(teil) == pytest.approx(0.75)
    gelesen = await Ton().lesen(teil, RATE)
    original = await Ton().lesen(quelle, RATE)
    assert np.array_equal(gelesen, original[int(0.5 * RATE):int(1.25 * RATE)])
    with pytest.raises(TonFehler):
        wav.dauer(await datei(tmp_path, "f.wav", werte, ARBEIT))           # Gleitkomma ist kein PCM für die Bytekopie


async def test_abspielfassungen_ueber_die_tonarbeit(tmp_path):
    quelle = SimpleNamespace(id=uuid4(), name="a.wav", etag="e1")      # die Fassungen brauchen nur Kennung, Name, Stand
    fassungen = Abspielfassungen(tmp_path / "abspielen", lambda: TonHier(), lambda: 1.0)
    roh = await datei(tmp_path, "roh.wav", sinus(1.0))
    p = await fassungen.aus_datei(quelle, roh)
    assert (await Ton().eigenschaften(p)).rate == 44100 and len(await fassungen.wellenform(quelle, None)) == 800
    fertig = await TonHier().wandeln(roh, tmp_path / "fertig.wav", ABSPIELEN)
    p2 = await fassungen.uebernehmen(quelle, fertig, [1, 2, 3])
    assert p2 == p and await fassungen.wellenform(quelle, None) == [1, 2, 3] and not fertig.exists()


async def test_tondienst_fuer_nachgestellte_leitstellen(tmp_path):
    """Der Testbaustein der Apps: eine Weiche schickt nur Anfragen an den Tondienst dorthin, alles andere woandershin."""
    from appkern.testen import Tondienst

    td = Tondienst(tmp_path / "ablage")

    class Weiche(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if td.zustaendig(request):
                return await td.transport.handle_async_request(request)
            return httpx.Response(404, json={"error": {"code": "kein_modell", "message": "nicht nachgestellt"}})

    async with httpx.AsyncClient(transport=Weiche()) as client:
        ls = Leitstelle("http://ls.test", "probe", "Probe", client=client)
        quelle = await datei(tmp_path, "q.wav", sinus(1.0))
        assert await TonDienst(lambda: ls, lambda: "klangwerk-ton").dauer(quelle) == pytest.approx(1.0, abs=0.01)
