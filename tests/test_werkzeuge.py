"""Werkzeuge der Entwicklung: Zeichenprüfung, Stilprüfung (mit Gegenproben), Fassung hochzählen."""

import json
from pathlib import Path

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
        ".x { border-top: 1px solid var(--rand-stark); }",                 # 11 Trennlinie in starker Randfarbe: erlaubt
        ".x { border-top: 1px solid var(--ls-rand); }",                    # 12 in Entwürfen der Leitstelle: erlaubt
        ".x { border-top: 1px solid var(--randfarbe-x); }",                # 13 keine Randfarbe
    ]))
    assert _regeln_der(stil_pruefen([css], tmp_path)) == [
        (1, "!important"), (2, "einseitiger Rahmen"), (4, "einseitiger Schatten"), (7, "einseitiger Rahmen"),
        (8, "einseitiger Rahmen"), (9, "einseitiger Rahmen"), (13, "einseitiger Rahmen")]


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


def test_ausrollen_prueft_den_tondienst_statt_ffmpeg():
    """Der Pi rechnet nicht: mit Ton prüft das Ausrollen nur, ob die Leitstelle den Tondienst meldet."""
    import pytest
    from pydantic import ValidationError

    from appkern.werkzeuge.ausrollen import Ziel, tondienst

    gemeldet = {"data": [{"id": "klangwerk-ton", "x-leitstelle": {"faehigkeiten": ["ton"]}},
                         {"id": "klangwerk-hoeren", "x-leitstelle": {"faehigkeiten": ["hoeren"]}}]}
    assert tondienst(json.dumps(gemeldet)) == "Tondienst: klangwerk-ton"
    assert tondienst(json.dumps({"data": gemeldet["data"][1:]})).startswith("WARNUNG")
    assert tondienst("").startswith("WARNUNG")
    angaben = {"kennung": "probe", "rechner": "pi@pi", "wurzel": "/srv/probe", "adresse": "https://pi:1",
               "repo": "x", "namen": ["pi"]}
    with pytest.raises(ValidationError):
        Ziel.model_validate({**angaben, "ton": True})
    assert Ziel.model_validate({**angaben, "ton": True, "leitstelle": "http://pi:8530"}).ton


def test_ausrollen_mit_eigener_zieldatei(tmp_path):
    """Ein Probestand rollt aus einer eigenen Datei aus (eigener Ordner, eigene Compose-Datei); ohne Angabe gilt
    deploy/ausrollen.toml mit compose.pi.yml."""
    from appkern.werkzeuge.ausrollen import laden

    (tmp_path / "deploy").mkdir()
    gemeinsam = 'kennung = "probe"\nrechner = "pi@pi"\nadresse = "https://pi:1"\nrepo = "x"\nnamen = ["pi"]\n'
    (tmp_path / "deploy" / "ausrollen.toml").write_text(gemeinsam + 'wurzel = "/srv/probe"\n')
    (tmp_path / "deploy" / "probe.toml").write_text(gemeinsam + 'wurzel = "/srv/probe-test"\ncompose = "compose.test.yml"\n')
    assert (laden(tmp_path).wurzel, laden(tmp_path).compose) == ("/srv/probe", "compose.pi.yml")
    z = laden(tmp_path, Path("deploy/probe.toml"))
    assert (z.wurzel, z.compose) == ("/srv/probe-test", "compose.test.yml")


