"""Testhilfen: Werte aus der Datei des Testzugangs, Aufräumen in der richtigen Reihenfolge mit Wiederholung."""

from types import SimpleNamespace

from appkern.kellerwolke import NichtGefunden
from appkern.testen import aufraeumen, hat_kellerwolke, werte


class Wolke:
    """Nachgestellte Kellerwolke: merkt die Reihenfolge; ein Knoten scheitert einmal, einer ist schon weg."""

    def __init__(self):
        self.knoten_ = {
            "o1": SimpleNamespace(id="o1", typ="ordner", pfad="Apps/T/Lauf"),
            "o2": SimpleNamespace(id="o2", typ="ordner", pfad="Apps/T/Lauf/Unter"),
            "d1": SimpleNamespace(id="d1", typ="datei", pfad="Apps/T/Lauf/a.txt"),
            "d2": SimpleNamespace(id="d2", typ="datei", pfad="Apps/T/Lauf/Unter/b.txt"),
        }
        self.geloescht: list[str] = []
        self.einmal_scheitern = {"d2"}

    async def knoten(self, k):
        if k not in self.knoten_:
            raise NichtGefunden("weg")
        return self.knoten_[k]

    async def loeschen(self, k):
        if k in self.einmal_scheitern:
            self.einmal_scheitern.discard(k)
            raise RuntimeError("gesperrt")
        self.geloescht.append(k)
        del self.knoten_[k]


async def test_dateien_vor_ordnern_und_wiederholung():
    w = Wolke()
    assert await aufraeumen(w, ["o1", "d1", "o2", "d2", "schon-weg"]) == []
    assert w.geloescht[:3] == ["d1", "o2", "o1"]     # Dateien zuerst, tiefe Ordner vor flachen
    assert w.geloescht[3:] == ["d2"]                  # im zweiten Lauf


def test_werte(tmp_path, monkeypatch):
    datei = tmp_path / ".env.test"
    datei.write_text("# Kommentar\nKELLERWOLKE_ADRESSE=http://kw\nKELLERWOLKE_SCHLUESSEL=s\nKELLERWOLKE_KENNUNG=k\n", encoding="utf-8")
    monkeypatch.setenv("KELLERWOLKE_KENNUNG", "aus-der-umgebung")
    w = werte(datei)
    assert w["KELLERWOLKE_ADRESSE"] == "http://kw" and w["KELLERWOLKE_KENNUNG"] == "aus-der-umgebung"
    assert not hat_kellerwolke(w)
    monkeypatch.setattr("appkern.testen.kellerwolke_antwortet", lambda *_a, **_k: True)
    assert hat_kellerwolke({**w, "KELLERWOLKE_PASSWORT": "p"})
    monkeypatch.setattr("appkern.testen.kellerwolke_antwortet", lambda *_a, **_k: False)
    assert not hat_kellerwolke({**w, "KELLERWOLKE_PASSWORT": "p"})               # antwortet sie nicht: überspringen
