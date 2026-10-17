"""Gerüst einer App gegen nachgestellte Kellerwolke und Leitstelle: erste Einrichtung (nur lokal, nur einmal),
Besitzer aus dem App-Schlüssel, Anmeldung nur für erlaubte Konten, Verbindungen, Protokoll der Ereignisse,
geschützte Bausteine, Auslieferung der Oberfläche."""

import json
from pathlib import Path

import httpx
import pytest
from pydantic import Field

from appkern.app import Geruest, Grundeinstellungen


class ProbeEinstellungen(Grundeinstellungen):
    sprache: str = Field("de", title="Sprache")


class Wolke:
    """Kellerwolke (Ablage und Anmeldung) und Leitstelle in einem Schein."""

    def __init__(self):
        self.sitzungen: dict[str, str] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pfad = request.url.path
        if request.url.host == "kw.test":
            if pfad == "/api/v1/ablage/ich":
                if request.headers.get("authorization") != "Bearer kw_app_gut":
                    return httpx.Response(401, json={"detail": "App-Schlüssel fehlt, ist unbekannt oder gesperrt"})
                return httpx.Response(200, json={"app": "Probe", "konto": "chef", "rechte": []})
            if pfad == "/api/v1/auth/login":
                e = json.loads(request.content)
                if e["passwort"] != "geheim":
                    return httpx.Response(401, json={"detail": "Anmeldung fehlgeschlagen"})
                token = f"t_{e['kennung']}_{len(self.sitzungen)}"
                self.sitzungen[token] = e["kennung"]
                return httpx.Response(200, json={"token": token, "benutzer": self._b(e["kennung"])})
            if pfad == "/api/v1/auth/status":
                name = self.sitzungen.get(request.headers.get("x-kellerwolke-sitzung", ""))
                return httpx.Response(200, json={"angemeldet": bool(name), "benutzer": self._b(name) if name else None})
            if pfad == "/api/v1/auth/logout":
                self.sitzungen.pop(request.headers.get("x-kellerwolke-sitzung", ""), None)
                return httpx.Response(204)
        if request.url.host == "ls.test" and pfad == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "gross"}, {"id": "klangwerk-hoeren"}]})
        return httpx.Response(404, json={"detail": "nicht da"})

    @staticmethod
    def _b(name):
        return {"id": {"chef": "1", "gast": "2"}[name], "name": name, "rolle": "mitglied", "aktiv": True}


@pytest.fixture
async def umgebung(tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>Probe</title>")
    (dist / "assets" / "a.js").write_text("1")
    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=ProbeEinstellungen, oberflaeche=dist, transport=httpx.MockTransport(Wolke()))
    app = geruest.fastapi()
    geruest.oberflaeche_ausliefern(app)
    await geruest.starten()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        yield geruest, app, client
    await geruest.stoppen()


async def test_einrichtung_anmeldung_verbindungen_protokoll(umgebung):
    geruest, app, c = umgebung
    info = (await c.get("/api/v1/app")).json()
    assert info["einrichtung_noetig"] and info["name"] == "Probe" and info["appkern"]
    assert (await c.get("/api/v1/verbindungen")).status_code == 401
    assert (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).status_code == 503

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.168.178.57", 5)), base_url="http://t") as fremd:
        r = await fremd.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
        assert r.status_code == 403
    r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test/", "kellerwolke_schluessel": "kw_app_falsch"})
    assert r.status_code == 422 and "nimmt den Schlüssel nicht" in r.json()["detail"]
    r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test/", "kellerwolke_schluessel": "kw_app_gut"})
    assert r.status_code == 200 and r.json()["besitzer"] == "chef" and not r.json()["einrichtung_noetig"]
    assert r.json()["kellerwolke"] == "http://kw.test" and "kw_app" not in r.text
    assert (await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "x", "kellerwolke_schluessel": "y"})).status_code == 409

    assert (await c.post("/api/v1/anmeldung", json={"kennung": "gast", "passwort": "geheim"})).status_code == 403
    h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]}
    assert (await c.get("/api/v1/ich", headers=h)).json()["name"] == "chef"
    verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
    assert verbindungen["Kellerwolke"]["ok"] and verbindungen["Kellerwolke"]["meldung"] == "Apps/Probe"
    assert not verbindungen["Leitstelle"]["ok"] and verbindungen["Leitstelle"]["meldung"] == "nicht eingerichtet"

    r = await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {
        "leitstelle_adresse": "http://ls.test", "leitstelle_schluessel": "ls_x", "weitere_konten": ["gast"]}})
    assert r.status_code == 200
    assert geruest.leitstelle is not None
    verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
    assert verbindungen["Leitstelle"]["ok"] and verbindungen["Leitstelle"]["meldung"] == "2 Modelle und Dienste"
    assert (await c.post("/api/v1/anmeldung", json={"kennung": "gast", "passwort": "geheim"})).status_code == 200

    ereignisse = [e["ereignis"] for e in (await c.get("/api/v1/protokoll", headers=h)).json()["eintraege"]]
    for e in ("app.eingerichtet", "anmeldung.angemeldet", "anmeldung.abgewiesen", "einstellung.geaendert"):
        assert e in ereignisse
    texte = json.dumps((await c.get("/api/v1/protokoll", headers=h)).json())
    assert "ls_x" not in texte and "kw_app_gut" not in texte and "geheim" not in texte

    assert (await c.get("/api/v1/auftraege")).status_code == 401
    assert (await c.get("/api/v1/auftraege", headers=h)).json()["gesamt"] == 0
    assert (await c.get("/api/v1/einstellungen")).status_code == 401
    await c.post("/api/v1/anmeldung/abmelden", headers=h)
    assert (await c.get("/api/v1/ich", headers=h)).status_code == 401


async def test_oberflaeche_ausliefern(umgebung):
    _, _, c = umgebung
    assert "Probe" in (await c.get("/")).text
    assert "Probe" in (await c.get("/auftraege/irgendwo")).text                 # Seiten der Oberfläche
    r = await c.get("/assets/a.js")
    assert r.text == "1" and "immutable" in r.headers["cache-control"]
    assert (await c.get("/api/v1/gibtsnicht")).status_code == 404
    assert (await c.get("/../../etc/passwd")).status_code in (200, 404)        # nie außerhalb der Oberfläche
    assert "root:" not in (await c.get("/%2e%2e/%2e%2e/etc/passwd")).text


async def test_hausstelle_wird_gefunden_und_geladen(tmp_path: Path, monkeypatch):
    import certifi

    from appkern.app.geruest import hausstelle
    (tmp_path / "rootCA.pem").write_text(Path(certifi.where()).read_text())
    monkeypatch.setenv("CAROOT", str(tmp_path))
    assert hausstelle() == tmp_path / "rootCA.pem"
    geruest = Geruest(name="P", kennung="p", rolle="r", fassung="0", daten=tmp_path / "d", einstellungen=ProbeEinstellungen)
    await geruest.db.oeffnen()
    await geruest.einstellungen.starten()
    assert geruest._pruefung().cert_store_stats()["x509_ca"] > 0
    await geruest.einstellungen.aendern({"ca_datei": str(tmp_path / "gibtsnicht.pem")})
    with pytest.raises(OSError):
        geruest._pruefung()
    await geruest.db.schliessen()
