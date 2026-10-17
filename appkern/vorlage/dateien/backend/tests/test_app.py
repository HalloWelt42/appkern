"""__NAME__ gegen eine nachgestellte Kellerwolke: einrichten, anmelden, Probeauftrag bis zum Ende, Protokoll."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.main import app_bauen


def kellerwolke(request: httpx.Request) -> httpx.Response:
    pfad = request.url.path
    if pfad == "/api/v1/ablage/ich":
        return httpx.Response(200, json={"app": "__NAME__", "konto": "probe", "rechte": []})
    if pfad == "/api/v1/auth/login":
        if json.loads(request.content)["passwort"] != "geheim":
            return httpx.Response(401, json={"detail": "Anmeldung fehlgeschlagen"})
        return httpx.Response(200, json={"token": "t1", "benutzer": {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True}})
    if pfad == "/api/v1/auth/status":
        ok = request.headers.get("x-kellerwolke-sitzung") == "t1"
        return httpx.Response(200, json={"angemeldet": ok, "benutzer": {"id": "1", "name": "probe", "rolle": "mitglied", "aktiv": True} if ok else None})
    return httpx.Response(404, json={"detail": "nicht da"})


@pytest.fixture
async def client(tmp_path: Path):
    app = app_bauen(tmp_path / "daten", transport=httpx.MockTransport(kellerwolke))
    await app.state.geruest.starten()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c
    await app.state.geruest.stoppen()


async def test_einrichten_anmelden_probeauftrag(client):
    assert (await client.get("/api/v1/app")).json()["einrichtung_noetig"]
    r = await client.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_x"})
    assert r.json()["besitzer"] == "probe"
    h = {"X-Kellerwolke-Sitzung": (await client.post("/api/v1/anmeldung", json={"kennung": "probe", "passwort": "geheim"})).json()["token"]}
    assert (await client.post("/api/v1/probe", json={"schritte": 3, "pause_s": 0})).status_code == 401
    a = (await client.post("/api/v1/probe", headers=h, json={"schritte": 3, "pause_s": 0})).json()
    for _ in range(300):
        stand = (await client.get(f"/api/v1/auftraege/{a['id']}", headers=h)).json()
        if stand["zustand"] == "fertig":
            break
        await asyncio.sleep(0.01)
    assert stand["ergebnis"] == {"schritte": 3} and stand["phase"] == "abschliessen"
    ereignisse = [e["ereignis"] for e in (await client.get("/api/v1/protokoll", headers=h)).json()["eintraege"]]
    assert "auftrag.fertig" in ereignisse and "app.eingerichtet" in ereignisse
