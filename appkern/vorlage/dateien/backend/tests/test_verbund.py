"""Verbund: __NAME__ gegen eine echte Kellerwolke (Entwicklungsinstanz), mit einem eigenen Testzugang (Lehre 20):
`backend/.env.test` (nie im Repo) mit KELLERWOLKE_ADRESSE, KELLERWOLKE_SCHLUESSEL (App-Schlüssel nur für Tests, nicht
der der Entwicklungsinstanz), KELLERWOLKE_KENNUNG und KELLERWOLKE_PASSWORT des Kontos, dem der Schlüssel gehört; ohne
wird übersprungen. Am Ende: Angelegtes in den Papierkorb (Dateien vor Ordnern), Aktionen des Testzugangs zurückziehen,
Sitzung beenden. Tests gehen nur Wege, die auch die Oberfläche geht (Lehre 19)."""

import asyncio
import uuid
from pathlib import Path

import httpx
import pytest

from appkern.testen import aktionen_zurueckziehen, aufraeumen, hat_kellerwolke, werte

from app.main import app_bauen

W = werte(Path(__file__).resolve().parents[1] / ".env.test")
pytestmark = pytest.mark.skipif(not hat_kellerwolke(W), reason="kein eigener Testzugang eingerichtet (backend/.env.test)")


async def test_einrichten_anmelden_auftrag_ablage(tmp_path: Path):
    app = app_bauen(tmp_path / "daten")
    geruest = app.state.geruest
    await geruest.starten()
    angelegt: list = []
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": W["KELLERWOLKE_ADRESSE"],
                                                          "kellerwolke_schluessel": W["KELLERWOLKE_SCHLUESSEL"]})
            assert r.status_code == 200, r.text
            r = await c.post("/api/v1/anmeldung", json={"kennung": W["KELLERWOLKE_KENNUNG"], "passwort": W["KELLERWOLKE_PASSWORT"]})
            assert r.status_code == 200, r.text
            h = {"X-Kellerwolke-Sitzung": r.json()["token"]}
            try:
                # wie die Oberfläche nach der Anmeldung: die App meldet ihre Adresse (für Öffnen aus der Kellerwolke)
                assert (await c.post("/api/v1/adresse", headers=h, json={"adresse": "http://t"})).status_code == 200
                verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
                assert verbindungen["Kellerwolke"]["ok"]
                a = (await c.post("/api/v1/probe", headers=h, json={"schritte": 2, "pause_s": 0})).json()
                for _ in range(300):
                    if (await c.get(f"/api/v1/auftraege/{a['id']}", headers=h)).json()["zustand"] == "fertig":
                        break
                    await asyncio.sleep(0.01)
                else:
                    pytest.fail("Probeauftrag wurde nicht fertig")
                # Ablage im eigenen Zweig: Ordner mit Datei anlegen, am Ende wieder weg
                kw = geruest.kellerwolke
                zweig = (await kw.ich()).zweig
                ordner = await kw.ordner(f"{zweig}/Testlauf {uuid.uuid4().hex[:8]}")
                angelegt.append(ordner.id)
                angelegt.append((await kw.schreiben(f"{ordner.pfad}/probe.txt", b"probe", inhaltstyp="text/plain")).id)
            finally:
                await c.post("/api/v1/anmeldung/abmelden", headers=h)
    finally:
        if angelegt and geruest.kellerwolke is not None:
            assert await aufraeumen(geruest.kellerwolke, angelegt) == []
        await geruest.stoppen()
        await aktionen_zurueckziehen(W["KELLERWOLKE_ADRESSE"], W["KELLERWOLKE_SCHLUESSEL"])
