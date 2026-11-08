"""Anmeldeposten (hier mit der Kennung des Vorbaus am Mac) gegen eine nachgestellte Kellerwolke: Seitenaufrufe ohne Anmeldung landen auf der Anmeldeseite,
Schnittstellen bekommen 401; eine Anmeldung gilt nur für den Vorbau und nur für erlaubte Konten; Fehlversuche bremsen;
fällt die Kellerwolke aus, trägt eine bestätigte Sitzung weiter, eine unbestätigte nicht."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from appkern.posten.dienst import Einstellungen, erstellen
from appkern.posten.kellerwolke import Kellerwolke

KEKS = "vorbau_sitzung"

KONTEN = {"alpha": ("richtig", "admin", 1), "kind": ("auch", "mitglied", 2)}


class ScheinKellerwolke:
    def __init__(self) -> None:
        self.sitzungen: dict[str, tuple[str, str]] = {}      # token -> (konto, app)
        self.aus = False
        self.abgemeldet: list[str] = []

    def __call__(self, r: httpx.Request) -> httpx.Response:
        if self.aus:
            raise httpx.ConnectError("weg", request=r)
        if r.url.path == "/api/v1/auth/login":
            import json
            d = json.loads(r.content)
            konto = KONTEN.get(d["kennung"])
            if konto is None or konto[0] != d["passwort"]:
                return httpx.Response(401, json={"detail": "Anmeldung fehlgeschlagen"})
            token = f"t{len(self.sitzungen) + 1}"
            self.sitzungen[token] = (d["kennung"], d.get("fuer_app") or "")
            return httpx.Response(200, json={"token": token, "benutzer": {"id": konto[2], "name": d["kennung"], "rolle": konto[1]}})
        token = r.headers.get("x-kellerwolke-sitzung", "")
        if r.url.path == "/api/v1/auth/status":
            if token not in self.sitzungen:
                return httpx.Response(200, json={"angemeldet": False})
            name, app = self.sitzungen[token]
            return httpx.Response(200, json={"angemeldet": True, "app": app,
                                             "benutzer": {"id": KONTEN[name][2], "name": name, "rolle": KONTEN[name][1]}})
        if r.url.path == "/api/v1/auth/logout":
            self.sitzungen.pop(token, None)
            self.abgemeldet.append(token)
            return httpx.Response(204)
        return httpx.Response(404)


@pytest.fixture
def aufbau():
    def bauen(**einstellungen):
        schein = ScheinKellerwolke()
        uhr = [1000.0]
        kw = Kellerwolke("https://kw.test", None, "Vorbau Mac", merken_s=60,
                         client=httpx.AsyncClient(base_url="https://kw.test", transport=httpx.MockTransport(schein)), uhr=lambda: uhr[0])
        e = Einstellungen(kellerwolke="https://kw.test", kennung="vorbau", app="Vorbau Mac", **einstellungen)
        c = TestClient(erstellen(e, kw), base_url="https://192.168.178.45:8459", follow_redirects=False)
        return c, schein, uhr
    return bauen


SEITE = {"accept": "text/html,application/xhtml+xml", "x-forwarded-method": "GET", "x-forwarded-uri": "/vorgaenge?seite=2"}


def anmelden(c, kennung="alpha", passwort="richtig", ziel="/vorgaenge?seite=2"):
    return c.post("/_vorbau/anmelden", data={"kennung": kennung, "passwort": passwort, "ziel": ziel}, headers={"x-vorbau-app": "Zusage"})


def test_ohne_anmeldung_seite_zur_anmeldung_schnittstelle_401(aufbau):
    c, _, _ = aufbau()
    r = c.get("/_vorbau/pruefen", headers=SEITE)
    assert r.status_code == 302 and r.headers["location"] == "/_vorbau/anmelden?ziel=%2Fvorgaenge%3Fseite%3D2"
    r = c.get("/_vorbau/pruefen", headers={"accept": "application/json", "x-forwarded-method": "GET", "x-forwarded-uri": "/api/x"})
    assert r.status_code == 401
    r = c.get("/_vorbau/pruefen", headers={**SEITE, "x-forwarded-method": "POST"})
    assert r.status_code == 401, "nur ein Seitenaufruf wird umgeleitet"
    seite = c.get("/_vorbau/anmelden?ziel=/x", headers={"x-vorbau-app": "Zusage"})
    assert seite.status_code == 200 and "<h1>Zusage</h1>" in seite.text and 'type="password"' in seite.text


def test_anmeldung_setzt_sicheren_keks_und_gilt(aufbau):
    c, schein, _ = aufbau()
    r = anmelden(c)
    assert r.status_code == 303 and r.headers["location"] == "/vorgaenge?seite=2"
    keks = r.headers["set-cookie"]
    assert keks.startswith(f"{KEKS}=") and "Secure" in keks and "HttpOnly" in keks and "SameSite=lax" in keks
    assert list(schein.sitzungen.values()) == [("alpha", "Vorbau Mac")], "die Sitzung gilt nur für den Vorbau"
    c.cookies.set(KEKS, r.cookies[KEKS])
    r = c.get("/_vorbau/pruefen", headers=SEITE)
    assert r.status_code == 200 and r.headers["x-vorbau-konto"] == "alpha"


def test_falsches_passwort_und_bremse(aufbau):
    c, _, _ = aufbau(fehlversuche=3)
    for _ in range(3):
        r = anmelden(c, passwort="falsch")
        assert r.status_code == 401 and "stimmen nicht" in r.text and KEKS not in r.headers.get("set-cookie", "")
    r = anmelden(c)
    assert r.status_code == 429 and "Zu viele" in r.text, "auch das richtige Passwort wartet, bis die Bremse löst"


def test_nur_erlaubte_konten(aufbau):
    c, schein, _ = aufbau()
    r = anmelden(c, "kind", "auch")
    assert r.status_code == 403 and "ist hier nicht zugelassen" in r.text and schein.sitzungen == {}, "die Sitzung ist sofort beendet"
    c2, _, _ = aufbau(erlaubt="kind")
    assert anmelden(c2, "kind", "auch").status_code == 303
    assert anmelden(c2).status_code == 403, "mit Liste gilt nur die Liste"


def test_fremde_und_volle_sitzungen_gelten_nicht(aufbau):
    c, schein, _ = aufbau()
    schein.sitzungen["voll"] = ("alpha", "")
    schein.sitzungen["andere"] = ("alpha", "Assistent")
    for token in ("voll", "andere", "erfunden"):
        c.cookies.set(KEKS, token)
        assert c.get("/_vorbau/pruefen", headers=SEITE).status_code == 302, token


def test_ausfall_der_kellerwolke(aufbau):
    c, schein, uhr = aufbau()
    token = anmelden(c).cookies[KEKS]
    schein.aus = True
    uhr[0] += 3600                                              # Merker abgelaufen, Kellerwolke weg
    c.cookies.set(KEKS, token)
    assert c.get("/_vorbau/pruefen", headers=SEITE).status_code == 200, "bestätigte Sitzung trägt durch den Ausfall"
    c.cookies.set(KEKS, "nie-bestaetigt")
    assert c.get("/_vorbau/pruefen", headers=SEITE).status_code == 503
    assert anmelden(c).status_code == 503 and "nicht erreichbar" in anmelden(c).text
    uhr[0] += 25 * 3600
    c.cookies.set(KEKS, token)
    assert c.get("/_vorbau/pruefen", headers=SEITE).status_code == 503, "nach einem Tag ohne Bestätigung nicht mehr"


def test_ziel_bleibt_auf_dem_rechner(aufbau):
    c, _, _ = aufbau()
    for boese in ("//boese.example/x", "https://boese.example", "boese", "/_vorbau/anmelden"):
        assert anmelden(c, ziel=boese).headers["location"] == "/", boese


def test_abmelden(aufbau):
    c, schein, _ = aufbau()
    token = anmelden(c).cookies[KEKS]
    c.cookies.set(KEKS, token)
    r = c.post("/_vorbau/abmelden")
    assert r.status_code == 303 and r.headers["location"] == "/_vorbau/anmelden" and token in schein.abgemeldet
    assert f'{KEKS}=""' in r.headers["set-cookie"] or "Max-Age=0" in r.headers["set-cookie"]


def test_statisch_ohne_pfadausbruch(aufbau):
    c, _, _ = aufbau()
    assert c.get("/_vorbau/statisch/barlow-latin-400-normal.woff2").status_code == 200
    assert c.get("/_vorbau/statisch/..%2F..%2Fposten.py").status_code == 404


def test_eigene_kennung_ergibt_keks_pfad_und_koepfe():
    """Zusage auf dem Pi: eigener Posten, nichts heißt dort Vorbau."""
    e = Einstellungen(kellerwolke="https://kw.test", kennung="zusage", app="Zusage")
    assert (e.keks, e.pfad, e.kopf("App"), e.kopf("Konto")) == ("zusage_sitzung", "/_zusage", "X-Zusage-App", "X-Zusage-Konto")
    c = TestClient(erstellen(e), base_url="https://192.168.178.49:8459", follow_redirects=False)
    r = c.get("/_zusage/pruefen", headers=SEITE)
    assert r.status_code == 302 and r.headers["location"].startswith("/_zusage/anmelden?ziel=")
    seite = c.get("/_zusage/anmelden")
    assert "<h1>Zusage</h1>" in seite.text and 'action="/_zusage/anmelden"' in seite.text and "/_zusage/statisch/barlow" in seite.text
    assert c.get("/_zusage/statisch/barlow-latin-400-normal.woff2").status_code == 200


def test_name_der_app_mit_umlaut_aus_dem_kopf(aufbau):
    """Der Vorschaltdienst schickt den Namen als UTF-8; die Seite zeigt ihn richtig (NAME-10)."""
    c, _, _ = aufbau()
    seite = c.get("/_vorbau/anmelden?ziel=/x", headers={"x-vorbau-app": "BücherFreunde".encode("utf-8")})
    assert "BücherFreunde" in seite.text and "BÃ" not in seite.text