def test_ergaenzung_fuellt_nur_was_fehlt(tmp_path):
    """Was dem Haus gehört (Rechner, Ordner, Adresse, Namen, Leitstelle), kommt aus einer privaten Ergänzung; was die
    Zieldatei selbst nennt, gilt (ein Probestand behält seinen Ordner). Der Name <kennung>.local steht immer in den
    Namen, weil der Vorschaltdienst ihn ohne Servernamen nimmt."""
    import pytest
    from pydantic import ValidationError

    from appkern.werkzeuge.ausrollen import laden

    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "ausrollen.toml").write_text('kennung = "probe"\nrepo = "x"\nton = true\n')
    (tmp_path / "deploy" / "probe.toml").write_text('kennung = "probe"\nrepo = "x"\nwurzel = "/srv/probe-test"\n')
    (tmp_path / "haus.toml").write_text('rechner = "pi@pi"\nwurzel = "/srv/probe"\nadresse = "https://pi:1"\n'
                                        'namen = ["pi"]\nleitstelle = "http://pi:8530"\n')
    z = laden(tmp_path, ergaenzung=tmp_path / "haus.toml")
    assert (z.rechner, z.wurzel, z.adresse, z.leitstelle) == ("pi@pi", "/srv/probe", "https://pi:1", "http://pi:8530")
    assert z.namen == ["pi", "probe.local"]
    assert z.einrichtungscode_ort == "pi@pi:/srv/probe/daten/einrichtungscode"
    assert laden(tmp_path, Path("deploy/probe.toml"), tmp_path / "haus.toml").wurzel == "/srv/probe-test"
    with pytest.raises(ValidationError):
        laden(tmp_path)            # ohne Ergänzung fehlen die Angaben des Hauses


def test_eigene_schale_ohne_pruefung_auf_klassen_der_schale(tmp_path):
    """Eine App, die nur Bausteine des Appkerns nutzt und den Stil nicht lädt, hat eine eigene Schale: dann gibt es
    keine Klassen der Schale, die ihre Regeln mit ändern könnten."""
    from appkern.werkzeuge.__main__ import _schale
    paket = tmp_path / "frontend" / "node_modules" / "appkern-oberflaeche" / "oberflaeche"
    (paket / "stil").mkdir(parents=True)
    (paket / "stil" / "alles.css").write_text(".knopf { color: red; }\n")
    quellen = tmp_path / "frontend" / "src"
    quellen.mkdir(parents=True)
    (quellen / "main.ts").write_text('import "./stil/eigen.css";\nimport { sitzung } from "appkern-oberflaeche";\n')
    assert _schale(tmp_path) is None
    (quellen / "main.ts").write_text('import "appkern-oberflaeche/stil.css";\n')
    assert _schale(tmp_path) == {"knopf"}


# ----- Marken der Gestaltung (Grunddesign: nur Marken, Ausnahme begründet) -----

MARKEN = {"--gross", "--akzent", "--app-farbe"}


def test_marken_findet_feste_werte_und_laesst_marken_frei(tmp_path):
    from appkern.werkzeuge import marken_pruefen

    css = _datei(tmp_path, "frontend/src/a.css", "\n".join([
        ".a { color: #fff; }",                                                     # 1 feste Farbe
        ".a { background: rgba(10, 20, 30, .4); }",                                # 2 feste Farbe
        ".a { border: 1px solid white; }",                                         # 3 Farbname
        ".a { color: var(--auf-akzent, #fff); }",                                  # 4 feste Farbe als Rückfall
        ".a { background: color-mix(in srgb, var(--gut) 20%, transparent); }",     # 5 Mischung aus Marken: frei
        ".a { background: color-mix(in srgb, var(--gut) 72%, #000); }",            # 6 feste Farbe in der Mischung
        ".a { background: rgba(var(--ls-akzent-rgb), 0.5); }",                     # 7 Kanäle aus einer Marke: frei
        ".a { font-family: ui-monospace, monospace; }",                            # 8 feste Schrift
        ".a { font-family: var(--schrift-code); }",                                # 9 frei
        ".a { font-size: 14px; }",                                                 # 10 feste Schriftgröße
        ".a { font-size: calc(var(--gross) + 2px); font-size: .9em; font-size: 0; }",  # 11 frei
        ".a i, .b > i.fa-x::before { font-size: 14px; }",                          # 12 Symbole: frei
        ".a .symbol { font-size: 14px; }",                                         # 13 keine erkennbaren Symbole
        ".a { --gross: 16px; }",                                                   # 14 Marke überschrieben
        ".a { --eigen: #e8590c; --breite: 440px; --mix: var(--akzent); }",         # 15 eigene Marke mit Farbe
        ".a { fill: url(#verlauf); content: \"#1\"; grid-template-areas: \"red\"; }",  # 16 frei
        ".a { font: inherit; }",                                                   # 17 frei
        ".a { font: 600 14px/1.2 Barlow; }",                                       # 18 feste Schriftgröße
        ".a { font-size: small; }",                                                # 19 feste Schriftgröße
        ".a { --app-farbe: var(--akzent); color: transparent; color: currentColor; }",  # 20 frei
        ".a { --mono: \"JetBrains Mono\", ui-monospace, monospace; }",     # 21 eigene Marke mit Schriftliste
        ".a { --raster: \"kopf kopf\"; --zeilen: 2; }",                    # 22 frei
    ]))
    befunde = marken_pruefen([css], tmp_path, MARKEN)
    assert _regeln_der(befunde) == [
        (1, "feste Farbe"), (2, "feste Farbe"), (3, "feste Farbe"), (4, "feste Farbe"), (6, "feste Farbe"),
        (8, "feste Schrift"), (10, "feste Schriftgröße"), (13, "feste Schriftgröße"), (14, "Marke des Appkerns überschrieben"),
        (15, "feste Farbe"), (18, "feste Schriftgröße"), (19, "feste Schriftgröße"), (21, "feste Schrift")]


