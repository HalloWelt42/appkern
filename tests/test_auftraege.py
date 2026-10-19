"""Aufträge: Einreihen und Abarbeiten mit Phasen und Fortschritt, Ereignisstrom, Abbruch wartend und laufend,
Fehler mit Ursache, Wiederholen mit Zwischenstand, Verhalten nach einem Neustart, Grenze gleichzeitiger Arbeit,
Aufräumen, Schnittstelle mit SSE."""

import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, ValidationError

from appkern.auftraege import Art, AuftragAbgebrochen, AuftragFehler, Auftraege, FalscherZustand, Kontext, Phase, UnbekannteArt
from appkern.auftraege.api import auftrags_router
from appkern.datenbank import Datenbank


class Texte(BaseModel):
    texte: list[str]


async def bis(auftraege: Auftraege, auftrag_id: str, *zustaende: str, sekunden: float = 5.0):
    for _ in range(int(sekunden / 0.01)):
        a = await auftraege.holen(auftrag_id)
        if a.zustand in zustaende:
            return a
        await asyncio.sleep(0.01)
    raise AssertionError(f"{auftrag_id} blieb {a.zustand}")


def arten(freigabe: asyncio.Event | None = None, gestartet: asyncio.Event | None = None):
    async def zaehlen(k: Kontext):
        await k.fortschritt(0.0, "Zählen beginnt", phase="lesen")
        for i, text in enumerate(k.eingabe.texte):
            await k.pruefen()
            await k.fortschritt((i + 1) / len(k.eingabe.texte), f"Text {i + 1}")
        await k.fortschritt(1.0, "Fertig gezählt", phase="schreiben")
        return {"zeichen": sum(len(t) for t in k.eingabe.texte)}

    async def warten(k: Kontext):
        if gestartet:
            gestartet.set()
        while not (freigabe and freigabe.is_set()):
            await k.pruefen()
            await asyncio.sleep(0.01)
        return {"ok": True}

    async def kaputt(k: Kontext):
        raise ValueError()

    class SeiteWeg(AuftragFehler):
        pass

    async def erwartet(k: Kontext):
        try:
            raise KeyError("404")
        except KeyError as f:
            raise SeiteWeg("Die Seite gibt es nicht mehr (404)") from f

    async def abschnitte(k: Kontext):
        fertig = list(k.zwischenstand.get("fertig", []))
        for n in range(len(fertig), 4):
            if n == 2 and not k.zwischenstand.get("zweiter_lauf"):
                await k.merken(zweiter_lauf=True)
                raise RuntimeError("Dienst weg")
            fertig.append(n)
            await k.merken(fertig=fertig)
        return {"abschnitte": fertig}

    return [
        Art("zaehlen", "Zeichen zählen", zaehlen, eingabe=Texte,
            phasen=[Phase(schluessel="lesen", titel="Lesen", symbol="book"), Phase(schluessel="schreiben", titel="Schreiben")]),
        Art("warten", "Warten", warten, nach_neustart="anhalten"),
        Art("warten_fortsetzen", "Warten", warten, nach_neustart="fortsetzen"),
        Art("kaputt", "Kaputt", kaputt),
        Art("erwartet", "Erwartet", erwartet),
        Art("abschnitte", "Abschnitte", abschnitte, fortsetzbar=True),
    ]


@pytest.fixture
async def db(tmp_path: Path):
    async with Datenbank(tmp_path / "app.sqlite") as d:
        yield d


@pytest.fixture
async def dienst(db):
    a = Auftraege(db, arten())
    await a.starten()
    yield a
    await a.stoppen()


async def test_einreihen_abarbeiten_mit_phasen_und_ereignissen(dienst):
    gesehen = []

    async def lauschen():
        async for a in dienst.ereignisse():
            assert a is not None
            gesehen.append((a.zustand, a.phase, a.fortschritt))
            if a.zustand == "fertig":
                return

    lauscher = asyncio.create_task(lauschen())
    await asyncio.sleep(0.02)
    a = await dienst.einreihen("zaehlen", {"texte": ["ab", "cde"]}, titel="Zwei Texte")
    assert a.zustand == "wartet" and a.titel == "Zwei Texte" and [p.schluessel for p in a.phasen] == ["lesen", "schreiben"]
    fertig = await bis(dienst, a.id, "fertig")
    await asyncio.wait_for(lauscher, 5)
    assert fertig.ergebnis == {"zeichen": 5} and fertig.fortschritt == 1.0 and fertig.phase == "schreiben"
    assert fertig.begonnen_am and fertig.beendet_am and fertig.schritt == ""
    assert gesehen[0][0] == "wartet" and ("laeuft", "lesen", 0.0) in gesehen and gesehen[-1][0] == "fertig"


