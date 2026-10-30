"""Anmeldung mit dem Kellerwolke-Konto gegen eine nachgestellte Kellerwolke: Passwort, Kopplung, Prüfen mit Merken,
erlaubte Konten (fremde Sitzung wird sofort beendet), Abmelden, Kellerwolke weg (bestätigte Anmeldungen gelten aus dem
Merker weiter), Schnittstelle mit Cookie."""

import asyncio
import json

import httpx
import pytest
from fastapi import Depends, FastAPI

from appkern.anmeldung import Abgelehnt, Anmeldung, KellerwolkeWeg, NichtErlaubt, ZuVieleVersuche
from appkern.anmeldung.api import COOKIE, angemeldet, anmeldungs_router, inhalt_cookie

KONTEN = {"chef": "1", "gast": "2"}
APPS = {"kw_app_vertonung": ("Vertonung", "chef"), "kw_app_fremd": ("Fremd", "gast")}


class Schein:
    """Kellerwolke mit Login, Kopplung, Status und Abmelden."""

    def __init__(self):
        self.sitzungen: dict[str, str] = {}
        self.statusabrufe = 0
        self.ich_abrufe = 0
        self.abmeldungen: list[str] = []
        self.weg = False
        self.versuche = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.versuche += 1
        if self.weg:
            raise httpx.ConnectError("weg")
        pfad = request.url.path
        if pfad == "/api/v1/auth/login":
            e = json.loads(request.content)
            if e["kennung"] in KONTEN and e["passwort"] == "geheim":
                token = f"tok_{e['kennung']}_{len(self.sitzungen)}"
                self.sitzungen[token] = e["kennung"]
                return httpx.Response(200, json={"token": token, "benutzer": self._b(e["kennung"])})
            return httpx.Response(401, json={"detail": "Anmeldung fehlgeschlagen"})
        if pfad == "/api/v1/geraete/koppeln":
            e = json.loads(request.content)
            if e["code"] == "BREMSE":
                return httpx.Response(429, json={"detail": "Zu viele falsche Codes."}, headers={"Retry-After": "120"})
            if e["code"] not in ("CHEF0001", "GAST0001"):
                return httpx.Response(404, json={"detail": "Dieser Code gilt nicht (mehr)."})
            name = "chef" if e["code"].startswith("CHEF") else "gast"
            schluessel = f"kw_geraet_{name}_{len(self.sitzungen)}"
            self.sitzungen[schluessel] = name
            return httpx.Response(201, json={"schluessel": schluessel, "geraet": {}, "benutzer": self._b(name)})
        if pfad == "/api/v1/auth/status":
            self.statusabrufe += 1
            name = self.sitzungen.get(request.headers.get("x-kellerwolke-sitzung", ""))
            return httpx.Response(200, json={"angemeldet": bool(name), "benutzer": self._b(name) if name else None})
        if pfad == "/api/v1/ablage/ich":
            self.ich_abrufe += 1
            app = APPS.get(request.headers.get("authorization", "").removeprefix("Bearer "))
            if not app:
                return httpx.Response(401, json={"detail": "Ungültiger Schlüssel"})
            return httpx.Response(200, json={"app": app[0], "konto": app[1], "konto_id": KONTEN[app[1]], "rechte": []})
        if pfad == "/api/v1/auth/logout":
            self.abmeldungen.append(request.headers.get("x-kellerwolke-sitzung", ""))
            self.sitzungen.pop(request.headers.get("x-kellerwolke-sitzung", ""), None)
            return httpx.Response(204)
        return httpx.Response(404)

    @staticmethod
    def _b(name):
        return {"id": KONTEN[name], "name": name, "kuerzel": None, "rolle": "mitglied", "aktiv": True}


def anmeldung(schein, erlaubt=lambda: {"Chef"}, **art) -> Anmeldung:
    return Anmeldung("http://kw.test", erlaubt, client=httpx.AsyncClient(transport=httpx.MockTransport(schein)), **art)


async def test_passwort_pruefen_merken_abmelden():
    s = Schein()
    a = anmeldung(s)
    token, konto = await a.anmelden("chef", "geheim")
    assert konto.name == "chef" and not konto.geraet
    assert (await a.pruefen(token)).name == "chef"
    assert s.statusabrufe == 0                                     # nach dem Anmelden gemerkt
    await a.abmelden(token)
    assert token not in s.sitzungen and await a.pruefen(token) is None and s.statusabrufe == 1
    with pytest.raises(Abgelehnt):
        await a.anmelden("chef", "falsch")


