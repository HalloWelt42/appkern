"""Werkzeuge der Entwicklung: Zeichenprüfung, Stilprüfung (mit Gegenproben), Fassung hochzählen."""

import json

from appkern.werkzeuge import hochzaehlen, stil_pruefen, zeichen_pruefen
from appkern.werkzeuge.stil import regeln


def _datei(tmp_path, name, text):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _regeln_der(befunde):
    return [(b.zeile, b.regel) for b in befunde]


def test_zeichen(tmp_path):
    gut = _datei(tmp_path, "gut.md", 'Nur "gerade" Zeichen - wie hier.\n')
    schlecht = _datei(tmp_path, "schlecht.ts", "// ok\nconst a = \"x \u2013 y\";\n")
    befunde = zeichen_pruefen([gut, schlecht], tmp_path)
    assert [(b.datei, b.zeile) for b in befunde] == [("schlecht.ts", 2)]


def test_leser_kennt_bloecke_und_zeilen():
    text = "/* Kopf\n   zwei Zeilen */\n.a { color: red; }\n@media (max-width: 900px) {\n  .b, .c { gap: 1px; }\n}\n" \
           "@keyframes drehen { from { opacity: 0; } to { opacity: 1; } }\n.d{x:y}"
    r = regeln(text)
    assert [(x.selektoren, x.zeile, x.im_rahmen.split(" ")[0]) for x in r] == [
        ([".a"], 3, ""), ([".b", ".c"], 5, "@media"), (["from"], 7, "@keyframes"), (["to"], 7, "@keyframes"), ([".d"], 8, "")]


def test_stil_findet_streifen_und_important(tmp_path):
    css = _datei(tmp_path, "a.css", "\n".join([
        ".x { color: red !important; }",                                   # 1 !important
        ".x { border-left: 3px solid var(--akzent); }",                    # 2 Streifen links
        ".x { border-left: 1px solid var(--rand); }",                      # 3 Trennlinie: erlaubt
        ".x { box-shadow: inset 3px 0 0 var(--akzent); }",                 # 4 Streifen per Schatten
        ".x { box-shadow: 0 1px 0 var(--rand); }",                         # 5 Trennlinie: erlaubt
        ".x { box-shadow: 0 2px 8px rgba(0,0,0,.2), 0 0 0 1px var(--rand); }",  # 6 Schatten rundum: erlaubt
        ".x { border-bottom: 3px solid transparent; }",                    # 7 Unterstreichung (Reiter)
        ".x { border-bottom: 1px solid var(--akzent); }",                  # 8 farbige Linie
        ".x { border-width: 0 0 0 4px; }",                                 # 9 einseitig über border-width
        ".x { border: 1px solid var(--rand); }",                           # 10 rundum: erlaubt
    ]))
    assert _regeln_der(stil_pruefen([css], tmp_path)) == [
        (1, "!important"), (2, "einseitiger Rahmen"), (4, "einseitiger Schatten"), (7, "einseitiger Rahmen"),
        (8, "einseitiger Rahmen"), (9, "einseitiger Rahmen")]


def test_stil_regeln_auf_klassen_der_schale(tmp_path):
    schale = {"knopf", "stand", "t-zeile", "mobil", "klein"}
    css = _datei(tmp_path, "app.css", "\n".join([
        ".stand { color: red; }",                 # 1 ändert die Schale mit
        ".knopf.eigen { height: 30px; }",         # 2 Erweiterung mit eigener Klasse: erlaubt
        ".mobil .t-zeile .klein { gap: 1px; }",   # 3 nur Klassen der Schale
        ".liste .stand { gap: 1px; }",            # 4 unter eigener Klasse: erlaubt
        ":root { --x: 1; }",                      # 5 Variablen: erlaubt
        "@media (max-width: 900px) { .knopf { padding: 0; } }",  # 6 auch in @media
    ]))
    assert _regeln_der(stil_pruefen([css], tmp_path, schale)) == [
        (1, "Regel auf Klassen der Schale"), (3, "Regel auf Klassen der Schale"), (6, "Regel auf Klassen der Schale")]
    # ohne Klassen der Schale (im Appkern selbst) keine solchen Befunde
    assert stil_pruefen([css], tmp_path) == []


def test_stil_in_svelte(tmp_path):
    svelte = _datei(tmp_path, "Teil.svelte", "\n".join([
        "<script>let a = 1;</script>",
        '<div style="color: red !important">x</div>',
        "<style>",
        "  .stand { color: red; }",               # eigener Block: Svelte begrenzt ihn auf die Komponente
        "  :global(.stand) { color: blue; }",     # global: trifft die Schale
        "  .y { border-right: 2px solid var(--gut); }",
        "</style>",
    ]))
    assert _regeln_der(stil_pruefen([svelte], tmp_path, {"stand"})) == [
        (2, "!important"), (5, "Regel auf Klassen der Schale"), (6, "einseitiger Rahmen")]


def test_fassung(tmp_path):
    datei = _datei(tmp_path, "version.json", json.dumps({"version": "0.9.3", "id": "aaaaaa", "voll": "v0.9.3-aaaaaa"}))
    assert hochzaehlen(datei, "patch").startswith("v0.9.4-")
    assert hochzaehlen(datei, "minor").startswith("v0.10.0-")
    vorher = json.loads(datei.read_text())
    assert hochzaehlen(datei, "id").startswith("v0.10.0-") and json.loads(datei.read_text())["id"] != vorher["id"]
    assert hochzaehlen(datei, "major").startswith("v1.0.0-")
