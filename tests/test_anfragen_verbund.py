"""Verbund: Begleitdateien, Anfragen mit dem Abholer, Anmeldung nur für die App und Dateiwahl gegen eine echte
Kellerwolke (ab 0.81). Braucht in `.env.test` (nicht im Repo) Adresse, App-Schlüssel und ein Testkonto, dem der
Schlüssel gehört; ohne wird übersprungen. Jeder Lauf legt seine Ordner am Ende in den Papierkorb und beendet seine
Sitzungen."""

import asyncio
import secrets

import httpx
import pytest
from test_anmeldung_verbund import W

from appkern.anfragen import Abholer, Angebot, AnfrageEingabe
from appkern.anmeldung import Anmeldung
from appkern.auftraege import Art, Auftraege, Kontext
from appkern.datenbank import Datenbank
from appkern.kellerwolke import Aktion, Kellerwolke, pfad_aus

pytestmark = pytest.mark.skipif(
    not all(W.get(k) for k in ("KELLERWOLKE_ADRESSE", "KELLERWOLKE_SCHLUESSEL", "KELLERWOLKE_KENNUNG", "KELLERWOLKE_PASSWORT")),
    reason="keine Test-Kellerwolke mit Schlüssel und Konto eingerichtet (.env.test)")

PROBE = Aktion(kennung="probe", titel="Probe", symbol="fa-flask", typen=("audio/*",), rolle="probe")


@pytest.fixture
async def verbund():
    """Zugang der App, Sitzung des Kontos in der Kellerwolke selbst und ein Ordner außerhalb der Rechte der App."""
    adresse = W["KELLERWOLKE_ADRESSE"]
    kw = Kellerwolke(adresse, W["KELLERWOLKE_SCHLUESSEL"])
    ich = await kw.ich()
    client = httpx.AsyncClient(base_url=adresse)
    r = await client.post("/api/v1/auth/login", json={"kennung": W["KELLERWOLKE_KENNUNG"], "passwort": W["KELLERWOLKE_PASSWORT"]})
    sitzung = {"X-Kellerwolke-Sitzung": r.json()["token"]}
    name = f"Appkern Probe {secrets.token_hex(3)}"
    ordner = (await client.post("/api/v1/dateien/ordner", json={"name": name, "parent_id": None}, headers=sitzung)).json()
    ton = (await client.post("/api/v1/dateien/upload", files={"datei": ("Stimme.wav", b"RIFF-probe", "audio/wav")},
                             data={"parent_id": ordner["id"]}, headers=sitzung)).json()
    yield kw, ich, client, sitzung, ordner, ton
    await client.delete(f"/api/v1/dateien/{ordner['id']}", headers=sitzung)
    await client.post("/api/v1/auth/logout", headers=sitzung)
    await client.aclose()
    await kw.schliessen()


async def test_begleiter_im_eigenen_zweig(verbund):
    kw, ich, *_ = verbund
    lauf = await kw.ordner(pfad_aus(ich.zweig, f"lauf-{secrets.token_hex(4)}"))
    try:
        ton = await kw.schreiben(pfad_aus(lauf.pfad, "Runde.wav"), b"RIFF-runde")
        b = await kw.begleiter_schreiben(ton.id, "transkript", ".transkript.json", b"{}", inhaltstyp="application/json")
        assert (b.name, b.rolle, b.haupt_id) == ("Runde.transkript.json", "transkript", ton.id)
        neu = await kw.begleiter_schreiben(ton.id, "transkript", ".transkript.json", b'{"v":2}', stand=b.etag)
        assert neu.id == b.id
        assert [x.name for x in await kw.begleiter(ton.id)] == ["Runde.transkript.json"]
        archiv = await kw.ordner(pfad_aus(lauf.pfad, "Archiv"))
        await kw.umziehen(b.id, archiv.id)                       # ein Mitglied verschiebt die Gruppe
        assert sorted(k.name for k in await kw.kinder(archiv.id)) == ["Runde.transkript.json", "Runde.wav"]
        geloest = await kw.begleiter_loesen(b.id)
        assert geloest.haupt_id is None and await kw.begleiter(ton.id) == []
    finally:
        await kw.loeschen(lauf.id)


