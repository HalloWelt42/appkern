"""Ablage der Dateien einer App (WIKI-11): dieselben Proben für die Kellerwolke (nachgestellt) und den Datenordner;
dazu, was nur der Ordner prüfen muss (nie aus der Wurzel heraus, keine halben Dateien in der Liste)."""

import json
import re
import uuid
from pathlib import Path

import httpx
import pytest

from appkern.ablage import AblageFehler, KellerwolkeAblage, NichtDa, OrdnerAblage, teile
from appkern.kellerwolke import Kellerwolke

ZEIT = "2026-11-08T12:00:00Z"


class Wolke:
    """Kellerwolke mit Ablage im Speicher: Kennung -> (Pfad, Inhalt), Ordner ohne Inhalt."""

    def __init__(self) -> None:
        self.knoten: dict[str, tuple[str, bytes | None]] = {}
        self.weg = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.weg:
            raise httpx.ConnectError("weg")
        pfad = request.url.path
        if pfad == "/api/v1/ablage/ich":
            return httpx.Response(200, json={"app": "Probe", "konto": "chef", "rechte": []})
        if pfad == "/api/v1/ablage/ordner":
            ziel = json.loads(request.content)["pfad"]
            teile_ = ziel.split("/")
            for i in range(1, len(teile_) + 1):
                if self._finden("/".join(teile_[:i])) is None:
                    self._anlegen("/".join(teile_[:i]), None)
            return self._json(self._finden(ziel))
        if pfad == "/api/v1/ablage/datei" and request.method == "PUT":
            ziel = request.url.params["pfad"]
            vorhanden = self._finden(ziel)
            if vorhanden is not None and request.headers.get("if-none-match") == "*":
                return httpx.Response(412, json={"detail": "gibt es schon"})
            if vorhanden is not None:
                self.knoten[vorhanden] = (ziel, request.content)
                return self._json(vorhanden)
            return self._json(self._anlegen(ziel, request.content))
        if pfad == "/api/v1/ablage/pfad":
            kennung = self._finden(request.url.params["pfad"])
            return self._json(kennung) if kennung else httpx.Response(404, json={"detail": "gibt es nicht"})
        if m := re.fullmatch(r"/api/v1/ablage/knoten/([0-9a-f-]+)/kinder", pfad):
            ordner = self.knoten[m.group(1)][0]
            kinder = sorted((k for k, (p, _) in self.knoten.items() if p.rsplit("/", 1)[0] == ordner and p != ordner),
                            key=lambda k: self.knoten[k][0])
            ab, anzahl = int(request.url.params.get("ab", 0)), int(request.url.params.get("anzahl", 200))
            return httpx.Response(200, json=[self._angaben(k) for k in kinder[ab:ab + anzahl]])
        if m := re.fullmatch(r"/api/v1/ablage/knoten/([0-9a-f-]+)(/inhalt)?", pfad):
            kennung = m.group(1)
            if kennung not in self.knoten:
                return httpx.Response(404, json={"detail": "gibt es nicht"})
            if request.method == "DELETE":
                unter = self.knoten[kennung][0]
                for k in [k for k, (p, _) in self.knoten.items() if p == unter or p.startswith(f"{unter}/")]:
                    del self.knoten[k]
                return httpx.Response(204)
            return httpx.Response(200, content=self.knoten[kennung][1] or b"")
        return httpx.Response(404, json={"detail": "nicht nachgestellt"})

    def _anlegen(self, pfad: str, inhalt: bytes | None) -> str:
        kennung = str(uuid.uuid4())
        self.knoten[kennung] = (pfad, inhalt)
        return kennung

    def _finden(self, pfad: str) -> str | None:
        return next((k for k, (p, _) in self.knoten.items() if p == pfad), None)

    def _angaben(self, kennung: str) -> dict:
        pfad, inhalt = self.knoten[kennung]
        return {"id": kennung, "name": pfad.rsplit("/", 1)[-1], "pfad": pfad, "recht": "schreiben",
                "typ": "ordner" if inhalt is None else "datei", "groesse": None if inhalt is None else len(inhalt),
                "etag": None if inhalt is None else f"e{len(self.knoten)}{len(inhalt)}", "erstellt_am": ZEIT, "geaendert_am": ZEIT}

    def _json(self, kennung: str) -> httpx.Response:
        return httpx.Response(200, json=self._angaben(kennung))


@pytest.fixture(params=["kellerwolke", "ordner"])
def ablage(request, tmp_path: Path):
    if request.param == "ordner":
        return OrdnerAblage(tmp_path / "ablage")
    kw = Kellerwolke("http://kw.test", "kw_app_x", client=httpx.AsyncClient(transport=httpx.MockTransport(Wolke())),
                     geduld_s=0)
    return KellerwolkeAblage(kw, "Apps/Probe")


