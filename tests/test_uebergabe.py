"""Übergabe zwischen Geräten (RAD-18): Vermittler und WebSocket"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Literal, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from appkern.anmeldung.dienst import Konto
from appkern.uebergabe import Anmeldung, Vermittler, uebergabe_router


class Zustand(BaseModel):
    titel: str
    laeuft: bool = False


class Paket(BaseModel):
    art: Literal["sender", "folge"]
    kennung: str
    stelle: float = 0


class Leitung:
    def __init__(self) -> None:
        self.post: list[dict[str, Any]] = []

    async def send_json(self, data: Any) -> None:
        self.post.append(data)

    def letzte(self, typ: str) -> Optional[dict[str, Any]]:
        return next((n for n in reversed(self.post) if n["typ"] == typ), None)


def gruss(kennung: str, art: str = "rechner") -> Anmeldung:
    return Anmeldung(typ="anmelden", id=kennung, geraet=f"b-{kennung}", name=kennung.title(), art=art)


def lauf(f):
    return asyncio.run(f())


def test_geraete_eines_kontos_sehen_einander_andere_nicht():
    async def f():
        v = Vermittler(Zustand, Paket)
        a, b, c = Leitung(), Leitung(), Leitung()
        await v.beitreten(a, gruss("a"), raum="k1")
        await v.beitreten(b, gruss("b", "telefon"), raum="k1")
        await v.beitreten(c, gruss("c"), raum="k2")
        assert [g["id"] for g in a.letzte("geraete")["geraete"]] == ["a", "b"]
        assert [g["id"] for g in c.letzte("willkommen")["geraete"]] == ["c"]
        await v.behandeln("a", {"typ": "zustand", "zustand": {"titel": "MANGORADIO", "laeuft": True}})
        assert b.letzte("zustand") == {"typ": "zustand", "id": "a", "zustand": {"titel": "MANGORADIO", "laeuft": True}}
        assert c.letzte("zustand") is None
    lauf(f)


def test_uebergabe_und_befehl_nur_im_eigenen_raum():
    async def f():
        v = Vermittler(Zustand, Paket)
        a, b, c = Leitung(), Leitung(), Leitung()
        await v.beitreten(a, gruss("a"), raum="k1")
        await v.beitreten(b, gruss("b"), raum="k1")
        await v.beitreten(c, gruss("c"), raum="k2")
        await v.behandeln("a", {"typ": "uebergabe", "an": "b", "paket": {"art": "folge", "kennung": "17", "stelle": 42.5}})
        assert b.letzte("uebergabe")["paket"] == {"art": "folge", "kennung": "17", "stelle": 42.5}
        assert b.letzte("uebergabe")["von"] == "a"
        await v.behandeln("a", {"typ": "befehl", "an": "c", "aktion": "abgeben"})
        assert c.letzte("befehl") is None
        assert a.letzte("fehler")["text"] == "Das Gerät ist nicht mehr da"
    lauf(f)


def test_paket_wird_mit_dem_modell_der_app_geprueft():
    async def f():
        v = Vermittler(Zustand, Paket)
        a, b = Leitung(), Leitung()
        await v.beitreten(a, gruss("a"), raum="k1")
        await v.beitreten(b, gruss("b"), raum="k1")
        await v.behandeln("a", {"typ": "uebergabe", "an": "b", "paket": {"art": "film", "kennung": "1"}})
        assert b.letzte("uebergabe") is None
        assert a.letzte("fehler")["text"] == "Nachricht nicht verstanden"
    lauf(f)


def test_verlassen_und_name_fuer_alle_fenster_des_browsers():
    async def f():
        v = Vermittler(Zustand, Paket)
        a, a2, b = Leitung(), Leitung(), Leitung()
        await v.beitreten(a, gruss("a"), raum="k1")
        await v.beitreten(a2, Anmeldung(typ="anmelden", id="a2", geraet="b-a", name="A"), raum="k1")
        await v.beitreten(b, gruss("b"), raum="k1")
        await v.behandeln("a", {"typ": "name", "name": "  Rechner   Küche "})
        namen = {g["id"]: g["name"] for g in b.letzte("geraete")["geraete"]}
        assert namen == {"a": "Rechner Küche", "a2": "Rechner Küche", "b": "B"}
        await v.verlassen("a", Leitung())               # fremde Verbindung: nichts
        assert len(v.geraete("k1")) == 3
        await v.verlassen("a", a)
        assert [g.id for g in v.geraete("k1")] == ["a2", "b"]
    lauf(f)


class Pruefer:
    async def pruefen(self, token: str) -> Optional[Konto]:
        return Konto(id="k1", name="Nutzer") if token == "gut" else None


def test_websocket_meldet_an_und_weist_ohne_token_ab():
    app = FastAPI()
    app.include_router(uebergabe_router(Vermittler(Zustand, Paket), Pruefer()))     # type: ignore[arg-type]
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/geraete/ws") as ws:
            ws.send_text(json.dumps({"typ": "anmelden", "token": "schlecht", "id": "x", "geraet": "g"}))
            try:
                ws.receive_text()
                assert False, "ohne gültigen Token keine Antwort"
            except Exception:
                pass
        with client.websocket_connect("/api/v1/geraete/ws") as ws:
            ws.send_text(json.dumps({"typ": "anmelden", "token": "gut", "id": "x", "geraet": "g", "name": "Rechner"}))
            assert ws.receive_json()["typ"] == "willkommen"
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
