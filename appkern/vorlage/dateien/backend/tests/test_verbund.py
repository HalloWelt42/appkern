"""Verbund: __NAME__ gegen eine echte Kellerwolke (Entwicklungsinstanz). Braucht `backend/.env.test` mit
KELLERWOLKE_ADRESSE, KELLERWOLKE_SCHLUESSEL (App-Schlüssel), KELLERWOLKE_KENNUNG und KELLERWOLKE_PASSWORT des Kontos,
dem der Schlüssel gehört; ohne wird übersprungen. Die Sitzung wird am Ende beendet."""

import asyncio
import os
from pathlib import Path

import httpx
import pytest

from app.main import app_bauen


def _werte() -> dict[str, str]:
    werte = dict(os.environ)
    datei = Path(__file__).resolve().parents[1] / ".env.test"
    if datei.is_file():
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            k, _, w = zeile.partition("=")
            werte.setdefault(k.strip(), w.strip())
    return werte


W = _werte()
pytestmark = pytest.mark.skipif(not all(W.get(k) for k in ("KELLERWOLKE_ADRESSE", "KELLERWOLKE_SCHLUESSEL",
                                                            "KELLERWOLKE_KENNUNG", "KELLERWOLKE_PASSWORT")),
                                reason="keine Test-Kellerwolke eingerichtet (backend/.env.test)")


async def test_einrichten_anmelden_auftrag(tmp_path: Path):
    app = app_bauen(tmp_path / "daten")
    await app.state.geruest.starten()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": W["KELLERWOLKE_ADRESSE"],
                                                          "kellerwolke_schluessel": W["KELLERWOLKE_SCHLUESSEL"]})
            assert r.status_code == 200, r.text
            r = await c.post("/api/v1/anmeldung", json={"kennung": W["KELLERWOLKE_KENNUNG"], "passwort": W["KELLERWOLKE_PASSWORT"]})
            assert r.status_code == 200, r.text
            h = {"X-Kellerwolke-Sitzung": r.json()["token"]}
            try:
                verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
                assert verbindungen["Kellerwolke"]["ok"]
                a = (await c.post("/api/v1/probe", headers=h, json={"schritte": 2, "pause_s": 0})).json()
                for _ in range(300):
                    if (await c.get(f"/api/v1/auftraege/{a['id']}", headers=h)).json()["zustand"] == "fertig":
                        break
                    await asyncio.sleep(0.01)
                else:
                    pytest.fail("Probeauftrag wurde nicht fertig")
            finally:
                await c.post("/api/v1/anmeldung/abmelden", headers=h)
    finally:
        await app.state.geruest.stoppen()
