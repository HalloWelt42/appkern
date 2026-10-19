"""Einstellungen (Vorgabe, Umgebung, gespeichert, Prüfung alles oder nichts, Geheimnisse verdeckt und aufdeckbar,
Beobachter, Zurücksetzen, Fortbestand nach Neustart) und Protokoll (Eintragen ohne Werfen, Filter, Seiten,
Aufräumen, Einträge der Aufträge), je mit Schnittstelle."""

import asyncio
from pathlib import Path
from typing import Literal

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, Field, SecretStr, ValidationError

from appkern.auftraege import Art, Auftraege
from appkern.datenbank import Datenbank
from appkern.einstellungen import Einstellungen, UnbekanntesFeld
from appkern.einstellungen.api import einstellungs_router
from appkern.protokoll import Protokoll
from appkern.protokoll.api import protokoll_router


class AppEinstellungen(BaseModel):
    leitstelle_adresse: str = Field("http://leitstelle:8530", title="Leitstelle", description="Adresse der Leitstelle",
                                    json_schema_extra={"gruppe": "Verbindungen"})
    leitstelle_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel der Leitstelle")
    sprache: Literal["de", "en"] = Field("de", title="Sprache",
                                         json_schema_extra={"beschriftungen": {"de": "Deutsch", "en": "Englisch"}})
    gleichzeitig: int = Field(1, ge=1, le=8, title="Gleichzeitige Aufträge")
    schwelle: float = Field(0.7, ge=0, le=1, title="Schwelle", json_schema_extra={"schritt": 0.05})
    vorlesen: bool = Field(True, title="Vorlesen")


@pytest.fixture
async def db(tmp_path: Path):
    async with Datenbank(tmp_path / "app.sqlite") as d:
        yield d


async def test_herkunft_vorgabe_umgebung_gespeichert(db):
    e = Einstellungen(db, AppEinstellungen, umgebung_praefix="T2_",
                      umgebung={"T2_LEITSTELLE_ADRESSE": "http://pi:8530", "T2_VORLESEN": "nein"})
    stand = await e.starten()
    assert stand.leitstelle_adresse == "http://pi:8530" and stand.vorlesen is False and stand.sprache == "de"
    herkunft = {f.name: f.herkunft for f in e.felder()}
    assert herkunft["leitstelle_adresse"] == "umgebung" and herkunft["sprache"] == "vorgabe"
    assert await e.aendern({"leitstelle_adresse": "http://studio:8530", "sprache": "en"}) == {"leitstelle_adresse", "sprache"}
    assert e.stand.leitstelle_adresse == "http://studio:8530"
    # Neustart: Gespeichertes geht vor der Umgebung.
    e2 = Einstellungen(db, AppEinstellungen, umgebung_praefix="T2_", umgebung={"T2_LEITSTELLE_ADRESSE": "http://pi:8530"})
    assert (await e2.starten()).leitstelle_adresse == "http://studio:8530" and e2.stand.sprache == "en"
    # None setzt zurück: dann gilt wieder die Umgebung.
    await e2.aendern({"leitstelle_adresse": None})
    assert e2.stand.leitstelle_adresse == "http://pi:8530"


async def test_pruefung_alles_oder_nichts(db):
    e = Einstellungen(db, AppEinstellungen)
    await e.starten()
    with pytest.raises(ValidationError):
        await e.aendern({"sprache": "en", "gleichzeitig": 99})
    assert e.stand.sprache == "de" and e.stand.gleichzeitig == 1
    assert await db.zeilen("SELECT * FROM einstellung") == []
    with pytest.raises(UnbekanntesFeld):
        await e.aendern({"gibtsnicht": 1})


async def test_geheimnis_verdeckt_aufdeckbar_und_leer_heisst_unveraendert(db):
    e = Einstellungen(db, AppEinstellungen)
    await e.starten()
    feld = next(f for f in e.felder() if f.name == "leitstelle_schluessel")
    assert feld.art == "geheimnis" and not feld.gesetzt and feld.wert == "" and feld.vorgabe is None
    await e.aendern({"leitstelle_schluessel": "ls_sehr_geheim_1234"})
    feld = next(f for f in e.felder() if f.name == "leitstelle_schluessel")
    assert feld.gesetzt and feld.wert.endswith("1234") and "geheim" not in feld.wert
    assert e.geheimnis("leitstelle_schluessel") == "ls_sehr_geheim_1234"
    assert "geheim" not in repr(e.stand)
    assert await e.aendern({"leitstelle_schluessel": ""}) == set()                      # leer: bleibt
    assert e.geheimnis("leitstelle_schluessel") == "ls_sehr_geheim_1234"
    with pytest.raises(UnbekanntesFeld):
        e.geheimnis("sprache")