async def test_fremdes_konto_wird_abgewiesen_und_seine_sitzung_beendet():
    s = Schein()
    a = anmeldung(s)
    with pytest.raises(NichtErlaubt):
        await a.anmelden("gast", "geheim")
    assert s.sitzungen == {}
    with pytest.raises(NichtErlaubt):
        await a.koppeln("GAST0001", "Telefon", "webapp")
    assert s.sitzungen == {}
    offen = anmeldung(s, erlaubt=None)
    token, konto = await offen.anmelden("gast", "geheim")
    assert konto.name == "gast"


async def test_koppeln_und_fehler():
    s = Schein()
    a = anmeldung(s)
    schluessel, konto = await a.koppeln("CHEF0001", "Telefon", "webapp")
    assert konto.geraet and schluessel.startswith("kw_geraet_")
    with pytest.raises(Abgelehnt) as f:
        await a.koppeln("FALSCH", "Telefon", "webapp")
    assert "http://kw.test" in f.value.meldung                     # sagt, welche Kellerwolke gefragt wurde
    assert "ein Code aus einer anderen Kellerwolke gilt hier nie" in f.value.meldung
    with pytest.raises(ZuVieleVersuche) as f:
        await a.koppeln("BREMSE", "Telefon", "webapp")
    assert f.value.nochmal_in == 120


async def test_erlaubt_wird_bei_jedem_pruefen_gefragt_und_merken_laeuft_ab():
    s = Schein()
    erlaubt = {"chef"}
    a = anmeldung(s, erlaubt=lambda: erlaubt, merken_s=0.0)
    token, _ = await a.anmelden("chef", "geheim")
    assert (await a.pruefen(token)).name == "chef" and s.statusabrufe == 1
    erlaubt.clear()
    assert await a.pruefen(token) is None                          # Einstellung geändert: sofort wirksam
    s.weg = True
    with pytest.raises(KellerwolkeWeg):
        await a.pruefen("irgendwas")


async def test_schnittstelle_mit_schutz_und_cookie():
    s = Schein()
    a = anmeldung(s)
    app = FastAPI()
    app.include_router(anmeldungs_router(a))
    pflicht = angemeldet(a)
    lesen = angemeldet(a, cookie=True)

    @app.get("/api/v1/geheim")
    async def geheim(konto=Depends(pflicht)):
        return {"konto": konto.name}

    @app.get("/api/v1/inhalt/ton")
    async def ton(konto=Depends(lesen)):
        return {"konto": konto.name}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/geheim")).status_code == 401
        assert (await c.post("/api/v1/anmeldung", json={"kennung": "gast", "passwort": "geheim"})).status_code == 403
        r = await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})
        h = {"X-Kellerwolke-Sitzung": r.json()["token"]}
        assert (await c.get("/api/v1/anmeldung", headers=h)).json()["konto"]["name"] == "chef"
        assert (await c.get("/api/v1/geheim", headers=h)).json() == {"konto": "chef"}
        r = await c.post("/api/v1/anmeldung/zugang", headers=h)
        assert r.status_code == 204 and COOKIE in r.cookies
        assert (await c.get("/api/v1/inhalt/ton")).json() == {"konto": "chef"}            # über das Cookie
        assert (await c.post("/api/v1/anmeldung/koppeln", json={"code": "BREMSE", "name": "T", "art": "webapp"})).headers["retry-after"] == "120"
        assert (await c.post("/api/v1/anmeldung/abmelden", headers=h)).status_code == 204
        assert (await c.get("/api/v1/geheim", headers=h)).status_code == 401
        s.weg = True
        assert (await c.get("/api/v1/geheim", headers={"X-Kellerwolke-Sitzung": "x"})).status_code == 503


async def test_andere_app_mit_ihrem_app_schluessel():
    s = Schein()
    a = anmeldung(s)
    konto = await a.pruefen("kw_app_vertonung")
    assert konto.name == "chef" and konto.app == "Vertonung" and not konto.mensch and konto.id == "1"
    assert (await a.pruefen("kw_app_vertonung")).app == "Vertonung" and s.ich_abrufe == 1      # gemerkt
    assert await a.pruefen("kw_app_fremd") is None                     # gehört einem Konto, das nicht darf
    assert await a.pruefen("kw_app_unbekannt") is None
    await a.abmelden("kw_app_vertonung")                                # beendet den fremden Schlüssel nie
    assert s.abmeldungen == [] and (await a.pruefen("kw_app_vertonung")).app == "Vertonung"


