"""Gerüst einer App gegen nachgestellte Kellerwolke und Leitstelle: erste Einrichtung (nur lokal, nur einmal),
Besitzer aus dem App-Schlüssel, Anmeldung nur für erlaubte Konten, Verbindungen, Protokoll der Ereignisse,
geschützte Bausteine, Auslieferung der Oberfläche."""

import asyncio
import json
import time
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
        self.kellerwolke_weg = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        pfad = request.url.path
        if request.url.host == "weg.test" or (request.url.host == "kw.test" and self.kellerwolke_weg):
            raise httpx.ConnectError("All connection attempts failed")
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
        if request.url.host == "haengt.test":
            return self._haengen()
        if request.url.host == "ls.test" and pfad == "/v1/models":
            return httpx.Response(200, json={"data": [
                {"id": "gross", "x-leitstelle": {"name": "Groß", "faehigkeiten": ["text"], "geladen": True, "knoten": "studio"}},
                {"id": "klangwerk-hoeren", "x-leitstelle": {"name": "Klangwerk Hören", "faehigkeiten": ["hoeren"]}}]})
        return httpx.Response(404, json={"detail": "nicht da"})

    @staticmethod
    def _b(name):
        return {"id": {"chef": "1", "gast": "2"}[name], "name": name, "rolle": "mitglied", "aktiv": True}

    @staticmethod
    async def _haengen() -> httpx.Response:
        await asyncio.sleep(3600)
        return httpx.Response(200)


@pytest.fixture
async def umgebung(tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<!doctype html><head><title>Probe</title><meta name="app-fassung" content="0.0.9" /></head>')
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
    assert info["auftraege_laufend"] == 0                    # nur die Zahl, für das Ausrollen ohne Abbruch
    assert (await c.get("/api/v1/verbindungen")).status_code == 401
    assert (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).status_code == 503

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("192.168.1.57", 5)), base_url="http://t") as fremd:
        r = await fremd.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
        assert r.status_code == 403
    r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test/", "kellerwolke_schluessel": "kw_app_falsch"})
    assert r.status_code == 422 and "kennt diesen App-Schlüssel nicht" in r.json()["detail"]
    r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://weg.test", "kellerwolke_schluessel": "kw_app_gut"})
    assert r.status_code == 422 and "nicht erreichbar" in r.json()["detail"]
    r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test/", "kellerwolke_schluessel": "kw_app_gut"})
    assert r.status_code == 200 and r.json()["besitzer"] == "chef" and not r.json()["einrichtung_noetig"]
    assert r.json()["kellerwolke"] == "http://kw.test" and "kw_app" not in r.text
    assert (await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "x", "kellerwolke_schluessel": "y"})).status_code == 409

    assert (await c.post("/api/v1/anmeldung", json={"kennung": "gast", "passwort": "geheim"})).status_code == 403
    h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]}
    assert (await c.get("/api/v1/ich", headers=h)).json()["name"] == "chef"
    # die Oberfläche meldet ihre Adresse; eingetragen wird die erste, Unsinn gar nicht
    assert (await c.post("/api/v1/adresse", json={"adresse": "https://app.test:8631"})).status_code == 401
    assert (await c.post("/api/v1/adresse", headers=h, json={"adresse": "javascript:alert(1)"})).status_code == 422
    assert (await c.post("/api/v1/adresse", headers=h, json={"adresse": "https://app.test:8631/pfad"})).status_code == 422
    assert (await c.post("/api/v1/adresse", headers=h, json={"adresse": "https://app.test:8631"})).json()["adresse"] == "https://app.test:8631"
    assert (await c.post("/api/v1/adresse", headers=h, json={"adresse": "http://anders.test"})).json()["adresse"] == "https://app.test:8631"
    assert geruest.einstellungen.stand.adresse == "https://app.test:8631"
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
    for datei in ("/manifest.webmanifest", "/assets/fehlt.js", "/favicon.ico", "/irgendwo/bild.PNG"):
        assert (await c.get(datei)).status_code == 404, datei          # fehlende Datei, nie die Startseite
    for seite in ("/transkripte/abc/12.5", "/einstellungen/verbindungen", "/a.b/c"):
        r = await c.get(seite)
        assert r.status_code == 200 and "Probe" in r.text, seite        # Seiten ohne Dateiendung bleiben Seiten
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
    assert geruest.tls_pruefung().cert_store_stats()["x509_ca"] > 0
    await geruest.einstellungen.aendern({"ca_datei": str(tmp_path / "gibtsnicht.pem")})
    with pytest.raises(OSError):
        geruest.tls_pruefung()
    await geruest.db.schliessen()


