"""Stilprüfung der Oberfläche (Lehren 1 und 2 der Transkription).

- kein `!important` (die Kaskade löst Konflikte über Spezifität und Reihenfolge)
- keine einseitigen Streifen: Rahmen oder Schatten mit Versatz zu einer Seite ohne Unschärfe (`border-left`,
  `inset 3px 0 0`, Unterstreichung des aktiven Reiters); erlaubt sind nur Trennlinien von 1px in einer Randfarbe
  (`var(--rand)`, `var(--rand-stark)`) zwischen Flächen
- keine Regeln auf Klassen der Schale: eine App-Regel muss eine eigene Klasse tragen (auch als Erweiterung wie
  `.knopf.klein`); sonst ändert sie Teile der Schale mit (so lief die Statuszeile der Einstellungen über)

Geprüft werden CSS-Dateien, `<style>`-Blöcke und `style`-Angaben in Svelte und HTML; Klassen nur in CSS-Dateien und
`:global(...)`, weil Svelte die Regeln seiner Blöcke ohnehin auf die eigene Komponente begrenzt.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .befund import Befund

KLASSE = re.compile(r"\.(-?[A-Za-z_][\w-]*)")
LAENGE = re.compile(r"^(-?\d*\.?\d+)(px|rem|em)?$")
EINSEITIG_SENKRECHT = {"border-left", "border-right", "border-inline-start", "border-inline-end",
                       "border-left-width", "border-right-width", "border-inline-start-width", "border-inline-end-width"}
EINSEITIG_WAAGRECHT = {"border-top", "border-bottom", "border-block-start", "border-block-end",
                       "border-top-width", "border-bottom-width"}
OHNE = {"0", "0px", "none", "hidden", "initial", "unset", "inherit"}


@dataclass
class Regel:
    selektoren: list[str]
    deklarationen: str
    zeile: int          # Zeile des Selektors
    im_rahmen: str      # umgebende @-Regel ("" oben)


def _ohne_kommentare(text: str) -> str:
    # Kommentare durch Leerraum gleicher Zeilenzahl ersetzen, damit die Zeilennummern stimmen
    return re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)


def regeln(text: str, erste_zeile: int = 1) -> list[Regel]:
    text = _ohne_kommentare(text)
    gefunden: list[Regel] = []
    rahmen: list[str] = []          # Stapel der Vorspänne offener Blöcke
    anfang = 0                      # Beginn des laufenden Vorspanns
    i = 0
    while i < len(text):
        z = text[i]
        if z == "{":
            vorspann = text[anfang:i].strip()
            zeile = erste_zeile + text.count("\n", 0, anfang + (len(text[anfang:i]) - len(text[anfang:i].lstrip())))
            if vorspann.startswith("@"):
                rahmen.append(vorspann)
                anfang = i + 1
            else:
                ende = text.find("}", i)
                ende = len(text) if ende < 0 else ende
                selektoren = [s.strip() for s in _teilen(vorspann) if s.strip()]
                gefunden.append(Regel(selektoren, text[i + 1:ende], zeile, rahmen[-1] if rahmen else ""))
                i = ende
                anfang = i + 1
        elif z == "}":
            if rahmen:
                rahmen.pop()
            anfang = i + 1
        elif z == ";" and text[anfang:i].strip().startswith("@"):
            anfang = i + 1          # Anweisungen wie @import gehören zu keinem Block
        i += 1
    return gefunden


def _teilen(liste: str, trenner: str = ",") -> list[str]:
    """Trennt an `trenner` außerhalb von Klammern."""
    teile, tiefe, start = [], 0, 0
    for i, z in enumerate(liste):
        if z in "([":
            tiefe += 1
        elif z in ")]":
            tiefe -= 1
        elif z == trenner and tiefe == 0:
            teile.append(liste[start:i])
            start = i + 1
    teile.append(liste[start:])
    return teile


def deklarationen(block: str) -> list[tuple[str, str, int]]:
    """(Eigenschaft, Wert, Zeilenversatz im Block)"""
    aus = []
    pos = 0
    for teil in _teilen(block, ";"):
        if ":" in teil:
            name, wert = teil.split(":", 1)
            versatz = block.count("\n", 0, pos + len(teil) - len(teil.lstrip()))
            aus.append((name.strip().lower(), wert.strip(), versatz))
        pos += len(teil) + 1
    return aus


def _laenge(token: str) -> float | None:
    m = LAENGE.match(token)
    if not m:
        return None
    zahl = float(m.group(1))
    return zahl * 16 if m.group(2) in ("rem", "em") else zahl


def _rahmenbreite(wert: str) -> float:
    """Breite aus einer Rahmenangabe (`2px solid ...`, `thin`, `0`); unbekannt zählt als 1px."""
    for token in wert.split():
        if token in OHNE:
            return 0
        if token == "thin":
            return 1
        if token in ("medium", "thick"):
            return 3
        laenge = _laenge(token)
        if laenge is not None:
            return laenge
    return 0 if wert.strip() in OHNE else 1


RANDFARBE = re.compile(r"var\(--(?:ls-)?rand(?:-stark)?\b")


def _trennlinie(wert: str, breite: float) -> bool:
    """Neutrale Trennlinie zwischen Flächen: höchstens 1px, in einer Randfarbe (--rand, --rand-stark; in Entwürfen der
    Leitstelle --ls-rand) oder unsichtbar."""
    return breite <= 1 and (bool(RANDFARBE.search(wert)) or "transparent" in wert)


def _streifen_im_schatten(wert: str) -> str | None:
    for schatten in _teilen(wert):
        tokens = [t for t in re.sub(r"\([^)]*\)", "()", schatten).split()]
        laengen = [l for t in tokens if (l := _laenge(t)) is not None]
        if len(laengen) < 2:
            continue
        x, y = laengen[0], laengen[1]
        unschaerfe = laengen[2] if len(laengen) > 2 else 0
        ausdehnung = laengen[3] if len(laengen) > 3 else 0
        if unschaerfe == 0 and ausdehnung == 0 and (x == 0) != (y == 0) and not _trennlinie(schatten, abs(x or y)):
            return schatten.strip()
    return None


def _deklarationen_pruefen(block: str, zeile: int, datei: str) -> list[Befund]:
    befunde = []
    for name, wert, versatz in deklarationen(block):
        wo = zeile + versatz
        text = f"{name}: {wert}"
        if "!important" in wert.replace(" ", ""):
            befunde.append(Befund(datei=datei, zeile=wo, regel="!important", text=text))
        if name in EINSEITIG_SENKRECHT | EINSEITIG_WAAGRECHT and (breite := _rahmenbreite(wert)) > 0 and not _trennlinie(wert, breite):
            befunde.append(Befund(datei=datei, zeile=wo, regel="einseitiger Rahmen", text=text))
        elif name == "border-width":
            breiten = [_rahmenbreite(t) for t in wert.split()]
            if len(set(breiten)) > 1:
                befunde.append(Befund(datei=datei, zeile=wo, regel="einseitiger Rahmen", text=text))
        elif name == "box-shadow" and (streifen := _streifen_im_schatten(wert)):
            befunde.append(Befund(datei=datei, zeile=wo, regel="einseitiger Schatten", text=f"{name}: {streifen}"))
    return befunde


def _klassen(selektor: str) -> set[str]:
    return set(KLASSE.findall(re.sub(r"\[[^\]]*\]", "", selektor)))


def _geladene_stile(stil: Path) -> list[Path]:
    """Die Stile, die eine App in der Schale lädt: alles.css und was es einbindet (nicht etwa die Bausteine des
    Leitstands, die nur Apps mit eigener Schale laden)."""
    einstieg = stil / "alles.css"
    if not einstieg.is_file():
        return sorted(stil.glob("*.css"))
    gefunden: list[Path] = []
    offen = [einstieg]
    while offen:
        datei = offen.pop(0)
        if datei in gefunden or not datei.is_file():
            continue
        gefunden.append(datei)
        for name in re.findall(r'@import\s+"\./([^"]+\.css)"', datei.read_text(encoding="utf-8")):
            offen.append(stil / name)
    return gefunden


def schalen_klassen(stil: Path, teile: Path | None = None) -> set[str]:
    """Klassen der Schale: aus den Stilen, die stil.css lädt, und aus den Vorlagen ihrer Teile (dort benutzt, auch ohne
    eigene Regel)."""
    klassen: set[str] = set()
    for css in _geladene_stile(stil):
        for r in regeln(css.read_text(encoding="utf-8")):
            for s in r.selektoren:
                klassen |= _klassen(s)
    if teile:
        for svelte in sorted(teile.rglob("*.svelte")):
            text = svelte.read_text(encoding="utf-8")
            for wert in re.findall(r'\bclass="([^"]*)"', text):
                klassen |= {k for k in re.sub(r"\{[^}]*\}", " ", wert).split() if re.fullmatch(r"[A-Za-z_][\w-]*", k)}
            klassen |= set(re.findall(r"\bclass:([A-Za-z_][\w-]*)", text))
    return klassen


def _kollision(selektor: str, schale: set[str]) -> str | None:
    if selektor.startswith(("from", "to")) or re.fullmatch(r"[\d.]+%", selektor):
        return None
    if ":root" in selektor or selektor.startswith(("html", "body", "*")):
        return None
    klassen = _klassen(selektor)
    if klassen and klassen <= schale:
        return ", ".join(sorted(klassen))
    return None


def _style_bloecke(text: str) -> list[tuple[str, int]]:
    return [(m.group(1), text.count("\n", 0, m.start(1)) + 1)
            for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, flags=re.S)]


def stil_pruefen(dateien: list[Path], wurzel: Path, schale: set[str] | None = None) -> list[Befund]:
    """Prüft die Dateien; `schale` (Klassen der Schale) nur für Apps, nicht für den Appkern selbst."""
    befunde: list[Befund] = []
    for p in dateien:
        if "node_modules" in p.parts or not p.is_file() or p.suffix not in (".css", ".svelte", ".html"):
            continue
        name = str(p.relative_to(wurzel))
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix == ".css":
            bloecke = [(text, 1)]
        else:
            bloecke = _style_bloecke(text)
            for m in re.finditer(r'\bstyle="([^"]*)"', text):
                befunde += _deklarationen_pruefen(m.group(1), text.count("\n", 0, m.start()) + 1, name)
        for block, erste in bloecke:
            for r in regeln(block, erste):
                befunde += _deklarationen_pruefen(r.deklarationen, r.zeile, name)
                if schale is None or r.im_rahmen.startswith("@keyframes"):
                    continue
                for s in r.selektoren:
                    if p.suffix != ".css":
                        global_teile = re.findall(r":global\(([^)]*)\)", s)
                        if not global_teile:
                            continue
                        s = " ".join(global_teile)
                    if klassen := _kollision(s, schale):
                        befunde.append(Befund(datei=name, zeile=r.zeile, regel="Regel auf Klassen der Schale",
                                              text=f"{s} ({klassen})"))
    return befunde