async def test_schnittstelle_fuer_andere_apps_ohne_oberflaechen_eigenes():
    s = Schein()
    a = anmeldung(s)
    app = FastAPI()
    app.include_router(anmeldungs_router(a))

    @app.get("/api/v1/arbeit")
    async def arbeit(konto=Depends(angemeldet(a))):
        return {"konto": konto.name, "app": konto.app}

    @app.get("/api/v1/einstellungen")
    async def einstellungen(konto=Depends(angemeldet(a, nur_menschen=True))):
        return {"konto": konto.name}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        h = {"Authorization": "Bearer kw_app_vertonung"}
        assert (await c.get("/api/v1/arbeit", headers=h)).json() == {"konto": "chef", "app": "Vertonung"}
        assert (await c.get("/api/v1/einstellungen", headers=h)).status_code == 403
        assert (await c.post("/api/v1/anmeldung/zugang", headers=h)).status_code == 403
        assert (await c.get("/api/v1/arbeit", headers={"Authorization": "Bearer kw_app_fremd"})).status_code == 401
        r = await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})
        assert (await c.get("/api/v1/einstellungen", headers={"X-Kellerwolke-Sitzung": r.json()["token"]})).status_code == 200


async def test_im_ausfall_gilt_eine_bestaetigte_anmeldung_aus_dem_merker():
    """Ist die Kellerwolke weg, gilt eine früher bestätigte Sitzung und ein bestätigter App-Schlüssel weiter, bis
    `ausfall_s` nach der letzten Bestätigung; nachgefragt wird im Hintergrund, frühestens nach `merken_s`. Nie
    bestätigte Token und neue Anmeldungen brauchen die Kellerwolke."""
    s = Schein()
    jetzt = [1000.0]
    a = anmeldung(s, merken_s=60, ausfall_s=3600, uhr=lambda: jetzt[0])
    token, _ = await a.anmelden("chef", "geheim")
    assert (await a.pruefen("kw_app_vertonung")).app == "Vertonung"
    s.weg = True
    jetzt[0] += 61                                                    # gemerkt abgelaufen: Rückfrage nötig
    assert (await a.pruefen(token)).name == "chef"                    # Kellerwolke weg: aus dem Merker
    assert (await a.pruefen("kw_app_vertonung")).app == "Vertonung"
    with pytest.raises(KellerwolkeWeg):
        await a.pruefen("tok_nie_bestaetigt")
    with pytest.raises(KellerwolkeWeg):
        await a.anmelden("chef", "geheim")
    versuche = s.versuche
    jetzt[0] += 30
    assert (await a.pruefen(token)).name == "chef" and s.versuche == versuche      # im Ausfall nicht bei jeder Anfrage
    jetzt[0] += 31
    assert (await a.pruefen(token)).name == "chef"                    # sofort aus dem Merker, Rückfrage im Hintergrund
    await asyncio.sleep(0.01)
    assert s.versuche == versuche + 1

    s.weg = False
    s.sitzungen.pop(token)                                            # inzwischen in der Kellerwolke beendet
    jetzt[0] += 61
    assert (await a.pruefen(token)).name == "chef"                    # noch aus dem Merker, die Rückfrage läuft
    await asyncio.sleep(0.01)
    assert await a.pruefen(token) is None                             # die Kellerwolke sagt: vorbei
    jetzt[0] += 61
    assert (await a.pruefen("kw_app_vertonung")).app == "Vertonung"   # wieder bestätigt

    s.weg = True
    jetzt[0] += 3601                                                  # länger weg, als eine Bestätigung trägt
    with pytest.raises(KellerwolkeWeg):
        await a.pruefen("kw_app_vertonung")
    await a.schliessen()


async def test_ohne_ausfallzeit_gilt_im_ausfall_nichts():
    s = Schein()
    a = anmeldung(s, merken_s=0.0, ausfall_s=0)
    token, _ = await a.anmelden("chef", "geheim")
    s.weg = True
    with pytest.raises(KellerwolkeWeg):
        await a.pruefen(token)


