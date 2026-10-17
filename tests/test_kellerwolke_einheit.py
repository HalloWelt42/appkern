"""Kellerwolke-Zugang gegen eine nachgestellte Ablage-Schnittstelle (httpx.MockTransport): Fehlerarten, Köpfe,
seitenweises Lesen, Bereiche, Herunterladen ohne halbe Dateien, Ereignisstrom und Neuverbinden."""

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from appkern.kellerwolke import (
    Kellerwolke, KellerwolkeFehler, NichtErreichbar, NichtGefunden, StandVeraltet, pfad_aus,
)

JETZT = datetime(2026, 10, 17, tzinfo=timezone.utc).isoformat()


def knoten_json(name="a.txt", typ="datei", **weiter):
    return {"id": str(uuid4()), "parent_id": None, "name": name, "typ": typ, "pfad": f"Apps/Test/{name}",
            "recht": "schreiben", "etag": "v1", "erstellt_am": JETZT, "geaendert_am": JETZT, **weiter}


def wolke(handler) -> Kellerwolke:
    return Kellerwolke("http://kw.test", "kw_app_geheim", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def test_schluessel_nie_in_der_ausgabe():
    assert "geheim" not in repr(Kellerwolke("http://kw.test", "kw_app_geheim"))


def test_pfad_aus():
    assert pfad_aus("Apps/Test", "Ton", "a b.wav") == "Apps/Test/Ton/a b.wav"
    assert pfad_aus("/x/", "", "y") == "x/y"
    for falsch in (("..",), ("a", "../b"), ("",)):
        with pytest.raises(ValueError):
            pfad_aus(*falsch)


async def test_fehlerarten_und_meldung():
    antworten = {"/api/v1/ablage/pfad": (404, {"detail": "Nicht gefunden"}),
                 "/api/v1/ablage/datei": (412, {"detail": "Die Datei wurde inzwischen geändert"}),
                 "/api/v1/ablage/ich": (503, {"detail": "Speicher nicht verfügbar"})}

    def handler(anfrage: httpx.Request):
        assert anfrage.headers["Authorization"] == "Bearer kw_app_geheim"
        status, inhalt = antworten[anfrage.url.path]
        return httpx.Response(status, json=inhalt)

    kw = wolke(handler)
    with pytest.raises(NichtGefunden):
        await kw.pfad("Apps/Test/fehlt")
    assert await kw.finden("Apps/Test/fehlt") is None
    with pytest.raises(StandVeraltet) as info:
        await kw.schreiben("Apps/Test/a.txt", b"x", stand="v0")
    assert info.value.status == 412 and "geändert" in info.value.meldung
    with pytest.raises(NichtErreichbar):
        await kw.ich()


async def test_ohne_verbindung():
    def handler(anfrage):
        raise httpx.ConnectError("weg", request=anfrage)

    with pytest.raises(NichtErreichbar):
        await wolke(handler).ich()


async def test_schreiben_aus_datei_mit_laenge_und_stand(tmp_path: Path):
    datei = tmp_path / "ton.wav"
    datei.write_bytes(b"RIFF" + b"\x00" * 5000)
    gesehen = {}

    async def handler(anfrage: httpx.Request):
        gesehen["kopf"] = dict(anfrage.headers)
        gesehen["koerper"] = await anfrage.aread()
        gesehen["pfad"] = anfrage.url.params["pfad"]
        return httpx.Response(200, json=knoten_json("ton.wav", groesse=5004))

    k = await Kellerwolke("http://kw.test", "s", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                          stueck=1000).schreiben("Apps/Test/ton.wav", datei, stand="v7", inhaltstyp="audio/wav")
    assert k.groesse == 5004 and gesehen["pfad"] == "Apps/Test/ton.wav"
    assert gesehen["koerper"] == datei.read_bytes()
    assert gesehen["kopf"]["content-length"] == "5004" and gesehen["kopf"]["if-match"] == '"v7"'
    assert gesehen["kopf"]["content-type"] == "audio/wav"


async def test_nur_neu_setzt_if_none_match():
    def handler(anfrage):
        assert anfrage.headers["if-none-match"] == "*" and "if-match" not in anfrage.headers
        return httpx.Response(200, json=knoten_json())

    await wolke(handler).schreiben("Apps/Test/a.txt", b"x", nur_neu=True)


async def test_alle_kinder_seitenweise():
    gesamt = [knoten_json(f"d{i:04}.txt") for i in range(1200)]

    def handler(anfrage):
        ab, anzahl = int(anfrage.url.params["ab"]), int(anfrage.url.params["anzahl"])
        return httpx.Response(200, json=gesamt[ab:ab + anzahl])

    namen = [k.name async for k in wolke(handler).alle_kinder(uuid4())]
    assert len(namen) == 1200 and namen[0] == "d0000.txt" and namen[-1] == "d1199.txt"


async def test_lesen_mit_bereich():
    def handler(anfrage):
        assert anfrage.headers["range"] == "bytes=10-19"
        return httpx.Response(206, content=b"0123456789")

    assert b"".join([d async for d in wolke(handler).lesen(uuid4(), start=10, ende=19)]) == b"0123456789"


async def test_herunterladen_nie_halb(tmp_path: Path):
    class Abbruch(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"erster Teil"
            raise httpx.ReadError("Verbindung weg")

    def handler(anfrage):
        return httpx.Response(200, stream=Abbruch())

    ziel = tmp_path / "unter" / "datei.bin"
    with pytest.raises(NichtErreichbar):
        await wolke(handler).herunterladen(uuid4(), ziel)
    assert not ziel.exists() and list(ziel.parent.iterdir()) == []

    def gut(anfrage):
        return httpx.Response(200, content=b"vollstaendig")

    assert (await wolke(gut).herunterladen(uuid4(), ziel)).read_bytes() == b"vollstaendig"


def sse(*staende, ende=None) -> bytes:
    teile = [": lebt\n\n"]
    for bis in staende:
        daten = {"eintraege": [{"seq": bis, "knoten_id": str(uuid4()), "typ": "erstellt", "zeit": JETZT}],
                 "bis": bis, "luecke": False}
        teile.append(f"id: {bis}\nevent: aenderungen\ndata: {json.dumps(daten)}\n\n")
    if ende:
        teile.append(f"event: ende\ndata: {ende}\n\n")
    return "".join(teile).encode()


async def test_ereignisse_lesen_und_ende():
    def handler(anfrage):
        return httpx.Response(200, content=sse(5, 7, ende="Kein Recht mehr"),
                              headers={"content-type": "text/event-stream"})

    gesehen = []
    with pytest.raises(KellerwolkeFehler, match="Kein Recht mehr"):
        async for stand in wolke(handler).ereignisse(uuid4(), 0):
            gesehen.append(stand.bis)
    assert gesehen == [5, 7]


async def test_beobachten_verbindet_neu_und_setzt_fort(monkeypatch):
    import appkern.kellerwolke.zugang as zugang

    async def sofort(_s):
        return None

    monkeypatch.setattr(zugang.asyncio, "sleep", sofort)
    runden = []

    def handler(anfrage):
        seit = int(anfrage.url.params["seit"])
        runden.append(seit)
        if len(runden) == 1:
            return httpx.Response(200, content=sse(3), headers={"content-type": "text/event-stream"})
        if len(runden) == 2:
            raise httpx.ConnectError("Pi startet neu", request=anfrage)
        return httpx.Response(200, content=sse(9), headers={"content-type": "text/event-stream"})

    gesehen = []
    async for stand in wolke(handler).beobachten(uuid4(), 0):
        gesehen.append(stand.bis)
        if len(gesehen) == 2:
            break
    assert gesehen == [3, 9]
    assert runden == [0, 3, 3]  # nach dem Abbruch am letzten Stand fortgesetzt