async def test_eingabe_wird_geprueft(dienst):
    with pytest.raises(Exception):
        await dienst.einreihen("zaehlen", {"texte": "kein Liste"})
    with pytest.raises(UnbekannteArt):
        await dienst.einreihen("gibtsnicht")


async def test_abbruch_wartend_und_laufend(db):
    gestartet = asyncio.Event()
    dienst = Auftraege(db, arten(gestartet=gestartet))
    await dienst.starten()
    try:
        laeuft = await dienst.einreihen("warten")
        wartet = await dienst.einreihen("warten")               # einer gleichzeitig: der zweite wartet
        await asyncio.wait_for(gestartet.wait(), 5)
        assert (await dienst.holen(wartet.id)).zustand == "wartet"
        assert await dienst.laufend() == 1                      # der wartende zählt nicht (ein Neustart setzt ihn fort)
        assert (await dienst.abbrechen(wartet.id)).zustand == "abgebrochen"
        a = await dienst.abbrechen(laeuft.id)
        assert a.zustand == "laeuft" and a.abbruch_gewuenscht and a.schritt == "Wird abgebrochen"
        assert (await bis(dienst, laeuft.id, "abgebrochen")).zustand == "abgebrochen"
        with pytest.raises(FalscherZustand):
            await dienst.abbrechen(laeuft.id)
    finally:
        await dienst.stoppen()


async def test_fehler_traegt_die_ursache_auch_ohne_text(dienst):
    a = await dienst.einreihen("kaputt")
    f = await bis(dienst, a.id, "fehler")
    assert f.fehler == "ValueError"
    zeile = await dienst.db.zeile("SELECT fehler_spur FROM auftrag WHERE id=?", (a.id,))
    assert "raise ValueError" in zeile["fehler_spur"]


async def test_erwarteter_fehlschlag_ohne_spur_unerwarteter_mit(dienst, caplog):
    """Ein AuftragFehler (auch eine abgeleitete Art) ist ein erwarteter, fachlicher Fehlschlag: Warnung mit der
    Meldung, keine Spur im Log und im Auftrag. Jeder andere Fehler steht mit Spur als Fehler im Log."""
    caplog.set_level(logging.WARNING, logger="appkern.auftraege")
    a = await dienst.einreihen("erwartet")
    f = await bis(dienst, a.id, "fehler")
    assert f.fehler == "Die Seite gibt es nicht mehr (404)"
    assert (await dienst.db.zeile("SELECT fehler_spur FROM auftrag WHERE id=?", (a.id,)))["fehler_spur"] is None
    eintrag = next(r for r in caplog.records if a.id[:8] in r.getMessage())
    assert eintrag.levelno == logging.WARNING and eintrag.exc_info is None
    assert "Die Seite gibt es nicht mehr (404)" in eintrag.getMessage() and "Traceback" not in caplog.text
    caplog.clear()
    b = await dienst.einreihen("kaputt")
    await bis(dienst, b.id, "fehler")
    eintrag = next(r for r in caplog.records if b.id[:8] in r.getMessage())
    assert eintrag.levelno == logging.ERROR and eintrag.exc_info is not None and "Traceback" in caplog.text


async def test_wiederholen_setzt_am_zwischenstand_an(dienst):
    a = await dienst.einreihen("abschnitte")
    f = await bis(dienst, a.id, "fehler")
    assert f.fehler == "RuntimeError: Dienst weg" and f.fortsetzbar
    neu = await dienst.wiederholen(a.id)
    assert neu.wiederholung_von == a.id and neu.id != a.id
    fertig = await bis(dienst, neu.id, "fertig")
    assert fertig.ergebnis == {"abschnitte": [0, 1, 2, 3]}                    # 0 und 1 nicht noch einmal
    with pytest.raises(FalscherZustand):
        await dienst.wiederholen(neu.id)