async def test_anfrage_aus_der_kellerwolke_wird_zum_begleiter(verbund, tmp_path):
    kw, ich, client, sitzung, _, ton = verbund

    optionen = []

    async def probe(k: Kontext):
        optionen.append(k.eingabe.optionen)
        zugang = kw.mit_anfrage(k.eingabe.anfrage_id)
        inhalt = b"".join([d async for d in zugang.lesen(k.eingabe.knoten_id)])
        await k.fortschritt(0.5, "gelesen")
        b = await zugang.begleiter_schreiben(k.eingabe.knoten_id, "probe", ".probe.txt", inhalt[::-1])
        return {"ergebnis_id": str(b.id)}

    db = Datenbank(tmp_path / "probe.sqlite")
    await db.oeffnen()
    auftraege = Auftraege(db, [Art(name="probe", titel="Probe", arbeit=probe, eingabe=AnfrageEingabe)])
    abholer = Abholer([Angebot(PROBE, auftrag="probe")], auftraege, lambda: kw, lambda: None)
    await auftraege.starten()
    await abholer.starten()
    await abholer.verbunden()
    try:
        aktion = None
        for _ in range(50):                          # das Melden läuft im Hintergrund an
            aktionen = (await client.get(f"/api/v1/dateien/{ton['id']}/aktionen", headers=sitzung)).json()
            aktion = next((a for a in aktionen if a["kennung"] == "probe"), None)
            if aktion:
                break
            await asyncio.sleep(0.1)
        assert aktion and aktion["erreichbar"]
        neu = (await client.post("/api/v1/anfragen", json={"zugang_id": aktion["zugang_id"], "aktion": "probe",
                                                           "knoten_id": ton["id"]}, headers=sitzung)).json()["anfrage"]
        stand = None
        for _ in range(100):
            stand = next(a for a in (await client.get("/api/v1/anfragen", headers=sitzung)).json() if a["id"] == neu["id"])
            if stand["zustand"] in ("fertig", "fehler"):
                break
            await asyncio.sleep(0.1)
        assert stand["zustand"] == "fertig", stand
        assert stand["ergebnis_name"] == "Stimme.probe.txt"
        # weitergegeben (hier an sich selbst) kommen die Optionen bis in den Auftrag
        eigen = await kw.schreiben(pfad_aus(ich.zweig, f"weiter-{secrets.token_hex(3)}.wav"), b"RIFF-weiter")
        weiter = (await kw.weitergeben(ich.app, "probe", eigen.id, {"sprache": "en"})).anfrage
        assert weiter.optionen == {"sprache": "en"}
        for _ in range(100):
            if (await kw.anfrage(weiter.id)).zustand in ("fertig", "fehler"):
                break
            await asyncio.sleep(0.1)
        assert optionen == [{}, {"sprache": "en"}]
        await kw.loeschen(eigen.id)
        # danach kommt die App nicht mehr an die Datei
        with pytest.raises(Exception):
            await kw.mit_anfrage(neu["id"]).knoten(ton["id"])
        # ein Auftrag, der nur das Recht einer Anfrage nutzt, schließt sie nicht (etwa Arbeit in einer geöffneten Datei)
        await kw.aktionen_melden([PROBE, Aktion(kennung="ansehen", titel="Ansehen", symbol="fa-eye", typen=("audio/*",),
                                                art="oeffnen")], "http://127.0.0.1:1")
        offen = (await client.post("/api/v1/anfragen", json={"zugang_id": aktion["zugang_id"], "aktion": "ansehen",
                                                             "knoten_id": ton["id"]}, headers=sitzung)).json()["anfrage"]
        await kw.anfrage_annehmen(offen["id"])
        fremd = await auftraege.einreihen("probe", AnfrageEingabe(anfrage_id=offen["id"], knoten_id=ton["id"], aktion="probe"))
        for _ in range(100):
            if (await auftraege.holen(fremd.id)).zustand in ("fertig", "fehler"):
                break
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.3)
        assert (await kw.anfrage(offen["id"])).zustand == "laeuft"
    finally:
        await abholer.stoppen()
        await auftraege.stoppen()
        await db.schliessen()


async def test_anmeldung_gilt_nur_fuer_die_app_und_waehlt(verbund):
    kw, ich, client, sitzung, ordner, ton = verbund

    async def name():
        return ich.app

    a = Anmeldung(W["KELLERWOLKE_ADRESSE"], lambda: {W["KELLERWOLKE_KENNUNG"]}, merken_s=0.0, app_name=name)
    token, _ = await a.anmelden(W["KELLERWOLKE_KENNUNG"], W["KELLERWOLKE_PASSWORT"])
    try:
        app = {"X-Kellerwolke-Sitzung": token}
        assert (await client.get("/api/v1/auth/status", headers=app)).json()["app"] == ich.app
        assert (await client.get("/api/v1/dateien", headers=app)).status_code == 403
        # die volle Sitzung der Kellerwolke gilt in der App nicht und wird von ihr beendet
        r = await client.post("/api/v1/auth/login", json={"kennung": W["KELLERWOLKE_KENNUNG"], "passwort": W["KELLERWOLKE_PASSWORT"]})
        voll = r.json()["token"]
        assert await a.pruefen(voll) is None
        assert (await client.get("/api/v1/auth/status", headers={"X-Kellerwolke-Sitzung": voll})).json()["angemeldet"] is False
        # Dateiwahl mit der Anmeldung an der App
        seite = await kw.wahl(token, ordner["id"])
        assert [k.name for k in seite.kette][-1] == ordner["name"] and [e.name for e in seite.eintraege] == ["Stimme.wav"]
        await kw.aktionen_melden([PROBE])
        neu = await kw.waehlen(token, ton["id"], "probe")
        assert neu.anfrage.zustand == "wartet" and neu.anfrage.app == ich.app
        await client.delete(f"/api/v1/anfragen/{neu.anfrage.id}", headers=sitzung)
    finally:
        await kw.aktionen_melden([])
        await a.abmelden(token)
        await a.schliessen()
