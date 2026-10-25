"""Mitteilungen aufs Gerät: Schlüssel entsteht einmal und bleibt, Abo je Gerät, Versand verschlüsselt (das nachgestellte
Gerät entschlüsselt ihn wirklich) und unterschrieben, ein Abo, das es nicht mehr gibt, geht; Wege nur für Menschen."""

import base64
import json
from pathlib import Path

import http_ece
import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from appkern.app import Geruest
from appkern.push import Mitteilung
from test_geruest import ProbeEinstellungen, Wolke


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


class Geraet:
    """Ein Browser mit Abo: eigener Schlüssel und Geheimnis, sammelt, was ankommt (entschlüsselt)."""

    def __init__(self, endpunkt: str) -> None:
        self.endpunkt = endpunkt
        self.schluessel = ec.generate_private_key(ec.SECP256R1())
        self.auth = b"0123456789abcdef"
        self.angekommen: list[dict] = []
        self.koepfe: list[httpx.Headers] = []

    def abo(self) -> dict:
        punkt = self.schluessel.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        return {"endpoint": self.endpunkt, "keys": {"p256dh": b64(punkt), "auth": b64(self.auth)}}

    def empfangen(self, request: httpx.Request) -> None:
        self.koepfe.append(request.headers)
        klar = http_ece.decrypt(request.content, private_key=self.schluessel, auth_secret=self.auth, version="aes128gcm")
        self.angekommen.append(json.loads(klar))


class Dienste(Wolke):
    """Kellerwolke wie im Gerüst-Test, dazu ein Push-Dienst mit zwei Geräten; das zweite gibt es nicht mehr (410)."""

    def __init__(self) -> None:
        super().__init__()
        self.telefon = Geraet("https://push.test/abo/telefon")
        self.altes = Geraet("https://push.test/abo/altes")

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "push.test":
            if request.url.path.endswith("/altes"):
                return httpx.Response(410)
            self.telefon.empfangen(request)
            return httpx.Response(201)
        return super().__call__(request)


@pytest.fixture
async def umgebung(tmp_path: Path):
    dienste = Dienste()
    geruest = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=tmp_path / "daten",
                      einstellungen=ProbeEinstellungen, push=True, transport=httpx.MockTransport(dienste))
    app = geruest.fastapi()
    await geruest.starten()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/einrichtung", json={"kellerwolke_adresse": "http://kw.test", "kellerwolke_schluessel": "kw_app_gut"})
        assert r.status_code == 200, r.text
        token = (await c.post("/api/v1/anmeldung", json={"kennung": "chef", "passwort": "geheim"})).json()["token"]
        yield geruest, dienste, c, {"X-Kellerwolke-Sitzung": token}
    await geruest.stoppen()


async def test_abo_versand_und_wegfall(umgebung):
    geruest, dienste, c, h = umgebung
    assert (await c.get("/api/v1/push/schluessel")).status_code == 401
    schluessel = (await c.get("/api/v1/push/schluessel", headers=h)).json()["schluessel"]
    assert schluessel == await geruest.push.oeffentlich() and len(base64.urlsafe_b64decode(schluessel + "=")) == 65

    for g, name in ((dienste.telefon, "iPhone, Web-App"), (dienste.altes, "Altes Telefon")):
        r = await c.post("/api/v1/push/abo", headers=h, json={"abo": g.abo(), "geraet": name})
        assert r.status_code == 200 and r.json()["name"] == name
    assert [g["name"] for g in (await c.get("/api/v1/push/geraete", headers=h)).json()] == ["iPhone, Web-App", "Altes Telefon"]

    v = await geruest.push.senden("1", Mitteilung(titel="Pinnwand", text="HAUS-3 ist dir zugewiesen", url="/board/haus/3",
                                                  tag="h-1", dringend=True))
    assert (v.zugestellt, v.entfernt, v.fehler) == (1, 1, 0)
    assert dienste.telefon.angekommen == [{"titel": "Pinnwand", "text": "HAUS-3 ist dir zugewiesen", "url": "/board/haus/3",
                                           "tag": "h-1", "dringend": True, "ttl": 86400}]
    kopf = dienste.telefon.koepfe[0]
    assert kopf["authorization"].startswith("vapid t=") and f"k={schluessel}" in kopf["authorization"]
    assert (kopf["content-encoding"], kopf["urgency"], kopf["ttl"]) == ("aes128gcm", "high", "86400") and len(kopf["topic"]) == 32
    # das alte Abo gibt es nicht mehr: es ist entfernt, das Telefon hat jetzt einen Zeitpunkt
    [telefon] = (await c.get("/api/v1/push/geraete", headers=h)).json()
    assert telefon["name"] == "iPhone, Web-App" and telefon["zuletzt"]

    assert (await c.post("/api/v1/push/probe", headers=h)).json() == {"zugestellt": 1, "entfernt": 0, "fehler": 0}
    assert dienste.telefon.angekommen[-1]["text"] == "Probe: Mitteilungen kommen auf diesem Gerät an."
    assert (await c.delete(f"/api/v1/push/geraete/{telefon['id']}", headers=h)).json() == {"entfernt": True}
    assert (await c.get("/api/v1/push/geraete", headers=h)).json() == []
    assert (await geruest.push.senden("1", Mitteilung(titel="Leer"))).zugestellt == 0


async def test_schluessel_bleibt_und_dienst_im_browser(umgebung, tmp_path: Path):
    geruest, _, c, h = umgebung
    erster = await geruest.push.oeffentlich()
    neu = Geruest(name="Probe", kennung="probe", rolle="probiert", fassung="0.1.0", daten=geruest.daten,
                  einstellungen=ProbeEinstellungen, push=True)
    async with neu.db:
        assert await neu.push.oeffentlich() == erster               # aus der Datenbank, nicht neu
    r = await c.get("/api/v1/push/dienst.js")
    assert r.status_code == 200 and r.headers["service-worker-allowed"] == "/" and "showNotification" in r.text
    r = await c.post("/api/v1/push/abo", headers=h, json={"abo": {"endpoint": "http://unsicher.test/x",
                                                                   "keys": {"p256dh": "a" * 87, "auth": "b" * 22}}})
    assert r.status_code == 422                                      # nur Abos über HTTPS