def test_marken_ausnahme_nur_mit_grund(tmp_path):
    from appkern.werkzeuge import marken_pruefen

    css = _datei(tmp_path, "frontend/src/a.css", "\n".join([
        ".a { color: #fff; } /* Ausnahme: weiß auf dem Foto, unabhängig vom Thema */",   # 1 frei
        "/* Ausnahme: 16 Pixel verhindern das Vergrößern am iPhone */",
        ".a { font-size: 16px; }",                                                      # 3 frei
        "/* Ausnahme: Farben der Codehervorhebung wie im Editor */",
        ".hljs {",
        "  color: #8839ef;",                                                            # 6 frei (über der Regel)
        "  background: #fff;",                                                          # 7 frei
        "}",
        ".a { color: #000; } /* Ausnahme: ok */",                                        # 9 Grund zu kurz
        "/* Ausnahme ohne Doppelpunkt und Grund */",
        ".a { color: #000; }",                                                          # 11 kein Grund
    ]))
    assert _regeln_der(marken_pruefen([css], tmp_path, MARKEN)) == [(9, "feste Farbe"), (11, "feste Farbe")]


def test_marken_in_svelte(tmp_path):
    from appkern.werkzeuge import marken_pruefen

    svelte = _datei(tmp_path, "frontend/src/Teil.svelte", "\n".join([
        "<script>const farbe = '#fff';</script>",                                       # 1 Skript: nicht Stil
        '<div style="color: #fff; width: {breite}px">x</div>',                           # 2 feste Farbe
        '<i class="fa-solid fa-x" style="font-size: 12px; color: var(--gut)"></i>',     # 3 Symbol: frei
        '<svg><circle fill="#e00" stroke="currentColor" r="2"/><text font-size="11">a</text></svg>',  # 4 zwei Befunde
        '<span style="background: {farbe}">x</span>',                                    # 5 Ausdruck der App: frei
        "<!-- Ausnahme: Farbe des Fremdlogos, so vorgegeben -->",
        '<b style="color: #1db954">x</b>',                                              # 7 frei
        "<style>",
        "  .x { font-family: Arial; }",                                                 # 9 feste Schrift
        "</style>",
    ]))
    assert _regeln_der(marken_pruefen([svelte], tmp_path, MARKEN)) == [
        (2, "feste Farbe"), (4, "feste Farbe"), (4, "feste Schriftgröße"), (9, "feste Schrift")]


