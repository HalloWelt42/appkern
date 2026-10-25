"""Verbund: Aufrufe an eine andere App mit dem App-Schlüssel, im Auftrag der Person; Fehler mit der Meldung des Ziels;
Inhalte mit Bereichen durchgereicht; Prüfung und Angebot für die Einstellungen."""

from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI, Request

from appkern.app import Geruest
from appkern.verbund import VerbundFehler
from test_geruest import ProbeEinstellungen, Wolke

TON = bytes(range(256)) * 4


class Ziel(Wolke):
    """Kellerwolke wie im Gerüst-Test, dazu eine andere App unter ziel.test, die sich merkt, wie sie gerufen wurde."""

    def __init__(self) -> None:
        super().__init__()
        self.koepfe: list[httpx.Headers] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host != "ziel.test":
            return super().__call__(request)
        self.koepfe.append(request.headers)
        if request.url.path == "/api/v1/app":
            return httpx.Response(200, json={"fassung": "0.9.1"})
        if request.url.path == "/api/v1/geheim":
            return httpx.Response(403, json={"detail": "Dieses Konto darf die Transkription nicht nutzen"})
        if request.url.path == "/api/v1/ton":
            start, ende = (int(x) for x in request.headers["range"].removeprefix("bytes=").split("-"))
            return httpx.Response(206, content=TON[start:ende + 1], headers={
                "content-type": "audio/wav", "content-range": f"bytes {start}-{ende}/{len(TON)}", "accept-ranges": "bytes",
                "x-intern": "bleibt hier"})
        return httpx.Response(200, json={"suche": request.url.params.get("suche")})


@pytest.fixture
async def umgebung(tmp_path: Path):
    ziel = Ziel()
    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=ProbeEinstellungen, transport=httpx.MockTransport(ziel))
    await geruest.starten()
    await geruest.einstellungen.aendern({"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    yield geruest, ziel
    await geruest.stoppen()


async def test_anfrage_im_auftrag_und_fehler(umgebung):
    geruest, ziel = umgebung
    v = geruest.verbund
    antwort = await v.anfrage("GET", "http://ziel.test/", "/api/v1/suche", sitzung="t-anna", params={"suche": "Dach"})
    assert antwort.json() == {"suche": "Dach"}
    assert ziel.koepfe[-1]["authorization"] == "Bearer kw_app_gut" and ziel.koepfe[-1]["x-kellerwolke-sitzung"] == "t-anna"
    await v.anfrage("GET", "http://ziel.test", "/api/v1/suche")
    assert "x-kellerwolke-sitzung" not in ziel.koepfe[-1]

    with pytest.raises(VerbundFehler) as f:
        await v.anfrage("GET", "http://ziel.test", "/api/v1/geheim", sitzung="t-anna")
    assert (f.value.status, f.value.meldung) == (403, "Dieses Konto darf die Transkription nicht nutzen")
    with pytest.raises(VerbundFehler) as f:
        await v.anfrage("GET", "", "/api/v1/app")
    assert (f.value.status, f.value.meldung) == (None, "nicht eingerichtet")


async def test_durchreichen_mit_bereich(umgebung):
    geruest, ziel = umgebung
    app = FastAPI()

    @app.get("/ton")
    async def ton(request: Request):
        return await geruest.verbund.durchreichen("http://ziel.test", "/api/v1/ton", request, sitzung="t-anna")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/ton", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206 and r.content == TON[100:200]
    assert r.headers["content-range"] == f"bytes 100-199/{len(TON)}" and r.headers["content-type"] == "audio/wav"
    assert "x-intern" not in r.headers and ziel.koepfe[-1]["x-kellerwolke-sitzung"] == "t-anna"


async def test_pruefung_und_angebot(umgebung):
    geruest, _ = umgebung
    adresse = {"wert": ""}
    geruest.verbund.anmelden("Ziel", lambda: adresse["wert"])
    ziel = next(x for x in await geruest.verbindungen() if x.name == "Ziel")
    assert (ziel.ok, ziel.meldung) == (False, "nicht eingerichtet")
    adresse["wert"] = "http://ziel.test"
    ziel = next(x for x in await geruest.verbindungen() if x.name == "Ziel")
    assert (ziel.ok, ziel.meldung, ziel.adresse) == (True, "Fassung 0.9.1", "http://ziel.test")
    angebot = await geruest.verbund.angebot("Ziel", "ziel", lambda: adresse["wert"])()
    assert [o.wert for o in angebot.optionen] == ["http://ziel.test"] and angebot.stand == "verbunden: Fassung 0.9.1"