async def test_schreiben_finden_lesen_liste_loeschen(ablage):
    e = await ablage.schreiben("Notizen/Buch/Artikel.md", "# Titel\n".encode(), inhaltstyp="text/markdown")
    assert e.pfad == "Notizen/Buch/Artikel.md" and e.name == "Artikel.md" and not e.ordner and e.groesse == 8
    gefunden = await ablage.finden("Notizen/Buch/Artikel.md")
    assert gefunden is not None and gefunden.kennung == e.kennung
    assert await ablage.lesen_ganz(e.kennung) == b"# Titel\n"

    neu = await ablage.schreiben("Notizen/Buch/Artikel.md", b"neu", inhaltstyp="text/markdown")
    assert neu.kennung == e.kennung and await ablage.lesen_ganz(neu.kennung) == b"neu"    # dieselbe Datei, neuer Stand
    with pytest.raises(AblageFehler):
        await ablage.schreiben("Notizen/Buch/Artikel.md", b"x", inhaltstyp="text/markdown", nur_neu=True)

    await ablage.schreiben("Notizen/Buch/B.md", b"b", inhaltstyp="text/markdown")
    await ablage.schreiben("Notizen/Buch/Unter/c.md", b"c", inhaltstyp="text/markdown")
    liste = await ablage.liste("Notizen/Buch")
    assert [(x.name, x.ordner) for x in liste] == [("Unter", True), ("Artikel.md", False), ("B.md", False)]
    assert await ablage.liste("Gibt/es/nicht") == []
    assert await ablage.finden("Gibt/es/nicht.md") is None

    assert await ablage.loeschen(e.kennung) and not await ablage.loeschen(e.kennung)
    with pytest.raises(NichtDa):
        await ablage.lesen_ganz(e.kennung)
    ordner = await ablage.finden("Notizen/Buch")
    assert ordner is not None and ordner.ordner
    assert await ablage.loeschen(ordner.kennung)                           # ein Ordner geht mit seinem Inhalt
    assert await ablage.finden("Notizen/Buch/B.md") is None
    assert not await ablage.weg("Notizen/Buch/B.md")


async def test_ort_fuer_menschen(ablage):
    ort = await ablage.ort("Bücher/Thema")
    assert ort == ("Apps/Probe/Bücher/Thema" if ablage.art == "kellerwolke" else "ablage/Bücher/Thema")
    assert ablage.name in ("Kellerwolke", "Datenordner")


async def test_nie_aus_der_wurzel_heraus(tmp_path: Path):
    ordner = OrdnerAblage(tmp_path / "ablage")
    (tmp_path / "geheim.txt").write_text("x")
    for falsch in ("../geheim.txt", "a/../../geheim.txt", "a//b", "a\\b", "./a"):
        with pytest.raises(AblageFehler):
            await ordner.schreiben(falsch, b"x", inhaltstyp="text/plain")
        with pytest.raises(AblageFehler):
            await ordner.finden(falsch)
    with pytest.raises(AblageFehler):
        await ordner.loeschen("")
    assert teile("/a/b/") == ["a", "b"] and teile("") == []
    assert (tmp_path / "geheim.txt").read_text() == "x"


async def test_ordner_ohne_halbe_dateien_in_der_liste(tmp_path: Path):
    ordner = OrdnerAblage(tmp_path / "ablage")
    await ordner.schreiben("A/x.txt", b"x", inhaltstyp="text/plain")
    (tmp_path / "ablage" / "A" / ".teil-123").write_bytes(b"halb")
    assert [e.name for e in await ordner.liste("A")] == ["x.txt"]


async def test_kellerwolke_weg_ist_ein_ablagefehler():
    wolke = Wolke()
    ablage = KellerwolkeAblage(Kellerwolke("http://kw.test", "kw_app_x",
                                           client=httpx.AsyncClient(transport=httpx.MockTransport(wolke)), geduld_s=0),
                               "Apps/Probe")
    e = await ablage.schreiben("a.txt", b"a", inhaltstyp="text/plain")
    wolke.weg = True
    with pytest.raises(AblageFehler):
        await ablage.lesen_ganz(e.kennung)
    with pytest.raises(AblageFehler):
        await ablage.schreiben("b.txt", b"b", inhaltstyp="text/plain")
    assert await ablage.ort("a.txt") == "Apps/Probe/a.txt"              # der Zweig ist schon bekannt


async def test_ort_ohne_antwort_der_kellerwolke():
    wolke = Wolke()
    wolke.weg = True
    ablage = KellerwolkeAblage(Kellerwolke("http://kw.test", "kw_app_x",
                                           client=httpx.AsyncClient(transport=httpx.MockTransport(wolke)), geduld_s=0),
                               "Apps/Probe")
    assert await ablage.ort("Bücher") == "Apps/Probe/Bücher"