def test_marken_pruefen_nur_den_stil_der_app(tmp_path):
    """Entwürfe, Doku, Abhängigkeiten und Gebautes zählen nicht; die Marken des Appkerns und die Marken einer Vorlage
    sind die Wahrheit, die Bausteine einer Vorlage werden geprüft (Gegenprobe: marken.css direkt unter vorlagen)."""
    from appkern.werkzeuge import marken_pruefen

    fest = ".a { color: #fff; }\n"
    dateien = [_datei(tmp_path, n, fest) for n in (
        "mockups/stil.css", "docs/prototyp/a.css", "frontend/node_modules/x/a.css", "frontend/dist/a.css",
        "oberflaeche/stil/marken.css", "daten-vorfuehrung/a.css", "frontend/src/a.css", "oberflaeche/stil/schale.css",
        "oberflaeche/stil/vorlagen/futur/marken.css", "oberflaeche/stil/vorlagen/futur/bausteine.css",
        "oberflaeche/stil/vorlagen/marken.css")]
    assert [b.datei for b in marken_pruefen(dateien, tmp_path, set())] == [
        "frontend/src/a.css", "oberflaeche/stil/schale.css", "oberflaeche/stil/vorlagen/futur/bausteine.css",
        "oberflaeche/stil/vorlagen/marken.css"]


def test_strenge_und_haken(tmp_path, capsys):
    """Ohne gestaltung.toml wird gemeldet und der Commit geht durch; scharf hält er an (Gegenprobe)."""
    import pytest

    from appkern.werkzeuge import strenge
    from appkern.werkzeuge.__main__ import pruefen

    css = _datei(tmp_path, "frontend/src/a.css", ".a { color: #fff; }\n")
    assert strenge(tmp_path) == "melden"
    assert pruefen(tmp_path, [css]) == 0
    assert "1 Befunde der Gestaltung gemeldet" in capsys.readouterr().err
    (tmp_path / "gestaltung.toml").write_text('marken = "scharf"\n')
    assert strenge(tmp_path) == "scharf"
    assert pruefen(tmp_path, [css]) == 1
    assert "feste Farbe" in capsys.readouterr().err
    css.write_text(".a { color: var(--text); }\n")
    assert pruefen(tmp_path, [css]) == 0
    (tmp_path / "gestaltung.toml").write_text('marken = "streng"\n')
    with pytest.raises(ValueError):
        strenge(tmp_path)


def test_der_appkern_selbst_ist_sauber():
    """Schale, Bausteine und Teile des Appkerns nutzen nur die Marken."""
    import subprocess

    from appkern.werkzeuge import marken_pruefen

    wurzel = Path(__file__).resolve().parents[1]
    dateien = [wurzel / n for n in subprocess.run(["git", "ls-files"], cwd=wurzel, capture_output=True, text=True).stdout.splitlines()]
    assert marken_pruefen(dateien, wurzel) == []


def test_gestaltung_aus_der_wahrheit(tmp_path):
    """Marken mit Gruppe, Zweck und Werten je Thema und Stufe; die erzeugten Dateien gelten als veraltet, sobald sich
    die Marken ändern (Gegenprobe), und passen nach dem Schreiben wieder."""
    from appkern.werkzeuge import gestaltung

    _datei(tmp_path, "oberflaeche/stil/marken.css", "\n".join([
        "/* Kopf der Marken */",
        "/* == Schriftgrößen == Dicht als Vorgabe. */",
        ':root, [data-schrift="dicht"] {',
        "  --gross: 15px;   /* Grundschrift */",
        "}",
        "/* Stufe gross: groß für eigene Schalen */",
        '[data-schrift="gross"] { --gross: 18px; }',
        "/* == Flächen == Von hinten nach vorn. */",
        ':root, [data-theme="hell"] {',
        "  --hg: #e4eaf2;   /* Seitengrund */",
        "}",
        '[data-theme="dunkel"] { --hg: #16202c; }',
    ]))
    _datei(tmp_path, "oberflaeche/gestaltung/katalog.json", json.dumps({"muster": [{"regel": "Nur Marken", "grund": "eine Wahrheit"}],
        "bausteine": [{"familie": "schale", "name": "Knopf", "klassen": ["knopf"], "wann": "immer", "warum": "gleich",
                       "html": '<button class="knopf">Los</button>'}], "nutzen": ["stil.css laden"], "pruefung": "Haken"}))
    m = gestaltung.marken_lesen((tmp_path / "oberflaeche/stil/marken.css").read_text())
    assert m.einleitung == "Kopf der Marken" and m.stufen["gross"] == "groß für eigene Schalen"
    gross, hg = m.alle()
    assert (gross.gruppe, gross.zweck, gross.werte, gross.art) == ("Schriftgrößen", "Grundschrift",
                                                                   {"alle": "15px", "stufe:gross": "18px"}, "schriftgroesse")
    assert (hg.gruppe, hg.werte, hg.art) == ("Flächen", {"hell": "#e4eaf2", "dunkel": "#16202c"}, "farbe")
    assert gestaltung.ist_quelle(tmp_path) and set(gestaltung.veraltet(tmp_path)) == {gestaltung.DATEN, gestaltung.SEITE}
    gestaltung.schreiben(tmp_path)
    assert gestaltung.veraltet(tmp_path) == []
    seite = (tmp_path / "docs/gestaltung.md").read_text()
    assert "| `--gross` | `15px` | `15px` | `15px` | `18px` | Grundschrift |" in seite   # ohne eigenen Wert gilt dicht and '<button class="knopf">Los</button>' in seite
    css = tmp_path / "oberflaeche/stil/marken.css"
    css.write_text(css.read_text().replace("#16202c", "#16202d"))
    assert gestaltung.veraltet(tmp_path) == [gestaltung.DATEN, gestaltung.SEITE]


