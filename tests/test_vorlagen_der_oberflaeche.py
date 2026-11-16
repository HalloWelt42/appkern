"""Vorlagen und Instrumente der Oberfläche (RAD-6): beide Einstiege der Vorlagen laden dieselben Vorlagen, die Breite
steht nur an den Einbindungen, die Liste der wählbaren Vorlagen (lib/vorlage.svelte.ts) passt zu den Stilen, jede
Vorlage hat Marken und Bausteine, und die Marken der Instrumente sind frei wie die Marken des Appkerns, ihre Bausteine
nicht."""

import re
from pathlib import Path

from appkern.werkzeuge import marken_pruefen

WURZEL = Path(__file__).resolve().parent.parent
STIL = WURZEL / "oberflaeche" / "stil"
EINBINDUNG = re.compile(r'^@import "\./vorlagen/(\w+)\.css"(.*);$', re.M)


def _einbindungen(datei: str) -> list[tuple[str, str]]:
    return [(name, rest.strip()) for name, rest in EINBINDUNG.findall((STIL / datei).read_text(encoding="utf-8"))]


def test_einstiege_laden_dieselben_vorlagen_mit_der_breite_nur_am_einstieg():
    rechner, alle = _einbindungen("vorlagen.css"), _einbindungen("vorlagen-alle-breiten.css")
    assert [n for n, _ in rechner] == [n for n, _ in alle] and "hifi" in dict(rechner)
    assert all(bedingung == "(min-width: 1000px)" for _, bedingung in rechner)
    assert all(bedingung == "" for _, bedingung in alle)
    for datei in (STIL / "vorlagen").rglob("*.css"):
        assert "@media (min-width: 1000px)" not in datei.read_text(encoding="utf-8"), f"{datei.name}: Breite gehört an den Einstieg"


def test_waehlbare_vorlagen_passen_zu_den_stilen():
    quelle = (WURZEL / "oberflaeche" / "lib" / "vorlage.svelte.ts").read_text(encoding="utf-8")
    waehlbar = re.findall(r'\{ id: "(\w+)"', quelle)
    assert re.search(r"\{ id: GRUNDDESIGN", quelle), "Klassisch (das Grunddesign) bleibt wählbar"
    stile = [n for n, _ in _einbindungen("vorlagen.css")]
    assert sorted(waehlbar) == sorted(stile)
    for name in stile:
        assert (STIL / "vorlagen" / name / "marken.css").is_file() and (STIL / "vorlagen" / name / "bausteine.css").is_file()


def test_marken_der_instrumente_frei_bausteine_geprueft(tmp_path: Path):
    marken = tmp_path / "oberflaeche" / "stil" / "instrumente" / "marken.css"
    bausteine = marken.with_name("bausteine.css")
    marken.parent.mkdir(parents=True)
    marken.write_text(":root { --ak-glas: #0b0f14; }\n", encoding="utf-8")
    bausteine.write_text(".ak-glas { background: #0b0f14; color: var(--ak-glas-tinte); }\n", encoding="utf-8")
    befunde = marken_pruefen([marken, bausteine], tmp_path, marken=set())
    assert [(Path(b.datei).name, b.regel) for b in befunde] == [("bausteine.css", "feste Farbe")]
