"""Leitstellen-Zugang gegen eine nachgestellte Fassade (httpx.MockTransport), wie ANBINDUNG.md Abschnitt 9 es
verlangt: Köpfe (Schlüssel, Titel, Priorität), Antwort am Stück und als Strom mit Warten, Abbruch mit Teiltext,
Fehlerarten mit Grundwort und Retry-After, Einbettungen, Modellliste, Dienste mit Hochladen und Herunterladen."""

import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

from appkern.leitstelle import (
    Abgebrochen, DienstFehler, DienstWeg, Ende, Gesperrt, Halt, KeinModell, Leitstelle, Nachricht, NichtErlaubt,
    NichtErreichbar, NichtGefunden, SchluesselUngueltig, Stueck, Ungueltig, Wartet,
)


def leitstelle(handler) -> Leitstelle:
    return Leitstelle("http://ls.test/v1", "ls_geheim", "Transkription",
                      client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def fehler(status, code, text="nein", **kopf):
    return httpx.Response(status, json={"error": {"message": text, "type": "leitstelle", "code": code}}, headers=kopf)


def sse(*teile: str) -> bytes:
    return "".join(teile).encode()


def stueck(text=None, ende=None, usage=None, model="gross"):
    roh = {"model": model, "choices": [{"index": 0, "delta": {"content": text} if text else {}, "finish_reason": ende}]}
    if usage:
        roh["usage"] = usage
    return f"data: {json.dumps(roh)}\n\n"


def test_schluessel_nie_in_der_ausgabe():
    ls = Leitstelle("http://ls.test", "ls_geheim", "App")
    assert "geheim" not in repr(ls) and "geheim" not in repr(ls.dienst("klangwerk-hoeren"))


async def test_chat_am_stueck_mit_koepfen():
    gesehen = {}

    def handler(request: httpx.Request):
        gesehen["pfad"] = request.url.path
        gesehen["kopf"] = dict(request.headers)
        gesehen["koerper"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "gross", "choices": [{"message": {"content": "Hallo"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}},
                              headers={"X-Leitstelle-Auftrag": "a1", "X-Leitstelle-Modell": "qwen-80b", "X-Leitstelle-Knoten": "studio"})

    async with leitstelle(handler) as ls:
        antwort = await ls.chat([Nachricht.system("Kurz."), "Grüß mich"], titel="Prüfen für Übersetzung",
                                prioritaet="hintergrund", temperature=0.2)
    assert antwort.text == "Hallo" and antwort.modell == "qwen-80b" and antwort.knoten == "studio"
    assert antwort.auftrag == "a1" and antwort.verbrauch.gesamt == 7 and not antwort.abgebrochen
    assert gesehen["pfad"] == "/v1/chat/completions"
    assert gesehen["kopf"]["authorization"] == "Bearer ls_geheim"
    assert gesehen["kopf"]["x-leitstelle-titel"].isascii()
    assert unquote(gesehen["kopf"]["x-leitstelle-titel"]) == "Transkription: Prüfen für Übersetzung"
    assert gesehen["kopf"]["x-leitstelle-prioritaet"] == "hintergrund"
    assert gesehen["koerper"] == {"messages": [{"role": "system", "content": "Kurz."}, {"role": "user", "content": "Grüß mich"}],
                                  "temperature": 0.2}                       # ohne model: die Kette der App gilt


async def test_strom_mit_warten_stuecken_und_verbrauch():
    def handler(request):
        koerper = json.loads(request.content)
        assert koerper["stream"] is True and koerper["model"] == "schnell"
        inhalt = sse(": wartet, Modell wird geladen, etwa 40 s\n\n", ": wartet, Speicher knapp\n\n",
                     stueck("Hal"), stueck("lo"), stueck(ende="stop"),
                     f"data: {json.dumps({'choices': [], 'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}})}\n\n",
                     "data: [DONE]\n\n")
        return httpx.Response(200, content=inhalt, headers={"content-type": "text/event-stream", "X-Leitstelle-Auftrag": "a2"})

    async with leitstelle(handler) as ls:
        ereignisse = [e async for e in ls.chat_strom(["Hallo?"], modell="schnell")]
    assert ereignisse[:2] == [Wartet(grund="Modell wird geladen", sekunden=40), Wartet(grund="Speicher knapp")]
    assert [e.text for e in ereignisse if isinstance(e, Stueck)] == ["Hal", "lo"]
    ende = ereignisse[-1]
    assert isinstance(ende, Ende) and ende.ende == "stop" and not ende.abgebrochen
    assert ende.auftrag == "a2" and ende.modell == "gross" and ende.verbrauch.gesamt == 5


async def test_abbruch_liefert_den_teiltext():
    def handler(request):
        if json.loads(request.content).get("stream"):
            return httpx.Response(200, content=sse(stueck("Bis hier"), stueck(ende="leitstelle_abbruch"), "data: [DONE]\n\n"))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Bis hier"}, "finish_reason": "leitstelle_abbruch"}]})

    async with leitstelle(handler) as ls:
        ereignisse = [e async for e in ls.chat_strom(["x"])]
        antwort = await ls.chat(["x"])
    assert ereignisse[-1].abgebrochen and ereignisse[0].text == "Bis hier"
    assert antwort.abgebrochen and antwort.text == "Bis hier"


@pytest.mark.parametrize("status,code,art", [
    (401, "unbekannter_schluessel", SchluesselUngueltig), (403, "zone_nicht_erlaubt", NichtErlaubt),
    (404, "kein_modell", KeinModell), (429, "gesperrt", Gesperrt), (503, "halt", Halt),
    (503, "modell_passt_nicht", DienstWeg), (502, "dienst_fehler", DienstFehler), (409, "nutzer", Abgebrochen),
    (400, "eingabe", Ungueltig),
])
async def test_fehlerarten_nach_grundwort(status, code, art):
    zaehler = {"n": 0}

    def handler(request):
        zaehler["n"] += 1
        kopf = {"Retry-After": "30"} if status in (429, 503) else {}
        return fehler(status, code, "Die Leitstelle sagt nein.", **kopf)

    async with leitstelle(handler) as ls:
        with pytest.raises(art) as f:
            await ls.chat(["x"])
    assert f.value.grund == code and f.value.meldung == "Die Leitstelle sagt nein." and f.value.status == status
    assert f.value.nochmal_in == (30 if status in (429, 503) else None)
    assert zaehler["n"] == 1                                                   # nie von selbst wiederholt


async def test_fehler_im_strom_und_vor_dem_strom():
    def handler(request):
        if request.headers.get("x-leitstelle-titel", "").endswith("vorher"):
            return fehler(503, "halt", "Halt am Hauptregler", **{"Retry-After": "30"})
        daten = json.dumps({"error": {"message": "Dienst weg", "type": "leitstelle", "code": "dienst_nicht_erreichbar"}})
        return httpx.Response(200, content=sse(stueck("Teil"), f"data: {daten}\n\ndata: [DONE]\n\n"))

    async with leitstelle(handler) as ls:
        with pytest.raises(Halt) as f:
            [e async for e in ls.chat_strom(["x"], titel="vorher")]
        assert f.value.nochmal_in == 30
        gesehen = []
        with pytest.raises(DienstWeg):
            async for e in ls.chat_strom(["x"]):
                gesehen.append(e)
        assert gesehen == [Stueck(text="Teil")]


async def test_nicht_erreichbar():
    def handler(request):
        raise httpx.ConnectError("weg")

    async with leitstelle(handler) as ls:
        with pytest.raises(NichtErreichbar):
            await ls.modelle()
        with pytest.raises(NichtErreichbar):
            [e async for e in ls.chat_strom(["x"])]


async def test_modelle_und_einbettungen():
    def handler(request):
        if request.url.path == "/v1/models":
            assert "x-leitstelle-titel" not in request.headers
            return httpx.Response(200, json={"object": "list", "data": [
                {"id": "gross", "object": "model", "x-leitstelle": {"name": "Qwen 80B", "geladen": True, "knoten": "studio",
                                                                    "extern": False, "faehigkeiten": ["text"], "gb": 48.0, "neu": 1}},
                {"id": "klangwerk-hoeren", "object": "model"}]})
        assert json.loads(request.content) == {"input": ["a", "b"]}
        return httpx.Response(200, json={"model": "nomic", "data": [{"index": 1, "embedding": [0.2]}, {"index": 0, "embedding": [0.1]}]})

    async with leitstelle(handler) as ls:
        modelle = await ls.modelle()
        einbettung = await ls.einbetten(["a", "b"])
    assert [(m.id, m.geladen, m.gb) for m in modelle] == [("gross", True, 48.0), ("klangwerk-hoeren", False, None)]
    assert einbettung.vektoren == [[0.1], [0.2]] and einbettung.modell == "nomic"


async def test_dienst_hochladen_json_und_herunterladen(tmp_path: Path):
    ton = tmp_path / "termin.wav"
    ton.write_bytes(b"RIFF" + b"\x00" * 2000)

    def handler(request):
        assert request.url.path.startswith("/v1/dienste/klangwerk-hoeren/")
        assert unquote(request.headers["x-leitstelle-titel"]) == "Transkription: Folge 12"
        if request.url.path.endswith("/stt"):
            assert b'name="file"; filename="termin.wav"' in request.content and b'name="language"' in request.content
            return httpx.Response(200, json={"text": "Hallo", "language": "de"})
        if request.url.path.endswith("/audio/x.wav"):
            return httpx.Response(200, content=b"A" * 5000)
        return httpx.Response(422, json={"detail": "Pfad passt nicht"})

    async with leitstelle(handler) as ls:
        hoeren = ls.dienst("klangwerk-hoeren")
        with open(ton, "rb") as datei:
            ergebnis = await hoeren.json("POST", "/stt", titel="Folge 12", data={"language": "de"},
                                         files={"file": ("termin.wav", datei, "audio/wav")})
        ziel = await hoeren.herunterladen("audio/x.wav", tmp_path / "x.wav", titel="Folge 12")
        with pytest.raises(Ungueltig) as f:
            await hoeren.anfrage("GET", "/etwas", titel="Folge 12")
    assert ergebnis == {"text": "Hallo", "language": "de"}
    assert ziel.read_bytes() == b"A" * 5000 and not list(tmp_path.glob(".*.teil"))
    assert f.value.meldung == "Pfad passt nicht"


async def test_herunterladen_hinterlaesst_bei_fehler_nichts(tmp_path: Path):
    def handler(request):
        return httpx.Response(404, json={"detail": "weg"})

    async with leitstelle(handler) as ls:
        with pytest.raises(NichtGefunden):
            await ls.dienst("klangwerk-sprechen").herunterladen("tts/audio/a.wav", tmp_path / "a.wav")
    assert list(tmp_path.iterdir()) == []


def test_keine_lese_zeitgrenze_fuer_arbeit():
    ls = Leitstelle("http://ls.test", "k", "App")
    assert ls._client.timeout.read is None and ls._client.timeout.connect == 10.0


def test_gehoerte_segmente_mit_versatz_ohne_leere():
    from appkern.leitstelle.hoeren import Gehoert, segmente_aus
    roh = [{"start": 0.0, "end": 1.2, "text": " Guten Tag. ", "words": [{"word": " Guten", "start": 0.0, "end": 0.5},
                                                                          {"word": " Tag.", "start": 0.5, "end": 1.2}]},
           {"start": 1.2, "end": 1.4, "text": "  ", "words": []}]
    s = segmente_aus(roh, versatz=10.0)
    assert len(s) == 1 and (s[0].start, s[0].ende, s[0].text) == (10.0, 11.2, "Guten Tag.")
    assert [(w.wort, w.start) for w in s[0].woerter] == [("Guten", 10.0), ("Tag.", 10.5)]
    assert Gehoert(segmente=s).text == "Guten Tag."


async def test_schemaantwort_aus_dem_denkfeld():
    """Denkende Modelle legen in LM Studio die Schema-Ausgabe ins Denkfeld; ohne Schema bleibt das Denken Denken."""
    def handler(request: httpx.Request):
        return httpx.Response(200, json={"model": "qwen3.8", "choices": [{"message": {
            "content": "", "reasoning_content": '{"a": 1}'}, "finish_reason": "stop"}]})

    async with leitstelle(handler) as ls:
        mit = await ls.chat(["x"], response_format={"type": "json_schema", "json_schema": {"name": "n", "schema": {}}})
        ohne = await ls.chat(["x"])
    assert (mit.text, mit.denken) == ('{"a": 1}', '{"a": 1}') and (ohne.text, ohne.denken) == ("", '{"a": 1}')


async def test_erlaubnisliste_extern_und_steckbriefe():
    """Die Erlaubnisliste aus den Einstellungen der App geht als Kopf X-Leitstelle-Extern mit jeder Anfrage; leer fehlt
    der Kopf (dann nie nach extern). Steckbriefe kommen gefiltert; neue Wörter einer neueren Leitstelle brechen nichts."""
    gesehen = {}

    def handler(request):
        gesehen[request.url.path] = request
        if request.url.path == "/v1/steckbriefe":
            return httpx.Response(200, json={"object": "list", "data": [{"id": "Qwen/Qwen3.8-27B", "name": "Qwen3.8-27B", "geladen": True,
                "steckbrief": {"zweck": "Übersetzen", "eignung": ["lange_texte", "kuenftig"], "zone": "extern", "anfragen_je_minute": 10,
                               "gemessen": {"auftraege": 3, "token_je_s": 40.0}, "herkunft": {"zweck": "hand"}, "neu": True}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    async with leitstelle(handler) as ls:
        await ls.chat(["x"])
        assert "x-leitstelle-extern" not in gesehen["/v1/chat/completions"].headers
        ls.extern = ("Qwen/Qwen3.8-27B", "Qwen3.6 35B")
        await ls.chat(["x"])
        assert unquote(gesehen["/v1/chat/completions"].headers["x-leitstelle-extern"]) == "Qwen/Qwen3.8-27B,Qwen3.6 35B"
        s = await ls.steckbriefe(eignung="lange_texte", sprache="de")
    assert dict(gesehen["/v1/steckbriefe"].url.params) == {"eignung": "lange_texte", "sprache": "de"}
    assert s[0].id == "Qwen/Qwen3.8-27B" and s[0].steckbrief.zone == "extern" and s[0].steckbrief.eignung == ["lange_texte", "kuenftig"]
    assert s[0].steckbrief.gemessen.token_je_s == 40.0 and s[0].steckbrief.herkunft == {"zweck": "hand"}