async def test_wiederholen_mit_geaenderter_eingabe(dienst):
    """Hat sich seit dem ersten Lauf etwas geändert (etwa eine Adresse), wiederholt der Auftrag mit dem neuen Wert;
    geprüft wie beim Einreihen."""
    a = await dienst.einreihen("zaehlen", Texte(texte=["ab"]))
    await bis(dienst, a.id, "fertig")
    await dienst.db.ausfuehren("UPDATE auftrag SET zustand='fehler' WHERE id=?", (a.id,))
    neu = await dienst.wiederholen(a.id, {"texte": ["abc", "de"]})
    assert (await bis(dienst, neu.id, "fertig")).ergebnis == {"zeichen": 5}
    await dienst.db.ausfuehren("UPDATE auftrag SET zustand='fehler' WHERE id=?", (neu.id,))
    with pytest.raises(ValidationError):
        await dienst.wiederholen(neu.id, {"texte": "kein Feld"})


async def test_neustart_haelt_an_oder_setzt_fort(tmp_path: Path):
    pfad = tmp_path / "app.sqlite"
    async with Datenbank(pfad) as db:
        gestartet = asyncio.Event()
        erster = Auftraege(db, arten(gestartet=gestartet), gleichzeitig=2)
        await erster.starten()
        anhalten = await erster.einreihen("warten")
        await asyncio.wait_for(gestartet.wait(), 5)
        fortsetzen = await erster.einreihen("warten_fortsetzen")
        await bis(erster, fortsetzen.id, "laeuft")
        await erster.stoppen()                                                  # wie ein Absturz: beide "laeuft"
    async with Datenbank(pfad) as db:
        freigabe = asyncio.Event()
        freigabe.set()
        zweiter = Auftraege(db, arten(freigabe=freigabe))
        await zweiter.starten()
        try:
            a = await zweiter.holen(anhalten.id)
            assert a.zustand == "unterbrochen" and a.fehler == "Durch einen Neustart unterbrochen"
            assert (await bis(zweiter, fortsetzen.id, "fertig")).ergebnis == {"ok": True}
            neu = await zweiter.wiederholen(anhalten.id)
            assert (await bis(zweiter, neu.id, "fertig")).zustand == "fertig"
        finally:
            await zweiter.stoppen()


async def test_gleichzeitig_grenze(db):
    gestartet = asyncio.Event()
    dienst = Auftraege(db, arten(gestartet=gestartet), gleichzeitig=2)
    await dienst.starten()
    try:
        ids = [(await dienst.einreihen("warten")).id for _ in range(3)]
        await asyncio.sleep(0.2)
        zustaende = sorted([(await dienst.holen(i)).zustand for i in ids])
        assert zustaende == ["laeuft", "laeuft", "wartet"]
        for i in ids:
            await dienst.abbrechen(i)
    finally:
        await dienst.stoppen()


async def test_liste_seitenweise_und_aufraeumen(dienst):
    ids = [(await dienst.einreihen("zaehlen", {"texte": ["x"]}, stapel="s1")).id for _ in range(5)]
    for i in ids:
        await bis(dienst, i, "fertig")
    seite = await dienst.liste(grenze=2, versatz=1, stapel="s1")
    assert seite.gesamt == 5 and len(seite.eintraege) == 2
    assert (await dienst.liste(zustand=["wartet"])).gesamt == 0
    assert (await dienst.liste(suche="Zeichen")).gesamt == 5 and (await dienst.liste(suche="%")).gesamt == 0
    await dienst.db.ausfuehren("UPDATE auftrag SET beendet_am='2020-01-01T00:00:00+00:00' WHERE id=?", (ids[0],))
    assert await dienst.aufraeumen() == 1
    assert (await dienst.liste()).gesamt == 4