def test_gestaltung_des_appkerns_ist_aktuell():
    from appkern.werkzeuge import gestaltung

    assert gestaltung.veraltet(Path(__file__).resolve().parents[1]) == []


def test_klassen_der_schale_nur_aus_dem_geladenen_stil(tmp_path):
    """Die Bausteine des Leitstands liegen neben der Schale, werden von Apps in der Schale aber nicht geladen: ihre
    Klassen zählen nicht als Klassen der Schale."""
    from appkern.werkzeuge import schalen_klassen

    _datei(tmp_path, "stil/alles.css", '@import "@fontsource/barlow/400.css";\n@import "./schale.css";\n')
    _datei(tmp_path, "stil/schale.css", '@import "./teil.css";\n.knopf { color: var(--text); }\n')
    _datei(tmp_path, "stil/teil.css", ".karte { padding: 0; }\n")
    _datei(tmp_path, "stil/leitstand.css", ".verlauf { display: block; }\n")
    assert schalen_klassen(tmp_path / "stil") == {"knopf", "karte"}


def test_roter_testlauf_beim_ausrollen_zeigt_den_grund_und_hebt_alles_auf(tmp_path, monkeypatch):
    from appkern.werkzeuge import ausrollen
    monkeypatch.setattr(ausrollen, "PROTOKOLLE", tmp_path / "protokolle")
    ausgabe = ("..F.\n____ test_eins ____\n    assert x == 1\nE   assert 2 == 1\nE    +  wo x = 2\n"
               "FAILED tests/test_a.py::test_eins - assert 2 == 1\n1 failed, 3 passed\n")
    assert ausrollen.fehlerzeilen(ausgabe).splitlines() == ["____ test_eins ____", "E   assert 2 == 1", "E    +  wo x = 2",
                                                            "FAILED tests/test_a.py::test_eins - assert 2 == 1"]
    pfad = ausrollen.testprotokoll("fundus", ausgabe)
    assert pfad.parent == tmp_path / "protokolle" and pfad.name.startswith("fundus-tests-") and pfad.read_text() == ausgabe
    viele = "\n".join(f"E   zeile {i}" for i in range(50))
    assert ausrollen.fehlerzeilen(viele).splitlines()[-1] == "... (10 weitere)"


def _ziel(**mehr):
    from appkern.werkzeuge.ausrollen import Ziel
    return Ziel.model_validate({"kennung": "probe", "rechner": "pi@pi", "wurzel": "/srv/probe", "adresse": "https://pi:1",
                                "repo": "x", "namen": ["pi"], **mehr})