async def test_begleiter_leben_mit_dem_geruest(tmp_path: Path):
    from appkern.app import Begleiter

    ablauf: list[str] = []

    class Abgleich(Begleiter):
        def __init__(self, name: str, geruest: Geruest):
            self.name, self.geruest = name, geruest

        async def starten(self):
            ablauf.append(f"{self.name}.starten")

        async def verbunden(self):
            ablauf.append(f"{self.name}.verbunden:{self.geruest.kellerwolke is not None}")

        async def stoppen(self):
            ablauf.append(f"{self.name}.stoppen")

    class Kaputt(Begleiter):
        async def starten(self):
            raise RuntimeError("kaputt")

    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=ProbeEinstellungen, transport=httpx.MockTransport(Wolke()))
    geruest.begleiter_anmelden(Abgleich("a", geruest), Kaputt(), Abgleich("b", geruest))
    await geruest.starten()
    with pytest.raises(RuntimeError):
        geruest.begleiter_anmelden(Abgleich("c", geruest))
    await geruest.einstellungen.aendern({"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    await geruest.stoppen()
    assert ablauf == ["a.starten", "b.starten", "a.verbunden:False", "b.verbunden:False",
                      "a.verbunden:True", "b.verbunden:True", "b.stoppen", "a.stoppen"]


async def test_angebote_fuer_verbindungen_und_leitstelle(umgebung):
    geruest, app, c = umgebung
    await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]}
    felder = {f["name"]: f for f in (await c.get("/api/v1/einstellungen", headers=h)).json()}
    assert felder["kellerwolke_adresse"]["angebot"] and felder["ca_datei"]["angebot"]
    kw = (await c.get("/api/v1/einstellungen/angebot/kellerwolke_adresse", headers=h)).json()
    assert kw["optionen"][0] == {"wert": "http://kw.test", "titel": "http://kw.test", "hinweis": "eingetragen"}
    assert kw["stand"] == "verbunden: Apps/Probe"
    hoeren = geruest.leitstelle_angebot("hoeren")
    assert (await hoeren()).stand.startswith("Leitstelle noch nicht eingerichtet")
    await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {"leitstelle_adresse": "http://ls.test", "leitstelle_schluessel": "ls_x"}})
    angebot = await hoeren()
    assert [(o.wert, o.titel) for o in angebot.optionen] == [("klangwerk-hoeren", "Klangwerk Hören")] and angebot.stand == ""
    text = await geruest.leitstelle_angebot("text", leer="Kette der App")()
    assert [(o.wert, o.titel, o.hinweis) for o in text.optionen] == [("", "Kette der App", "die Leitstelle wählt"),
                                                                     ("gross", "Groß", "geladen auf studio")]
    assert (await geruest.leitstelle_angebot("musik")()).stand == "Die Leitstelle bietet dieser App dafür nichts an"


async def test_oberflaeche_meldet_ihre_gebaute_fassung(umgebung):
    geruest, app, c = umgebung
    assert (await c.get("/api/v1/app")).json()["oberflaeche"] == "0.0.9"     # gebaut für eine ältere Fassung als 0.1.0
    eintraege = (await c.get("/api/v1/protokoll")).status_code
    assert eintraege == 401                                                  # Protokoll bleibt geschützt
    ereignisse = [e.ereignis for e in (await geruest.protokoll.liste()).eintraege]
    assert "app.oberflaeche_veraltet" in ereignisse
    (geruest.oberflaeche / "index.html").write_text('<head><meta name="app-fassung" content="0.1.0" /></head>')
    import os
    os.utime(geruest.oberflaeche / "index.html", (1, 1))
    assert (await c.get("/api/v1/app")).json()["oberflaeche"] == "0.1.0"


async def test_geduld_bei_ausfall_aus_den_einstellungen(umgebung):
    """Die Einstellung "Geduld bei Ausfall" (Minuten, Gruppe Verbindungen) gilt beim Start und nach jeder Änderung für
    alle geduldigen Aufrufe der App."""
    from appkern.leitstelle import geduld, geduld_setzen
    from appkern.leitstelle.geduld import GEDULD_S
    geruest, _app, _c = umgebung
    try:
        feld = geruest.einstellungen.modell.model_fields["leitstelle_geduld_min"]
        assert feld.title == "Geduld bei Ausfall" and feld.default == 30 and feld.json_schema_extra["gruppe"] == "Verbindungen"
        assert geduld() == 30 * 60
        await geruest.einstellungen.aendern({"leitstelle_geduld_min": 5})
        assert geduld() == 5 * 60
    finally:
        geduld_setzen(GEDULD_S)


