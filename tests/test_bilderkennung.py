"""Bilderkennung (LS-35): Rahmen von Vision nach oben links, die Gegenseite mit einem nachgestellten Rechner, der Zugang der
Apps über eine nachgestellte Leitstelle. Apple Vision selbst rechnet hier nicht: das läuft nur über die Leitstelle."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from appkern.bilderkennung import BILD_FEHLER, BildFehler, Erkannt, Erkennen, ErkennenDienst, Gesicht, Textstelle, aus_vision
from appkern.bilderkennung.gegenseite import routen
from appkern.leitstelle import LeitstellenFehler


def test_vision_rahmen_von_unten_links_nach_oben_links():
    r = aus_vision(0.1, 0.7, 0.2, 0.1)
    assert (round(r.x, 3), round(r.y, 3), round(r.b, 3), round(r.h, 3)) == (0.1, 0.2, 0.2, 0.1)
    r = aus_vision(0.95, -0.05, 0.2, 0.1)                     # ragt hinaus: bleibt im Bild
    assert r.x == 0.95 and round(r.b, 3) == 0.05 and r.y + r.h <= 1


class Nachgestellt:
    def __init__(self, fehler: str = "") -> None:
        self.fehler, self.auftraege = fehler, []

    def erkennen(self, inhalt: bytes, auftrag: Erkennen) -> Erkannt:
        self.auftraege.append(auftrag)
        if self.fehler:
            raise BildFehler(self.fehler)
        return Erkannt(breite=400, hoehe=300, ms=12.5, texte=[Textstelle(text="Kim Weber", rahmen=aus_vision(0.1, 0.8, 0.3, 0.05), sicherheit=0.98)],
                       gesichter=[Gesicht(rahmen=aus_vision(0.6, 0.4, 0.2, 0.3), sicherheit=0.9)])


def client(hier: Nachgestellt) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(routen(hier))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://d")


async def test_gegenseite_antwortet_mit_dem_erkannten():
    hier = Nachgestellt()
    async with client(hier) as c:
        r = await c.post("/erkennen", files={"bild": ("a.png", b"PNG", "image/png")}, data={"auftrag": Erkennen(gesichter=False).model_dump_json()})
    assert r.status_code == 200
    e = Erkannt.model_validate(r.json())
    assert e.texte[0].text == "Kim Weber" and round(e.texte[0].rahmen.y, 3) == 0.15 and hier.auftraege[0].gesichter is False


async def test_gegenseite_nennt_unlesbares_und_leeres():
    async with client(Nachgestellt(fehler="Das Bild lässt sich nicht lesen")) as c:
        r = await c.post("/erkennen", files={"bild": ("a.png", b"kaputt", "image/png")})
        assert r.status_code == 422 and r.json()["error"]["code"] == BILD_FEHLER
        r = await c.post("/erkennen", files={"bild": ("a.png", b"", "image/png")})
        assert r.status_code == 422 and r.json()["error"]["code"] == BILD_FEHLER
        r = await c.post("/erkennen", files={"bild": ("a.png", b"PNG", "image/png")}, data={"auftrag": '{"sprachen": 5}'})
        assert r.status_code == 422 and r.json()["error"]["code"] == "auftrag"


class Dienst:
    def __init__(self, antwort=None, fehler: LeitstellenFehler | None = None) -> None:
        self.antwort, self.fehler, self.gefragt = antwort, fehler, []

    async def json(self, methode, pfad, **art):
        self.gefragt.append((methode, pfad, art))
        if self.fehler:
            raise self.fehler
        return self.antwort


class Leitstelle:
    def __init__(self, dienst: Dienst) -> None:
        self._dienst, self.namen = dienst, []

    def dienst(self, name: str) -> Dienst:
        self.namen.append(name)
        return self._dienst


async def test_apps_fragen_ueber_die_leitstelle():
    d = Dienst(antwort=Erkannt(breite=10, hoehe=10, ms=1).model_dump())
    ls = Leitstelle(d)
    e = await ErkennenDienst(lambda: ls).erkennen(b"JPG", Erkennen(sprachen=["de-DE"]), titel="Unkenntlich")
    assert e.breite == 10 and ls.namen == ["bild-erkennen"]
    methode, pfad, art = d.gefragt[0]
    assert (methode, pfad) == ("POST", "/erkennen") and art["files"][0][1][1] == b"JPG" and '"de-DE"' in art["data"]["auftrag"] and art["titel"] == "Unkenntlich"


async def test_unlesbares_bild_kommt_als_bildfehler_zurueck():
    ls = Leitstelle(Dienst(fehler=LeitstellenFehler("Das Bild lässt sich nicht lesen", status=422, grund=BILD_FEHLER)))
    with pytest.raises(BildFehler, match="nicht lesen"):
        await ErkennenDienst(lambda: ls).erkennen(b"x")
    with pytest.raises(BildFehler, match="Keine Leitstelle"):
        await ErkennenDienst(lambda: None).erkennen(b"x")
