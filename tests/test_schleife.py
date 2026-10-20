"""Werkzeugschleife gegen eine nachgestellte Fassade: mehrere Runden, lesende Werkzeuge nebeneinander und die übrigen
der Reihe nach, Ergebnisse in der Reihenfolge der Aufrufe, falsche Argumente zurück ans Modell, Nachladen,
Rundengrenze, Warten, Bilder erzeugen als Strom."""

import asyncio
import base64
import json

import httpx
from pydantic import BaseModel

from appkern.leitstelle import Bilder, Leitstelle, Nachricht, Wartet
from appkern.leitstelle.schleife import (
    Antwort, Aufruf, Ergebnis, Grenze, ModellWerkzeug, RundeEnde, Schleife, TextStueck, Warten, WerkzeugErgebnis,
)


def leitstelle(handler) -> Leitstelle:
    return Leitstelle("http://ls.test", "ls_geheim", "Assistent", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def teil(delta: dict, ende: str | None = None) -> str:
    return f"data: {json.dumps({'model': 'gross', 'choices': [{'index': 0, 'delta': delta, 'finish_reason': ende}]})}\n\n"


def aufrufe(*liste: tuple[str, str, dict]) -> str:
    return "".join(teil({"tool_calls": [{"index": i, "id": k, "function": {"name": n, "arguments": json.dumps(a)}}]})
                   for i, (k, n, a) in enumerate(liste)) + teil({}, "tool_calls") + "data: [DONE]\n\n"


def text(t: str) -> str:
    return teil({"content": t}) + teil({}, "stop") + "data: [DONE]\n\n"


class Fassade:
    """Spielt die Runden der Reihe nach ab und merkt sich, was das Modell gesehen hat."""

    def __init__(self, *runden: str) -> None:
        self.runden = list(runden)
        self.gesehen: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.gesehen.append(json.loads(request.content))
        return httpx.Response(200, content=self.runden.pop(0).encode(), headers={"content-type": "text/event-stream"})


class Ort(BaseModel):
    ort: str


def wetter(protokoll: list[str], pause: float = 0.0) -> ModellWerkzeug:
    async def ausfuehren(a: Ort) -> WerkzeugErgebnis:
        protokoll.append(f"anfang {a.ort}")
        await asyncio.sleep(pause)
        protokoll.append(f"ende {a.ort}")
        return WerkzeugErgebnis(text=f"{a.ort}: 11 Grad", daten={"ort": a.ort})

    return ModellWerkzeug("get_weather", "Wetter an einem Ort. Wann: bei Wetterfragen.", Ort, ausfuehren)


async def test_zwei_runden_lesende_nebeneinander_ergebnisse_in_reihenfolge():
    fassade = Fassade(aufrufe(("a", "get_weather", {"ort": "Zeitz"}), ("b", "get_weather", {"ort": "Halle"})), text("Beide 11 Grad."))
    protokoll: list[str] = []
    async with leitstelle(fassade) as ls:
        ereignisse = [e async for e in Schleife().laufen(ls, [Nachricht.nutzer("Wetter?")], [wetter(protokoll, 0.01)], titel="Frage")]
    # nebeneinander: beide beginnen, bevor einer endet
    assert protokoll[:2] == ["anfang Zeitz", "anfang Halle"]
    ergebnisse = [e for e in ereignisse if isinstance(e, Ergebnis)]
    assert [e.ergebnis.daten for e in ergebnisse] == [{"ort": "Zeitz"}, {"ort": "Halle"}] and [e.nr for e in ergebnisse] == [1, 2]
    assert [e.werkzeug for e in ereignisse if isinstance(e, Aufruf)] == ["get_weather", "get_weather"]
    assert isinstance(ereignisse[-1], Antwort) and ereignisse[-1].text == "Beide 11 Grad." and ereignisse[-1].runde == 2
    zweite = fassade.gesehen[1]["messages"]
    assert zweite[1]["tool_calls"][0]["function"]["name"] == "get_weather"
    assert zweite[2] == {"role": "tool", "content": "Zeitz: 11 Grad", "tool_call_id": "a"}
    assert zweite[3]["tool_call_id"] == "b"
    assert fassade.gesehen[0]["tools"][0]["function"]["parameters"]["required"] == ["ort"]


async def test_schreibende_der_reihe_nach():
    protokoll: list[str] = []

    async def merken(a: Ort) -> WerkzeugErgebnis:
        protokoll.append(f"anfang {a.ort}")
        await asyncio.sleep(0.01)
        protokoll.append(f"ende {a.ort}")
        return WerkzeugErgebnis(text="gemerkt")

    w = ModellWerkzeug("merken", "Merkt etwas.", Ort, merken, nur_lesend=False)
    fassade = Fassade(aufrufe(("a", "merken", {"ort": "A"}), ("b", "merken", {"ort": "B"})), text("ok"))
    async with leitstelle(fassade) as ls:
        [e async for e in Schleife().laufen(ls, [Nachricht.nutzer("x")], [w])]
    assert protokoll == ["anfang A", "ende A", "anfang B", "ende B"]


async def test_falsche_argumente_und_unbekanntes_werkzeug_gehen_ans_modell():
    fassade = Fassade(aufrufe(("a", "get_weather", {"stadt": "Zeitz"}), ("b", "zaubern", {})), text("Entschuldigung."))
    async with leitstelle(fassade) as ls:
        ereignisse = [e async for e in Schleife().laufen(ls, [Nachricht.nutzer("x")], [wetter([])])]
    fehler = [e.ergebnis for e in ereignisse if isinstance(e, Ergebnis)]
    assert all(f.fehler for f in fehler)
    assert "ort" in fehler[0].text and "zaubern" in fehler[1].text
    assert "Argumente passen nicht" in fassade.gesehen[1]["messages"][2]["content"]


async def test_vorrede_warten_und_nachladen():
    erste = ": wartet, Modell wird geladen, etwa 40 s\n\n" + teil({"content": "Ich sehe nach."}) + aufrufe(
        ("a", "weitere_werkzeuge", {"namen": ["get_weather"]}))
    fassade = Fassade(erste, aufrufe(("b", "get_weather", {"ort": "Zeitz"})), text("11 Grad."))
    async with leitstelle(fassade) as ls:
        ereignisse = [e async for e in Schleife().laufen(ls, [Nachricht.nutzer("x")], [], nachladbar=[wetter([])])]
    assert isinstance(ereignisse[1], Warten) and ereignisse[1].sekunden == 40
    assert any(isinstance(e, TextStueck) and e.text == "Ich sehe nach." for e in ereignisse)
    assert next(e for e in ereignisse if isinstance(e, RundeEnde)).text == "Ich sehe nach."
    assert [t["function"]["name"] for t in fassade.gesehen[0]["tools"]] == ["weitere_werkzeuge"]
    assert [t["function"]["name"] for t in fassade.gesehen[1]["tools"]] == ["get_weather"]
    assert ereignisse[-1].text == "11 Grad."


async def test_rundengrenze():
    fassade = Fassade(*(aufrufe((f"a{i}", "get_weather", {"ort": "Zeitz"})) for i in range(3)))
    async with leitstelle(fassade) as ls:
        ereignisse = [e async for e in Schleife(runden=3).laufen(ls, [Nachricht.nutzer("x")], [wetter([])])]
    assert isinstance(ereignisse[-1], Grenze) and ereignisse[-1].runde == 3


def test_ergebnis_wird_fuer_das_modell_gekuerzt():
    e = WerkzeugErgebnis(text="x" * 50, rat="enger fragen")
    assert e.fuer_modell(100).endswith("Rat: enger fragen")
    assert "gekürzt" in e.fuer_modell(10)


async def test_bilder_erzeugen_als_strom():
    png = b"\x89PNG\r\n\x1a\nbild"

    def handler(request: httpx.Request):
        koerper = json.loads(request.content)
        assert request.url.path == "/v1/images/generations"
        assert koerper == {"prompt": "Lampions", "size": "1344x768", "n": 1, "response_format": "b64_json", "stream": True, "seed": 7}
        antwort = {"created": 1, "data": [{"b64_json": base64.b64encode(png).decode()}],
                   "x-leitstelle": {"seed": 7, "modell": "flux", "dauer_ms": 9000}}
        inhalt = f": wartet, Dienst startet, etwa 180 s\n\ndata: {json.dumps(antwort)}\n\ndata: [DONE]\n\n"
        return httpx.Response(200, content=inhalt.encode(), headers={"content-type": "text/event-stream", "X-Leitstelle-Auftrag": "b1"})

    async with leitstelle(handler) as ls:
        ereignisse = [e async for e in ls.bilder_erzeugen("Lampions", groesse="1344x768", startwert=7, titel="Plakat")]
    assert ereignisse[0] == Wartet(grund="Dienst startet", sekunden=180)
    fertig = ereignisse[1]
    assert isinstance(fertig, Bilder) and fertig.bilder[0].daten == png and fertig.startwert == 7 and fertig.auftrag == "b1"