async def test_einrichtung_von_anderswo_mit_einrichtungscode(umgebung):
    """Hinter Vorschaltdienst oder Docker kommt keine Anfrage vom Rechner selbst (Lehre 34): dann gilt der einmalige Code
    aus der Datei am Rechner (Modus 0600); App-Angaben nennen nur den Ort, nach der Einrichtung ist die Datei weg."""
    geruest, app, c = umgebung
    datei = geruest.daten / "einrichtungscode"
    assert datei.is_file() and (datei.stat().st_mode & 0o777) == 0o600
    code = datei.read_text().strip()
    info = (await c.get("/api/v1/app")).json()
    assert info["einrichtungscode"] == str(datei) and code not in json.dumps(info)
    eingabe = {"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("172.25.0.3", 5)), base_url="http://t") as fremd:
        ohne = await fremd.post("/api/v1/einrichtung", json=eingabe)
        assert ohne.status_code == 403 and str(datei) in ohne.json()["detail"]
        falsch = await fremd.post("/api/v1/einrichtung", json={**eingabe, "einrichtungscode": "AAAA-BBBB-CCCC-DDDD"})
        assert falsch.status_code == 403 and "stimmt nicht" in falsch.json()["detail"]
        r = await fremd.post("/api/v1/einrichtung", json={**eingabe, "einrichtungscode": code.lower().replace("-", " ")})
        assert r.status_code == 200, r.text
        assert not r.json()["einrichtung_noetig"] and r.json()["einrichtungscode"] is None
    assert not datei.exists()
    protokoll = (await c.get("/api/v1/protokoll", headers={"X-Kellerwolke-Sitzung": (await c.post(
        "/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]})).text
    assert "einrichtungscode" in protokoll and code not in protokoll         # der Ort steht drin, der Code nie


def test_einrichtungscode_sperrt_nach_falschen_versuchen(tmp_path):
    from appkern.app.einrichtungscode import Einrichtungscode, Gesperrt

    jetzt = [1000.0]
    e = Einrichtungscode(tmp_path / "code", "~/.app/code", versuche=3, sperre_s=600, uhr=lambda: jetzt[0])
    e.erzeugen()
    richtig = (tmp_path / "code").read_text().strip()
    assert len(richtig) == 19 and richtig.count("-") == 3 and not set(richtig.replace("-", "")) & set("01OIL")
    assert [e.pruefen("falsch") for _ in range(3)] == [False, False, False]
    with pytest.raises(Gesperrt) as g:
        e.pruefen(richtig)                                   # gesperrt, auch für den richtigen Code
    assert 0 < g.value.sekunden <= 600
    jetzt[0] += 601
    assert e.pruefen(richtig)
    e.entfernen()
    assert not (tmp_path / "code").exists() and not e.aktiv and e.pruefen(richtig) is False


async def test_anmeldung_traegt_durch_einen_ausfall_der_kellerwolke(umgebung):
    """Ist die Kellerwolke weg, bleibt die App mit einer früher bestätigten Anmeldung bedienbar (sonst wäre man
    ausgesperrt und könnte nicht einmal ihre Adresse berichtigen): Einstellungen lesen und ändern, Verbindungen zeigen
    die Kellerwolke als nicht erreichbar. Neue Anmeldungen und nie bestätigte Token gehen nicht."""
    geruest, app, c = umgebung
    wolke = geruest._transport.handler
    await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    assert geruest.anmeldung.ausfall_s == 24 * 3600                       # Vorgabe der Einstellung: 24 Stunden
    geruest.anmeldung.merken_s = 0                                        # jede Anfrage fragt die Kellerwolke
    h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]}
    wolke.kellerwolke_weg = True
    assert (await c.get("/api/v1/einstellungen", headers=h)).status_code == 200
    kw = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}["Kellerwolke"]
    assert not kw["ok"] and "nicht erreichbar" in kw["meldung"]
    r = await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {"kellerwolke_adresse": "http://weg.test"}})
    assert r.status_code == 200                                          # auch eine falsche Adresse sperrt nicht aus
    assert (await c.get("/api/v1/ich", headers=h)).json()["name"] == "chef"
    assert (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).status_code == 503
    assert (await c.get("/api/v1/ich", headers={"X-Kellerwolke-Sitzung": "t_nie"})).status_code == 503
    wolke.kellerwolke_weg = False
    r = await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {"kellerwolke_adresse": "http://kw.test"}})
    assert r.status_code == 200
    kw = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}["Kellerwolke"]
    assert kw["ok"]
    await geruest.einstellungen.aendern({"anmeldung_ausfall_h": 2})
    assert geruest.anmeldung.ausfall_s == 2 * 3600