def test_sicherung_vor_dem_ausrollen_im_neuen_abbild_mit_eigenen_ordnern():
    """Das Ausrollen sichert nicht mehr selbst, sondern ruft den Baustein im eben gebauten Abbild der App: dieselbe
    Regel und dieselben Einstellungen wie in der App, Daten und Sicherungen eigens eingebunden, Ordner als Nutzer des Pi
    angelegt."""
    import shlex

    from appkern.werkzeuge.ausrollen import sicherungs_skript

    skript = sicherungs_skript(_ziel(compose="compose.test.yml"))
    assert "mkdir -p daten sicherungen" in skript
    befehl = shlex.split(skript.split("\n", 3)[3].replace("\\\n", " "))
    assert befehl[:9] == ["docker", "compose", "-f", "compose.test.yml", "run", "--rm", "--no-deps", "-T", "-v"]
    assert befehl[9:12] == ["/srv/probe/daten:/sicherung/daten", "-v", "/srv/probe/sicherungen:/sicherung/sicherungen"]
    assert befehl[12:] == ["probe", "python", "-m", "appkern.sicherung", "vor-ausrollen", "--kennung", "probe",
                           "--datenbank", "/sicherung/daten/probe.sqlite", "--ordner", "/sicherung/sicherungen"]


def test_aufraeumen_nur_nach_gelungenem_ausrollen_mit_grenze_aus_der_einstellung(tmp_path, monkeypatch, capsys):
    """Nach einem gelungenen Ausrollen: verwaiste Abbilder weg, Baucache bis zur Grenze; nach einem Abbruch bleibt
    alles (das alte Abbild ist der Rückweg); ein gescheitertes Aufräumen ist nur eine Warnung."""
    from appkern.werkzeuge import ausrollen

    assert ausrollen.aufgeraeumt("Deleted Images:\ndeleted: sha256:ab\n\nTotal reclaimed space: 1.2GB\n",
                                 "ID\tRECLAIMABLE\tSIZE\nxy\ttrue\t3GB\nTotal:\t4.5GB\n", 20) == \
        "Aufgeräumt: verwaiste Abbilder 1.2GB, Baucache 4.5GB freigegeben (Grenze 20 GB)"
    assert ausrollen.aufgeraeumt("", "", 7) == "Aufgeräumt: verwaiste Abbilder 0B, Baucache 0B freigegeben (Grenze 7 GB)"

    (tmp_path / "deploy").mkdir()
    (tmp_path / "deploy" / "ausrollen.toml").write_text('kennung = "probe"\nrechner = "pi@pi"\nwurzel = "/srv/probe"\n'
                                                        'adresse = "https://pi:1"\nrepo = "x"\nnamen = ["pi"]\n')
    assert ausrollen.laden(tmp_path, umgebung={}).baucache_gb == 20
    assert ausrollen.laden(tmp_path, umgebung={"BAUCACHE_GB": "35"}).baucache_gb == 35

    befehle: list[str] = []

    def ssh(z, skript):
        befehle.append(skript)
        return "Total reclaimed space: 2GB" if "image prune" in skript else "Total:\t9GB"

    monkeypatch.setattr(ausrollen, "_ssh", ssh)
    for schritt in ("stand_und_tests", "pi_pruefen", "zertifikat", "stand_holen", "bauen", "ruhe_abwarten", "sichern",
                    "starten", "pruefen", "fortsetzen"):
        monkeypatch.setattr(ausrollen, schritt, lambda *a, **k: None)
    monkeypatch.setenv("BAUCACHE_GB", "12")
    assert ausrollen.ausrollen(tmp_path) == 0
    assert befehle == ["docker image prune -f", "docker builder prune -f --max-used-space 12GB"]
    assert "Baucache 9GB freigegeben (Grenze 12 GB)" in capsys.readouterr().out

    befehle.clear()

    def faellt(*a, **k):
        raise ausrollen.Abbruch("Fassungen passen nicht zusammen")

    monkeypatch.setattr(ausrollen, "pruefen", faellt)
    assert ausrollen.ausrollen(tmp_path) == 1
    assert befehle == [], "nach einem Fehlschlag wird nicht aufgeräumt"

    monkeypatch.setattr(ausrollen, "pruefen", lambda *a, **k: None)
    monkeypatch.setattr(ausrollen, "_ssh", faellt)
    assert ausrollen.ausrollen(tmp_path) == 0
    assert "Warnung: Aufräumen ging nicht" in capsys.readouterr().out
