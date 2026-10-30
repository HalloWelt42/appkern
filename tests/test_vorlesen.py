"""Vorlesen: Satzteilung und der Anschluss an die App Vorlesen (Strom im Auftrag der Person, Gründe vor der ersten
Zeile als Antwort, Abriss danach als Zeile `fehler`, Feld mit Angebot und Verbindung)."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from appkern.app import Geruest, Grundeinstellungen
from appkern.saetze import hat_worte, saetze, stuecke
from appkern.vorlesen import Vorlesen, VorlesenEinstellungen, VorlesenFehler
from test_geruest import Wolke


class Einstellungen(Grundeinstellungen, VorlesenEinstellungen):
    pass


def test_saetze_abkuerzungen_ordnungszahlen_absaetze():
    text = "Am 12. September kam z. B. Anna. Sie wohnt im 3. Stock!  Was nun?\n\nNeuer Absatz ohne Punkt"
    s = saetze(text)
    assert [x.text for x in s] == ["Am 12. September kam z. B. Anna.", "Sie wohnt im 3. Stock!", "Was nun?",
                                   "Neuer Absatz ohne Punkt"]
    assert [x.absatz_ende for x in s] == [False, False, True, True]
    assert all(text[x.von:x.bis].split() == x.text.split() for x in s)


def test_stuecke_und_worte():
    lang = ", ".join(f"Teil {i} mit einigen Wörtern" for i in range(20)) + "."
    teile = stuecke(lang, 60)
    assert all(len(t) <= 60 for t in teile) and " ".join(teile).split() == lang.split()
    assert stuecke("kurz") == ["kurz"] and stuecke("   ") == []
    assert hat_worte("Ja.") and not hat_worte(" - ... ")


class Vorleseapp(Wolke):
    """Kellerwolke wie im Gerüst-Test, dazu eine App Vorlesen unter vl.test, die sich merkt, wie sie gerufen wurde."""

    def __init__(self) -> None:
        super().__init__()
        self.rufe: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "vl.test":
            return super().__call__(request)
        self.rufe.append(request)
        if request.url.path == "/api/v1/app":
            return httpx.Response(200, json={"fassung": "0.1.0"})
        text = json.loads(request.content)["text"]
        if text == "verboten":
            return httpx.Response(401, json={"detail": "Anmeldung fehlt"})
        if text == "abriss":
            return httpx.Response(200, stream=Abriss())
        zeilen = [{"art": "satz", "nr": i, "text": t, "ton": "UklGRg=="} for i, t in enumerate(text.split("."))]
        zeilen.append({"art": "ende", "saetze": len(zeilen), "dauer_ms": 0})
        return httpx.Response(200, content="".join(json.dumps(z) + "\n" for z in zeilen),
                              headers={"content-type": "application/x-ndjson"})


class Abriss(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"art": "satz", "nr": 0}\n'
        raise httpx.ReadError("weg")


@pytest.fixture
async def umgebung(tmp_path: Path):
    ziel = Vorleseapp()
    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=Einstellungen, transport=httpx.MockTransport(ziel))
    vorlesen = Vorlesen(geruest)
    app: FastAPI = geruest.fastapi()
    app.include_router(vorlesen.router())
    await geruest.starten()
    await geruest.einstellungen.aendern({"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        token = (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]
        yield geruest, vorlesen, ziel, c, {"X-Kellerwolke-Sitzung": token}
    await geruest.stoppen()


async def test_ohne_adresse_nicht_da(umgebung):
    geruest, vorlesen, _, c, h = umgebung
    assert (await c.get("/api/v1/vorlesen", headers=h)).json() == {"da": False}
    r = await c.post("/api/v1/vorlesen", headers=h, json={"text": "Hallo."})
    assert r.status_code == 503 and "nicht eingerichtet" in r.json()["detail"]
    assert (await c.post("/api/v1/vorlesen", json={"text": "Hallo."})).status_code == 401


async def test_strom_im_auftrag_der_person(umgebung):
    geruest, vorlesen, ziel, c, h = umgebung
    await geruest.einstellungen.aendern({"vorlesen_adresse": "http://vl.test/"})
    assert vorlesen.adresse() == "http://vl.test" and (await c.get("/api/v1/vorlesen", headers=h)).json() == {"da": True}
    r = await c.post("/api/v1/vorlesen", headers=h, json={"text": "Eins. Zwei"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert [z["art"] for z in zeilen] == ["satz", "satz", "ende"] and zeilen[1]["text"] == " Zwei"
    ruf = ziel.rufe[-1]
    assert ruf.url.path == "/api/v1/vorlesen/strom" and ruf.headers["authorization"] == "Bearer kw_app_gut"
    assert ruf.headers["x-kellerwolke-sitzung"] == h["X-Kellerwolke-Sitzung"]
    verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
    assert verbindungen["Vorlesen"]["ok"] and verbindungen["Vorlesen"]["meldung"] == "Fassung 0.1.0"
    angebot = (await c.get("/api/v1/einstellungen/angebot/vorlesen_adresse", headers=h)).json()
    assert angebot["optionen"][0]["wert"] == "http://vl.test"


async def test_ablehnung_vorher_abriss_danach(umgebung):
    geruest, vorlesen, _, c, h = umgebung
    await geruest.einstellungen.aendern({"vorlesen_adresse": "http://vl.test"})
    r = await c.post("/api/v1/vorlesen", headers=h, json={"text": "verboten"})
    assert r.status_code == 403 and "lässt das nicht zu" in r.json()["detail"]   # nie als 401 weiter (Lehre 39)
    r = await c.post("/api/v1/vorlesen", headers=h, json={"text": "abriss"})
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert [z["art"] for z in zeilen] == ["satz", "fehler"] and "brach ab" in zeilen[1]["meldung"]
    with pytest.raises(VorlesenFehler) as f:
        await anext(vorlesen.zeilen("x" * 100_001))
    assert f.value.status == 400


def test_einstellungen_ohne_feld_abgelehnt(tmp_path: Path):
    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=Grundeinstellungen)
    with pytest.raises(TypeError):
        Vorlesen(geruest)