async def test_schnittstellendoku_nur_in_der_entwicklung(tmp_path: Path, monkeypatch):
    """Ohne Anmeldung zeigt die App ihren Aufbau nicht (/docs, /redoc, /openapi.json); mit
    PROBE_SCHNITTSTELLEN_DOKU=1 schon. Das Schema im Code (app.openapi()) gibt es immer."""
    def bauen():
        geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                          einstellungen=ProbeEinstellungen, transport=httpx.MockTransport(Wolke()))
        app = geruest.fastapi()
        geruest.oberflaeche_ausliefern(app)
        return app

    monkeypatch.delenv("PROBE_SCHNITTSTELLEN_DOKU", raising=False)
    app = bauen()
    assert "/api/v1/app" in app.openapi()["paths"]
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        for pfad in ("/docs", "/redoc", "/openapi.json"):
            r = await c.get(pfad)
            assert "swagger" not in r.text.lower() and "redoc" not in r.text.lower() and '"paths"' not in r.text, pfad
    monkeypatch.setenv("PROBE_SCHNITTSTELLEN_DOKU", "1")
    app = bauen()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert "swagger" in (await c.get("/docs")).text.lower()
        assert "/api/v1/app" in (await c.get("/openapi.json")).json()["paths"]


async def test_verbindungen_antworten_rasch_auch_wenn_eine_haengt(umgebung, monkeypatch):
    """Beide Prüfungen laufen nebeneinander und höchstens PRUEFEN_S; eine hängende Leitstelle hält die Antwort nicht
    auf (sonst hinge auch das Erneut-Prüfen der Oberfläche)."""
    import appkern.app.geruest as geruest_modul
    geruest, app, c = umgebung
    monkeypatch.setattr(geruest_modul, "PRUEFEN_S", 0.3)
    await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]}
    await c.patch("/api/v1/einstellungen", headers=h, json={"werte": {"leitstelle_adresse": "http://haengt.test",
                                                                      "leitstelle_schluessel": "ls_x"}})
    beginn = time.perf_counter()
    verbindungen = {v["name"]: v for v in (await c.get("/api/v1/verbindungen", headers=h)).json()}
    assert time.perf_counter() - beginn < 1.5
    assert verbindungen["Kellerwolke"]["ok"]
    assert not verbindungen["Leitstelle"]["ok"] and "antwortet nicht binnen" in verbindungen["Leitstelle"]["meldung"]
    assert verbindungen["Leitstelle"]["adresse"] == "http://haengt.test"


async def test_weitere_verbindungen_und_farbe(umgebung):
    """Eine App meldet weitere Verbindungen (andere Apps, Dienste am Mac); sie stehen neben Kellerwolke und Leitstelle,
    eine scheiternde Prüfung wird eine gestörte Verbindung statt eines Fehlers."""
    from appkern.app.geruest import Verbindung
    geruest, _, c = umgebung

    async def fundus() -> Verbindung:
        return Verbindung(name="Fundus", ok=True, adresse="https://fundus.test", meldung="21 Werkzeuge")

    async def kaputt() -> Verbindung:
        raise RuntimeError("weg")

    geruest.verbindung_anmelden("Fundus", fundus)
    geruest.verbindung_anmelden("Befehlsdienst", kaputt)
    assert (await c.get("/api/v1/app")).json()["farbe"] == "#2f7ce0"
    await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
    h = {"X-Kellerwolke-Sitzung": (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]}
    liste = (await c.get("/api/v1/verbindungen", headers=h)).json()
    assert [v["name"] for v in liste] == ["Kellerwolke", "Leitstelle", "Fundus", "Befehlsdienst"]
    assert liste[2]["ok"] and liste[2]["meldung"] == "21 Werkzeuge"
    assert not liste[3]["ok"] and "RuntimeError" in liste[3]["meldung"]
