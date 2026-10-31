"""Vorlesen über die Vertonung: Satzteilung, Teile bis 7500 Zeichen mit durchgezählten Sätzen, Strom im Auftrag der
Person, Gründe vor dem ersten Satz als Antwort, Abriss danach als Zeile `fehler`, Vorlesestimme je App mit der Auswahl
aus der Vertonung (Katalog und privat nur, was sie dieser App freigibt)."""

import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from appkern.app import Geruest, Grundeinstellungen
from appkern.saetze import hat_worte, saetze, stuecke
from appkern.vorlesen import TEIL_HOECHSTENS, Vorlesen, VorlesenEinstellungen, VorlesenFehler, stimmwahl, teile
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


def test_stuecke_teile_und_worte():
    lang = ", ".join(f"Teil {i} mit einigen Wörtern" for i in range(20)) + "."
    st = stuecke(lang, 60)
    assert all(len(t) <= 60 for t in st) and " ".join(st).split() == lang.split()
    assert stuecke("kurz") == ["kurz"] and stuecke("   ") == []
    assert hat_worte("Ja.") and not hat_worte(" - ... ")
    text = "Das ist ein Satz mit genau so vielen Wörtern, dass er lang genug ist. " * 130
    t = teile(text)
    assert len(t) == 2 and all(len(x) <= TEIL_HOECHSTENS for x in t) and " ".join(t).split() == text.split()
    assert stimmwahl("") is None and stimmwahl("katalog:eins") == {"art": "katalog", "name": "eins"}
    assert stimmwahl("abc-123") == {"art": "klon", "knoten_id": "abc-123"}


class Vertonung(Wolke):
    """Kellerwolke wie im Gerüst-Test, dazu eine Vertonung unter vt.test, die sich merkt, wie sie gerufen wurde."""

    def __init__(self) -> None:
        super().__init__()
        self.rufe: list[httpx.Request] = []
        self.privat_frei = True

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "vt.test":
            return super().__call__(request)
        self.rufe.append(request)
        pfad = request.url.path
        if pfad == "/api/v1/app":
            return httpx.Response(200, json={"fassung": "0.17.0"})
        if pfad == "/api/v1/stimmen":
            if request.url.params.get("bereich") == "privat":
                if not self.privat_frei:
                    return httpx.Response(403, json={"detail": "Private Stimmen sind dieser App nicht erlaubt"})
                return httpx.Response(200, json=[{"id": "p-1", "name": "Eigene", "bereich": "privat"}])
            return httpx.Response(200, json=[{"id": "katalog:eins", "name": "eins", "bereich": "katalog"}])
        text = json.loads(request.content)["text"]
        if text.startswith("verboten"):
            return httpx.Response(401, json={"detail": "Anmeldung fehlt"})
        if text.startswith("abriss"):
            return httpx.Response(200, stream=Abriss())
        saetze_ = [t for t in re.split(r"(?<=[.!?])\s+", text) if t]
        zeilen = [{"art": "satz", "nr": i, "text": t, "dauer_ms": 1000, "ton": "UklGRg=="} for i, t in enumerate(saetze_)]
        zeilen.append({"art": "ende", "saetze": len(zeilen), "dauer_ms": 1000 * len(zeilen)})
        return httpx.Response(200, content="".join(json.dumps(z) + "\n" for z in zeilen),
                              headers={"content-type": "application/x-ndjson"})


class Abriss(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'{"art": "satz", "nr": 0, "dauer_ms": 1}\n'
        raise httpx.ReadError("weg")


@pytest.fixture
async def umgebung(tmp_path: Path):
    ziel = Vertonung()
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


def strom(ziel: Vertonung) -> list[httpx.Request]:
    return [r for r in ziel.rufe if r.url.path == "/api/v1/sprechen/strom"]


async def test_ohne_adresse_nicht_da(umgebung):
    geruest, vorlesen, _, c, h = umgebung
    assert (await c.get("/api/v1/vorlesen", headers=h)).json() == {"da": False}
    r = await c.post("/api/v1/vorlesen", headers=h, json={"text": "Hallo."})
    assert r.status_code == 503 and "nicht eingerichtet" in r.json()["detail"]
    assert (await c.post("/api/v1/vorlesen", json={"text": "Hallo."})).status_code == 401


async def test_strom_im_auftrag_der_person_in_teilen(umgebung):
    geruest, vorlesen, ziel, c, h = umgebung
    await geruest.einstellungen.aendern({"vertonung_adresse": "http://vt.test/"})
    assert vorlesen.adresse() == "http://vt.test" and (await c.get("/api/v1/vorlesen", headers=h)).json() == {"da": True}
    r = await c.post("/api/v1/vorlesen", headers=h, json={"text": "Eins. Zwei."})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    zeilen = [json.loads(z) for z in r.text.splitlines()]
    assert [z["art"] for z in zeilen] == ["satz", "satz", "ende"] and zeilen[-1] == {"art": "ende", "saetze": 2, "dauer_ms": 2000}
    ruf = strom(ziel)[-1]
    assert json.loads(ruf.content) == {"ausschreiben": True, "text": "Eins. Zwei."}      # ohne Wahl: Stimme ab Werk
    assert ruf.headers["authorization"] == "Bearer kw_app_gut" and ruf.headers["x-kellerwolke-sitzung"] == h["X-Kellerwolke-Sitzung"]
    lang = "Das ist ein Satz mit genau so vielen Wörtern, dass er lang genug ist. " * 130
    zeilen = [json.loads(z) for z in (await c.post("/api/v1/vorlesen", headers=h, json={"text": lang})).text.splitlines()]
    assert len(strom(ziel)) == 3 and [z["nr"] for z in zeilen if z["art"] == "satz"] == list(range(130))
    verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
    assert verbindungen["Vertonung"]["ok"] and verbindungen["Vertonung"]["meldung"] == "Fassung 0.17.0"


async def test_vorlesestimme_der_app(umgebung):
    geruest, vorlesen, ziel, c, h = umgebung
    angebot = (await c.get("/api/v1/einstellungen/angebot/vorlesen_stimme", headers=h)).json()
    assert [o["wert"] for o in angebot["optionen"]] == [""] and not angebot["eigener_wert"]
    await geruest.einstellungen.aendern({"vertonung_adresse": "http://vt.test"})
    angebot = (await c.get("/api/v1/einstellungen/angebot/vorlesen_stimme", headers=h)).json()
    assert [o["wert"] for o in angebot["optionen"]] == ["", "p-1", "katalog:eins"]
    ziel.privat_frei = False                                          # nicht freigegeben: nur der Katalog
    angebot = (await c.get("/api/v1/einstellungen/angebot/vorlesen_stimme", headers=h)).json()
    assert [o["wert"] for o in angebot["optionen"]] == ["", "katalog:eins"]
    await geruest.einstellungen.aendern({"vorlesen_stimme": "p-1"})
    await c.post("/api/v1/vorlesen", headers=h, json={"text": "Zwei."})
    assert json.loads(strom(ziel)[-1].content)["stimme"] == {"art": "klon", "knoten_id": "p-1"}
    await geruest.einstellungen.aendern({"vorlesen_stimme": "katalog:eins"})
    await c.post("/api/v1/vorlesen", headers=h, json={"text": "Drei."})
    assert json.loads(strom(ziel)[-1].content)["stimme"] == {"art": "katalog", "name": "eins"}


async def test_ablehnung_vorher_abriss_danach(umgebung):
    geruest, vorlesen, _, c, h = umgebung
    await geruest.einstellungen.aendern({"vertonung_adresse": "http://vt.test"})
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