async def test_beobachter_hoeren_nur_echte_aenderungen(db):
    e = Einstellungen(db, AppEinstellungen)
    await e.starten()
    gehoert = []

    async def beobachter(stand, geaendert):
        gehoert.append((stand.sprache, geaendert))

    e.bei_aenderung(beobachter)
    e.bei_aenderung(lambda stand, geaendert: gehoert.append(("sync", geaendert)))
    await e.aendern({"sprache": "de"})
    await e.aendern({"sprache": "en"})
    assert gehoert == [("en", {"sprache"}), ("sync", {"sprache"})]


async def test_felder_fuer_die_oberflaeche(db):
    e = Einstellungen(db, AppEinstellungen)
    await e.starten()
    felder = {f.name: f for f in e.felder()}
    assert felder["sprache"].art == "auswahl" and felder["sprache"].optionen == ["de", "en"]
    assert felder["sprache"].beschriftungen == {"de": "Deutsch", "en": "Englisch"}
    assert (felder["schwelle"].schritt, felder["schwelle"].kleinste, felder["schwelle"].groesste) == (0.05, 0.0, 1.0)
    assert (felder["gleichzeitig"].schritt, felder["gleichzeitig"].kleinste, felder["gleichzeitig"].groesste) == (None, 1.0, 8.0)
    assert felder["gleichzeitig"].art == "zahl" and felder["vorlesen"].art == "schalter"
    assert felder["leitstelle_adresse"].gruppe == "Verbindungen" and felder["leitstelle_adresse"].titel == "Leitstelle"
    assert felder["leitstelle_adresse"].beschreibung == "Adresse der Leitstelle"


async def test_einstellungen_schnittstelle(db):
    e = Einstellungen(db, AppEinstellungen)
    await e.starten()
    app = FastAPI()
    app.include_router(einstellungs_router(e))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.patch("/api/v1/einstellungen", json={"werte": {"leitstelle_schluessel": "ls_abcdefgh9876", "sprache": "en"}})
        felder = {f["name"]: f for f in r.json()}
        assert r.status_code == 200 and felder["sprache"]["wert"] == "en" and "abcdefgh" not in r.text
        assert (await c.get("/api/v1/einstellungen/geheimnis/leitstelle_schluessel")).json()["wert"] == "ls_abcdefgh9876"
        assert (await c.get("/api/v1/einstellungen/geheimnis/sprache")).status_code == 404
        r = await c.patch("/api/v1/einstellungen", json={"werte": {"gleichzeitig": 0}})
        assert r.status_code == 422 and "gleichzeitig" in r.json()["detail"]
        assert (await c.patch("/api/v1/einstellungen", json={"werte": {"x": 1}})).status_code == 422
        assert (await c.get("/api/v1/einstellungen/angebot/sprache")).status_code == 404


async def test_angebot_aus_dem_system(db):
    from appkern.einstellungen import Angebot, Option

    e = Einstellungen(db, AppEinstellungen)
    await e.starten()

    async def adressen() -> Angebot:
        return Angebot(optionen=[Option(wert="http://pi:8530", titel="Pi", hinweis="im Heimnetz")], stand="verbunden")

    e.anbieten("leitstelle_adresse", adressen)
    with pytest.raises(UnbekanntesFeld):
        e.anbieten("gibt_es_nicht", adressen)
    felder = {f.name: f for f in e.felder()}
    assert felder["leitstelle_adresse"].angebot and not felder["sprache"].angebot
    app = FastAPI()
    app.include_router(einstellungs_router(e))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = (await c.get("/api/v1/einstellungen/angebot/leitstelle_adresse")).json()
        assert r == {"optionen": [{"wert": "http://pi:8530", "titel": "Pi", "hinweis": "im Heimnetz"}], "eigener_wert": True,
                     "stand": "verbunden"}