class ScheinMitBindung(Schein):
    """Kellerwolke ab 0.81: jede Sitzung ist an eine App gebunden ("" für eine volle Sitzung)."""

    def __init__(self):
        super().__init__()
        self.bindung: dict[str, str] = {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/auth/status":
            self.statusabrufe += 1
            token = request.headers.get("x-kellerwolke-sitzung", "")
            name = self.sitzungen.get(token)
            return httpx.Response(200, json={"angemeldet": bool(name), "benutzer": self._b(name) if name else None,
                                             "app": self.bindung.get(token, "")})
        return super().__call__(request)


async def test_fremde_sitzung_gilt_nicht_und_bleibt_gueltig_volle_wird_beendet():
    s = ScheinMitBindung()
    s.sitzungen.update({"tok_assistent": "chef", "tok_voll": "chef"})
    s.bindung.update({"tok_assistent": "Assistent", "tok_voll": ""})
    a = anmeldung(s, app_name=lambda: _wert("Fundus"))
    assert await a.pruefen("tok_assistent") is None
    assert "tok_assistent" in s.sitzungen and "tok_assistent" not in s.abmeldungen     # die andere App bleibt angemeldet
    assert await a.pruefen("tok_voll") is None and "tok_voll" in s.abmeldungen


async def test_im_auftrag_eines_menschen_ueber_eine_andere_app():
    s = ScheinMitBindung()
    s.sitzungen.update({"tok_vertonung": "chef", "tok_andere": "chef"})
    s.bindung.update({"tok_vertonung": "Vertonung", "tok_andere": "Assistent"})
    a = anmeldung(s, app_name=lambda: _wert("Fundus"))
    app = FastAPI()
    app.include_router(anmeldungs_router(a))

    @app.get("/api/v1/zeigen")
    async def zeigen(konto=Depends(angemeldet(a))):
        return {"mensch": konto.mensch, "auftrag": konto.im_auftrag, "app": konto.app}

    @app.get("/api/v1/einstellungen")
    async def einstellungen(konto=Depends(angemeldet(a, nur_menschen=True))):
        return {"konto": konto.name}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        h = {"Authorization": "Bearer kw_app_vertonung", "X-Kellerwolke-Sitzung": "tok_vertonung"}
        assert (await c.get("/api/v1/zeigen", headers=h)).json() == {"mensch": True, "auftrag": "Vertonung", "app": None}
        assert (await c.get("/api/v1/einstellungen", headers=h)).status_code == 403
        # eine Sitzung, die nicht der rufenden App gehört: der Aufruf gilt nur als der der App
        h2 = {"Authorization": "Bearer kw_app_vertonung", "X-Kellerwolke-Sitzung": "tok_andere"}
        assert (await c.get("/api/v1/zeigen", headers=h2)).json() == {"mensch": False, "auftrag": None, "app": "Vertonung"}
        assert not s.abmeldungen
        r = await c.get("/api/v1/zeigen", headers={"X-Kellerwolke-Sitzung": "tok_andere"})
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Kellerwolke-Sitzung"


async def _wert(w):
    return w



async def test_inhalts_cookie_je_app():
    """HELF-56: ein Cookie gilt für den Rechner, nicht für den Port. Zwei Apps auf demselben Rechner setzen darum je ein
    eigenes Inhalts-Cookie; meldet sich jemand an der zweiten an, bleiben Bilder und Töne der ersten erreichbar."""
    assert inhalt_cookie("pinnwand") == "app_inhalt_pinnwand" and inhalt_cookie("Leit Stelle") == "app_inhalt_leit_stelle"
    s = Schein()
    a = anmeldung(s)
    apps = {}
    for kennung in ("pinnwand", "leitstelle"):
        app = FastAPI()
        app.include_router(anmeldungs_router(a, cookie=inhalt_cookie(kennung)))
        lesen = angemeldet(a, cookie=inhalt_cookie(kennung))

        @app.get("/api/v1/inhalt/bild")
        async def bild(konto=Depends(lesen)):
            return {"konto": konto.name}

        apps[kennung] = app
    # ein Browser, zwei Apps auf demselben Rechner: dieselbe Keksdose
    dose = httpx.Cookies()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=apps["pinnwand"]), base_url="http://t", cookies=dose) as p, \
               httpx.AsyncClient(transport=httpx.ASGITransport(app=apps["leitstelle"]), base_url="http://t", cookies=dose) as l:
        token = (await p.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]
        assert (await p.post("/api/v1/anmeldung/zugang", headers={"X-Kellerwolke-Sitzung": token})).status_code == 204
        dose.update(p.cookies)
        assert (await p.get("/api/v1/inhalt/bild")).json() == {"konto": "chef"}
        anderes = (await l.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]
        assert (await l.post("/api/v1/anmeldung/zugang", headers={"X-Kellerwolke-Sitzung": anderes})).status_code == 204
        dose.update(l.cookies)
        assert {"app_inhalt_pinnwand", "app_inhalt_leitstelle"} <= set(dose.keys())
        assert dose.get("app_inhalt_pinnwand") == token                  # nicht überschrieben
        assert (await p.get("/api/v1/inhalt/bild")).json() == {"konto": "chef"}