async def test_schnittstelle_mit_ereignisstrom(dienst):
    app = FastAPI()
    router = auftrags_router(dienst)
    app.include_router(router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        a = await dienst.einreihen("zaehlen", {"texte": ["abc"]})
        await bis(dienst, a.id, "fertig")
        assert (await client.get(f"/api/v1/auftraege/{a.id}")).json()["ergebnis"] == {"zeichen": 3}
        assert (await client.get("/api/v1/auftraege", params={"zustand": ["fertig"]})).json()["gesamt"] == 1
        assert (await client.post(f"/api/v1/auftraege/{a.id}/abbrechen")).status_code == 409
        assert (await client.get("/api/v1/auftraege/gibtsnicht")).status_code == 404
        k = await dienst.einreihen("kaputt")
        await bis(dienst, k.id, "fehler")
        r = await client.post(f"/api/v1/auftraege/{k.id}/wiederholen")
        assert r.status_code == 201 and r.json()["wiederholung_von"] == k.id
        await bis(dienst, r.json()["id"], "fehler")
        assert (await client.delete(f"/api/v1/auftraege/{k.id}")).status_code == 204
        zahlen = (await client.get("/api/v1/auftraege/zahlen")).json()     # eine Abfrage für alle Zustände
        assert zahlen == {"wartet": 0, "laeuft": 0, "fertig": 1, "fehler": 1, "abgebrochen": 0, "unterbrochen": 0}

    # Ereignisstrom: der Testweg über ASGITransport wartet auf das Ende der Antwort, ein Strom endet nie;
    # deshalb den Körper der Antwort direkt lesen (Format und Reihenfolge sind dieselben).
    route = next(r for r in router.routes if r.path.endswith("/ereignisse"))
    antwort = await route.endpoint()
    assert antwort.media_type == "text/event-stream"
    koerper = antwort.body_iterator
    neu = await dienst.einreihen("zaehlen", {"texte": ["a"]})
    sammeln: list[dict] = []
    while not sammeln or sammeln[-1]["zustand"] != "fertig":
        teil = (await asyncio.wait_for(koerper.__anext__(), 5)).decode()
        assert teil.startswith("event: auftrag\ndata: ") and teil.endswith("\n\n")
        sammeln.append(json.loads(teil.split("data: ", 1)[1]))
    await koerper.aclose()
    assert {e["id"] for e in sammeln} == {neu.id} and sammeln[0]["zustand"] in ("wartet", "laeuft")  # Stand der offenen zuerst


async def test_herzschlag_bei_stille(dienst):
    strom = dienst.ereignisse(herzschlag_s=0.05)
    assert await asyncio.wait_for(strom.__anext__(), 2) is None
    await strom.aclose()
    assert not dienst._hoerer


async def test_datenbank_stufen_nur_einmal(tmp_path: Path):
    async with Datenbank(tmp_path / "x.sqlite") as db:
        assert await db.einrichten("probe", ["CREATE TABLE a (x INTEGER);"]) == 1
        assert await db.einrichten("probe", ["CREATE TABLE a (x INTEGER);", "ALTER TABLE a ADD COLUMN y TEXT;"]) == 2
        assert await db.einrichten("probe", ["CREATE TABLE a (x INTEGER);", "ALTER TABLE a ADD COLUMN y TEXT;"]) == 2
        await db.ausfuehren("INSERT INTO a (x, y) VALUES (1, 'z')")
        with pytest.raises(Exception):
            await db.einrichten("kaputt", ["CREATE TABLE b (x INTEGER); CREATE TABLE b (x INTEGER);"])
        assert await db.zeile("SELECT name FROM sqlite_master WHERE name='b'") is None     # ganz oder gar nicht
        assert await db.zeilen("SELECT x, y FROM a") == [{"x": 1, "y": "z"}]


async def test_anfragen_im_auftrag_tragen_seine_kennung(db):
    """Jede Anfrage an die Leitstelle, die innerhalb eines Auftrags läuft, trägt seine Kennung (X-Leitstelle-Arbeit);
    außerhalb nicht. So sieht die Leitstelle, welche Modelle eine begonnene Arbeit nutzt."""
    from appkern.leitstelle import Leitstelle

    ls = Leitstelle("http://ls.test", "probe", "Probe")
    gesehen = {}

    async def fragen(k: Kontext):
        gesehen["kopf"] = ls.koepfe("im Auftrag")

        async def nebenher():                        # auch in Aufgaben, die die Arbeit selbst startet
            return ls.koepfe("nebenher")
        gesehen["nebenher"] = await asyncio.create_task(nebenher())
        return {"ok": True}

    a = Auftraege(db, [Art("fragen", "Fragen", fragen)])
    await a.starten()
    try:
        auftrag = await a.einreihen("fragen", None, titel="Probe")
        await bis(a, auftrag.id, "fertig")
    finally:
        await a.stoppen()
        await ls.schliessen()
    assert gesehen["kopf"]["X-Leitstelle-Arbeit"] == auftrag.id == gesehen["nebenher"]["X-Leitstelle-Arbeit"]
    assert "X-Leitstelle-Arbeit" not in ls.koepfe("außerhalb")