async def test_protokoll_filter_seiten_aufraeumen(db):
    p = Protokoll(db, aufbewahren_tage=30)
    await p.starten()
    await p.eintragen("datei.hochgeladen", "Termin.wav", bezug_art="datei", bezug_id="d1", bezug_name="Termin.wav")
    await p.eintragen("auftrag.fehler", "Dienst weg", stufe="fehler", bezug_id="a1", bezug_name="Folge 12")
    await p.eintragen("auftrag.fertig", "", bezug_id="a2", bezug_name="Folge_13 100%")
    assert (await p.liste()).gesamt == 3
    assert [e.ereignis for e in (await p.liste(ereignis="auftrag.")).eintraege] == ["auftrag.fertig", "auftrag.fehler"]
    assert (await p.liste(stufe="fehler")).eintraege[0].text == "Dienst weg"
    assert (await p.liste(bezug_id="d1")).eintraege[0].bezug_name == "Termin.wav"
    assert (await p.liste(suche="_13 100%")).gesamt == 1 and (await p.liste(suche="%")).gesamt == 1   # Platzhalter wörtlich
    heute = (await p.liste()).eintraege[0].zeit.date().isoformat()
    assert (await p.liste(ab=heute)).gesamt == 3 and (await p.liste(ab="2999-01-01")).gesamt == 0
    assert len((await p.liste(grenze=2)).eintraege) == 2 and len((await p.liste(grenze=2, versatz=2)).eintraege) == 1
    await db.ausfuehren("UPDATE protokoll SET zeit='2020-01-01T00:00:00+00:00' WHERE bezug_id='d1'")
    assert await p.aufraeumen() == 1
    app = FastAPI()
    app.include_router(protokoll_router(p))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/protokoll", params={"stufe": "fehler"})).json()["gesamt"] == 1
        assert (await c.get("/api/v1/protokoll", params={"tag": "gestern"})).status_code == 422


async def test_protokoll_bereiche_fuer_sichten(db):
    """Mehrere Anfänge, Stufen und Arten von Aufträgen zugleich, dazu ein fester Endpunkt beim Blättern."""
    p = Protokoll(db)
    await p.starten()
    await p.eintragen("quelle.angelegt", "Ordner")
    await p.eintragen("regeln.geaendert", "Regel")
    await p.eintragen("auftrag.fertig", "", daten={"art": "scannen"})
    await p.eintragen("auftrag.fehler", "weg", stufe="fehler", daten={"art": "einlesen"})
    assert (await p.liste(ereignisse=["quelle.", "regeln."])).gesamt == 2
    assert [e.text for e in (await p.liste(ereignisse=["auftrag."], arten=["einlesen"])).eintraege] == ["weg"]
    assert (await p.liste(stufen=["info", "warnung"])).gesamt == 3
    assert (await p.liste(stufen=["info"], ohne=["auftrag.fertig"])).gesamt == 2
    bis = (await p.liste()).eintraege[0].zeit
    await p.eintragen("quelle.entfernt", "danach")
    assert (await p.liste(bis=bis.isoformat())).gesamt == 4 and (await p.liste()).gesamt == 5
    app = FastAPI()
    app.include_router(protokoll_router(p))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/api/v1/protokoll", params=[("ereignisse", "quelle."), ("ereignisse", "regeln."), ("bis", bis.isoformat())])
        assert r.json()["gesamt"] == 2


async def test_protokoll_wirft_nie(db):
    p = Protokoll(db)
    await p.starten()
    await db.schliessen()
    await p.eintragen("x")                                   # Datenbank zu: wird geschluckt und geloggt


async def test_auftraege_tragen_ins_protokoll_ein(db):
    p = Protokoll(db)
    await p.starten()

    async def ok(k):
        return {"ok": True}

    async def kaputt(k):
        raise RuntimeError("Dienst weg")

    a = Auftraege(db, [Art("ok", "Gut", ok), Art("kaputt", "Kaputt", kaputt)], protokoll=p)
    await a.starten()
    try:
        eins = await a.einreihen("ok", titel="Folge 12")
        zwei = await a.einreihen("kaputt", titel="Folge 13")
        for _ in range(500):
            if (await p.liste()).gesamt >= 2:
                break
            await asyncio.sleep(0.01)
        eintraege = {e.bezug_id: e for e in (await p.liste()).eintraege}
        assert eintraege[eins.id].ereignis == "auftrag.fertig" and eintraege[eins.id].bezug_name == "Folge 12"
        assert eintraege[zwei.id].stufe == "fehler" and eintraege[zwei.id].text == "RuntimeError: Dienst weg"
    finally:
        await a.stoppen()
