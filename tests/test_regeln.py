"""Harte Architekturregeln (ATL-15): Arten von Regeln, Ausnahmen nur mit Freigabe des Nutzers, Commit-Nachricht."""

from pathlib import Path

import pytest

from appkern.werkzeuge import regeln
from appkern.werkzeuge.__main__ import nachricht_pruefen

REGELN = """
[freigabe]
pinnwand = "https://pinnwand.test/api/v1"
schluessel = "~/gibt-es-nicht"

[[regel]]
kennung = "R1"
titel = "Kein Link ins Netz"
art = "verboten"
dateien = ["src/**"]
muster = 'https?://cdn\\.'

[[regel]]
kennung = "R2"
titel = "Schichten"
art = "schichten"
dateien = ["src/**"]
schichten = [{ name = "kern", dateien = ["src/kern/*"] }, { name = "oberflaeche", dateien = ["src/ui/*"] }]
erlaubt = { oberflaeche = ["kern"] }

[[regel]]
kennung = "R3"
titel = "Plan vorhanden"
art = "pflicht"
dateien = ["docs/ARCHITEKTUR.md"]

[[regel]]
kennung = "R4"
titel = "Kleine Dateien"
art = "zeilen"
dateien = ["src/**"]
hoechstens = 5
"""


@pytest.fixture
def app(tmp_path: Path) -> Path:
    (tmp_path / "architektur").mkdir()
    (tmp_path / "architektur" / "regeln.toml").write_text(REGELN, encoding="utf-8")
    for pfad, text in {
        "src/kern/rechnen.ts": "export const a = 1;\n",
        "src/ui/flaeche.ts": "import { a } from '../kern/rechnen';\n",
        "src/kern/schlecht.ts": "import { b } from '../ui/flaeche';\nconst s = 'https://cdn.example/x.js';\n",
    }.items():
        (tmp_path / pfad).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / pfad).write_text(text, encoding="utf-8")
    return tmp_path


def _alle(app: Path) -> list[Path]:
    return [p for p in app.rglob("*") if p.is_file()]


def test_arten_finden_ihre_verstoesse(app: Path) -> None:
    befunde = regeln.regeln_pruefen(_alle(app), app)
    arten = {(b.regel, b.datei) for b in befunde}
    assert ("R1", "src/kern/schlecht.ts") in arten                  # verbotenes Muster
    assert ("R2", "src/kern/schlecht.ts") in arten                  # Kern bindet Oberfläche ein
    assert ("R2", "src/ui/flaeche.ts") not in arten                 # erlaubte Richtung
    assert ("R3", "docs/ARCHITEKTUR.md") in arten                   # Pflichtdatei fehlt
    assert not any(b.regel == "R4" for b in befunde)                # Dateien sind kurz genug


def test_ausnahme_ohne_freigabe_haelt_auf(app: Path) -> None:
    (app / "architektur" / "ausnahmen.toml").write_text(
        '[[ausnahme]]\nregel = "R1"\ndateien = ["src/kern/schlecht.ts"]\ngrund = "Probe"\nticket = "ATL-99"\n', encoding="utf-8")
    befunde = regeln.regeln_pruefen(_alle(app), app)
    assert any(b.regel == "R1" for b in befunde)                    # nicht aufgehoben
    ohne = [b for b in befunde if b.regel == "Ausnahme ohne Freigabe"]
    assert ohne and "nicht erreichbar" in ohne[0].text              # sicher scheitern ohne Pinnwand


def _stand(von: str, text: str) -> dict:
    return {"karten": [{"schluessel": "ATL-99", "kommentare": [{"von": von, "text": text}]}]}


@pytest.mark.parametrize("von, text, gilt", [
    ("nutzer-id", "Ausnahme freigegeben: R1", True),
    ("nutzer-id.app-helfer", "Ausnahme freigegeben: R1", False),    # eine App kann nicht freigeben
    ("nutzer-id", "Ausnahme freigegeben: R2", False),               # andere Regel
    ("nutzer-id", "klingt gut", False),
])
def test_freigabe_nur_durch_den_nutzer(app: Path, monkeypatch: pytest.MonkeyPatch, von: str, text: str, gilt: bool) -> None:
    (app / "architektur" / "ausnahmen.toml").write_text(
        '[[ausnahme]]\nregel = "R1"\ndateien = ["src/kern/schlecht.ts"]\ngrund = "Probe"\nticket = "ATL-99"\n', encoding="utf-8")
    schluessel = app / "schluessel"
    schluessel.write_text("geheim")
    toml = (app / "architektur" / "regeln.toml").read_text().replace("~/gibt-es-nicht", str(schluessel))
    (app / "architektur" / "regeln.toml").write_text(toml)

    class Antwort:
        def __init__(self, daten: dict) -> None:
            import json
            self.daten = json.dumps(daten).encode()

        def read(self, *_: object) -> bytes:
            return self.daten

    monkeypatch.setattr(regeln.urllib.request, "urlopen", lambda *a, **k: Antwort(_stand(von, text)))
    befunde = regeln.regeln_pruefen(_alle(app), app)
    assert (not any(b.regel == "R1" for b in befunde)) is gilt


def test_ausnahme_auf_unbekannte_regel(app: Path) -> None:
    (app / "architektur" / "ausnahmen.toml").write_text(
        '[[ausnahme]]\nregel = "R9"\ndateien = ["*"]\ngrund = "x"\nticket = "ATL-1"\n', encoding="utf-8")
    assert any(b.regel == "Ausnahme" for b in regeln.regeln_pruefen(_alle(app), app))


@pytest.mark.parametrize("nachricht, ok", [
    ("ATL-15: Regeln von Git erzwungen", True),
    ("ATL-15, HELF-156: zwei Tickets", True),
    ("Regeln eingebaut", False),
    ("atl-15: klein", False),
    ("Merge branch 'main'", True),
])
def test_commit_nachricht_braucht_ticket(tmp_path: Path, nachricht: str, ok: bool) -> None:
    datei = tmp_path / "COMMIT_EDITMSG"
    datei.write_text(nachricht + "\n\n# Kommentar\n", encoding="utf-8")
    assert (nachricht_pruefen(datei) == 0) is ok


def test_ohne_regelwerk_nichts_zu_tun(tmp_path: Path) -> None:
    assert regeln.regeln_pruefen([], tmp_path) == []
