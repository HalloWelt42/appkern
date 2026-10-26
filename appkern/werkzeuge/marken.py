"""Prüfung der Gestaltung gegen die Marken des Appkerns (Grunddesign, Nutzer 24.10.2026: "Nur Marken, Ausnahme
begründet").

Farben, Schriften und Schriftgrößen stehen an genau einer Stelle: in den Marken des Appkerns
(`oberflaeche/stil/marken.css`, CSS-Variablen). Der Stil einer App nutzt nur diese Marken; eine neue Farbe kommt zuerst
dorthin. Befunde:

- feste Farbe: `#rgb` bis `#rrggbbaa`, Farbfunktionen (`rgb`, `hsl`, `hwb`, `lab`, `lch`, `oklab`, `oklch`, `color`)
  ohne Marke in den Kanälen, Farbnamen (`white`, `red`, ...) in Farbeigenschaften. Erlaubt sind Marken (`var(...)`),
  `currentColor`, `transparent` und Mischungen aus Marken (`color-mix(in srgb, var(--gut) 20%, transparent)`).
- feste Schrift: `font-family` oder `font` mit einem Schriftnamen statt `var(--schrift...)` oder `inherit`; auch eine
  eigene Marke mit einer Schriftliste (`--mono: "Name", monospace`).
- feste Schriftgröße: `font-size` oder `font` mit absoluter Größe (`px`, `pt`, `rem`, ...) oder einem Schlüsselwort
  wie `small`. Erlaubt sind Marken, Rechnungen mit Marken (`calc(var(--gross) + 2px)`), relative Größen (`em`, `%`,
  `smaller`) und `0`. Symbole (Regeln, deren Ziel ein `i`, eine Klasse `fa-...` oder ein `svg` ist) dürfen feste
  Größen haben: sie sitzen in Kästen fester Größe und sind keine Schrift zum Lesen.
- Marke überschrieben: eine Marke des Appkerns bekommt im Stil einer App einen festen Wert.
- im Markup (Svelte, HTML): die Attribute `fill`, `stroke`, `stop-color`, `flood-color`, `color` mit fester Farbe,
  `font-size` und `font-family` mit festem Wert; Ausdrücke in `{...}` gelten als Werte der App und bleiben frei.

Ausnahme: ein Kommentar `Ausnahme: <Grund>` (mindestens drei Wörter Grund) in derselben Zeile, in der Zeile darüber
oder über einer Regel (dann für die ganze Regel); im Markup als `<!-- Ausnahme: <Grund> -->`.

Geprüft werden CSS-, Svelte- und HTML-Dateien außerhalb von Entwürfen (`mockups`, `docs`), Abhängigkeiten und
Gebautem. Die Marken selbst sind die Wahrheit und bleiben frei, ebenso die Marken einer Vorlage
(`oberflaeche/stil/vorlagen/<name>/marken.css`): ihre Werte für ein anderes Aussehen; die Bausteine der Vorlage daneben
werden geprüft wie jeder Stil. Ob ein Befund den Commit aufhält, sagt
`gestaltung.toml` im Wurzelordner (`marken = "scharf"`); ohne diese Angabe wird nur gemeldet, damit eine App erst
sauber wird und dann scharf geschaltet werden kann.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .befund import Befund
from .stil import deklarationen, regeln

MARKEN_IM_APPKERN = Path("oberflaeche") / "stil" / "marken.css"
#: Marken einer Vorlage (vorlagen/<name>/marken.css): die Werte eines anderen Aussehens, frei wie die Marken selbst
VORLAGEN = Path("oberflaeche") / "stil" / "vorlagen"
MARKEN_IM_PAKET = Path("frontend") / "node_modules" / "appkern-oberflaeche" / "oberflaeche" / "stil" / "marken.css"
EINSTELLUNG = "gestaltung.toml"
Strenge = Literal["melden", "scharf"]

# Ordner, deren Dateien nicht zum Stil der App gehören: Entwürfe, Doku, Abhängigkeiten, Gebautes, Probestände
NICHT_GEPRUEFT = {"node_modules", "dist", "mockups", "docs", "prototyp", ".probe", ".probelauf", ".venv", "tests"}
ENDUNGEN = (".css", ".svelte", ".html")

FARBNAMEN = frozenset("""
aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue blueviolet brown burlywood cadetblue
chartreuse chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey
darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen darkslateblue darkslategray
darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite forestgreen
fuchsia gainsboro ghostwhite gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki
lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen
lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime
limegreen linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive
olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum
powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell sienna silver
skyblue slateblue slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet wheat white
whitesmoke yellow yellowgreen""".split())
FARBEIGENSCHAFTEN = {
    "color", "background", "background-color", "background-image", "border", "border-color", "border-top",
    "border-right", "border-bottom", "border-left", "border-block", "border-inline", "border-top-color",
    "border-right-color", "border-bottom-color", "border-left-color", "border-block-start", "border-block-end",
    "border-inline-start", "border-inline-end", "outline", "outline-color", "box-shadow", "text-shadow", "fill", "stroke",
    "caret-color", "accent-color", "text-decoration", "text-decoration-color", "column-rule", "column-rule-color",
    "stop-color", "flood-color", "lighting-color", "scrollbar-color", "-webkit-tap-highlight-color", "filter",
    "text-emphasis-color", "-webkit-text-fill-color", "-webkit-text-stroke-color", "-webkit-text-stroke"}
FREIE_WERTE = {"inherit", "initial", "unset", "revert", "revert-layer"}
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FARBFUNKTION = re.compile(r"\b(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(")
ABSOLUT = re.compile(r"(?<![\w.-])(\d*\.?\d+)(px|pt|pc|cm|mm|in|q|rem|vw|vh|vmin|vmax|svh|lvh|dvh|svw|lvw|dvw)\b", re.I)
GROESSEN_WORTE = {"xx-small", "x-small", "small", "medium", "large", "x-large", "xx-large", "xxx-large"}
AUSNAHME = re.compile(r"Ausnahme:\s*(\S+(?:\s+\S+){2,})")
SCHRIFTFAMILIE = re.compile(r"(?<![\w-])(sans-serif|serif|monospace|cursive|fantasy|system-ui|ui-monospace|ui-sans-serif|ui-serif)(?![\w-])")
SYMBOL_ZIEL = re.compile(r"(^|[\s>+~])(i|svg)(?=$|[.:\[#])|\.fa-[\w-]+")
MARKUP_FARBE = ("fill", "stroke", "stop-color", "flood-color", "color")
MARKUP_SCHRIFT = ("font-size", "font-family")


@dataclass
class _Kommentar:
    von: int
    bis: int
    ausnahme: bool


def strenge(wurzel: Path) -> Strenge:
    """Wie streng die Prüfung in diesem Repo ist (`gestaltung.toml`, Vorgabe melden)."""
    datei = wurzel / EINSTELLUNG
    if not datei.is_file():
        return "melden"
    wert = tomllib.loads(datei.read_text(encoding="utf-8")).get("marken", "melden")
    if wert not in ("melden", "scharf"):
        raise ValueError(f"{EINSTELLUNG}: marken ist \"melden\" oder \"scharf\", nicht {wert!r}")
    return wert


def marken_datei(wurzel: Path) -> Path | None:
    """Die Marken, die für dieses Repo gelten: im Appkern selbst seine eigenen, in einer App die des eingebundenen
    Pakets (der Stand, gegen den sie gebaut wird)."""
    for kandidat in (wurzel / MARKEN_IM_APPKERN, wurzel / MARKEN_IM_PAKET):
        if kandidat.is_file():
            return kandidat
    return None


def marken_namen(datei: Path | None) -> set[str]:
    if datei is None:
        return set()
    return {name for r in regeln(datei.read_text(encoding="utf-8")) for name, _, _ in deklarationen(r.deklarationen)
            if name.startswith("--")}


def gehoert_zum_stil(p: Path, wurzel: Path) -> bool:
    if p.suffix not in ENDUNGEN or not p.is_file():
        return False
    try:
        teile = p.relative_to(wurzel).parts
    except ValueError:
        return False
    if any(t in NICHT_GEPRUEFT or t.startswith("daten") for t in teile[:-1]):
        return False
    pfad = Path(*teile)
    vorlagen_marken = pfad.name == "marken.css" and pfad.parent.parent == VORLAGEN
    return pfad != MARKEN_IM_APPKERN and not vorlagen_marken


# ----- Werte -----

def _ohne_klammer(wert: str, name: str) -> str:
    """Entfernt Aufrufe wie var(...) oder url(...) samt verschachtelter Klammern."""
    while (start := re.search(rf"\b{name}\(", wert)) is not None:
        tiefe, i = 0, start.end() - 1
        while i < len(wert):
            if wert[i] == "(":
                tiefe += 1
            elif wert[i] == ")":
                tiefe -= 1
                if tiefe == 0:
                    break
            i += 1
        wert = wert[:start.start()] + " " + wert[i + 1:]
    return wert


def _gesaeubert(wert: str) -> str:
    wert = re.sub(r"\"[^\"]*\"|'[^']*'", " ", wert)     # Texte (content, Rasterflächen)
    return _ohne_klammer(wert, "url")


def _farbfunktion_fest(wert: str) -> bool:
    for m in FARBFUNKTION.finditer(wert):
        tiefe, i = 0, m.end() - 1
        while i < len(wert):
            tiefe += {"(": 1, ")": -1}.get(wert[i], 0)
            if tiefe == 0:
                break
            i += 1
        if "var(" not in wert[m.end():i]:
            return True
    return False


def feste_farbe(eigenschaft: str, wert: str) -> bool:
    wert = _gesaeubert(wert)
    if HEX.search(wert) or _farbfunktion_fest(wert):
        return True
    worte = re.findall(r"[a-zA-Z-]+", _ohne_klammer(wert, "var").lower())
    if eigenschaft.startswith("--"):
        return len(worte) == 1 and worte[0] in FARBNAMEN and wert.strip().lower() == worte[0]
    return eigenschaft in FARBEIGENSCHAFTEN and any(w in FARBNAMEN for w in worte)


def feste_groesse(wert: str) -> bool:
    w = _gesaeubert(wert).strip().lower()
    if "var(" in w or w in FREIE_WERTE:
        return False
    if any(t in GROESSEN_WORTE for t in re.findall(r"[a-z-]+", w)):
        return True
    return any(float(m.group(1)) != 0 for m in ABSOLUT.finditer(w))


def feste_schrift(wert: str) -> bool:
    w = wert.strip().lower()
    if w in FREIE_WERTE:
        return False
    return bool(_ohne_klammer(w, "var").replace(",", " ").strip())


def _font_kurz(wert: str) -> str | None:
    """Regel für die Kurzform `font`: frei sind inherit und Marken, sonst setzt sie eine Schrift (und meist eine Größe)."""
    w = wert.strip().lower()
    if w in FREIE_WERTE or w.startswith("var("):
        return None
    if feste_groesse(_ohne_klammer(w, "var")):
        return "feste Schriftgröße"
    return "feste Schrift" if "var(--schrift" not in w else None


def _ziel(selektor: str) -> str:
    """Das letzte zusammengesetzte Glied eines Selektors ohne Pseudo-Elemente (`.a > i.fa-x::before` ergibt `i.fa-x`)."""
    ohne = re.sub(r"::?(before|after)\b", "", re.sub(r":global\(([^)]*)\)", r"\1", selektor)).strip()
    return re.split(r"\s*[\s>+~]\s*", ohne)[-1] if ohne else ""


def _symbol_regel(selektoren: list[str]) -> bool:
    """Trifft die Regel nur Symbole (i, svg, Klassen fa-...)?"""
    return bool(selektoren) and all(SYMBOL_ZIEL.search(" " + _ziel(s)) for s in selektoren)


def deklaration_pruefen(name: str, wert: str, marken: set[str], symbol: bool = False) -> str | None:
    """Regel, die eine Deklaration verletzt, oder None."""
    if name.startswith("--"):
        if name in marken and _ohne_klammer(_gesaeubert(wert), "var").replace(",", " ").strip() not in ("", *FREIE_WERTE):
            return "Marke des Appkerns überschrieben"
        if feste_farbe(name, wert):
            return "feste Farbe"
        # eine eigene Marke mit einer Schriftliste ("Name", ..., monospace) ist eine feste Schrift
        return "feste Schrift" if SCHRIFTFAMILIE.search(_ohne_klammer(wert, "var")) else None
    if name == "font-family":
        return "feste Schrift" if feste_schrift(wert) else None
    if name == "font-size":
        return "feste Schriftgröße" if feste_groesse(wert) and not symbol else None
    if name == "font":
        regel = _font_kurz(wert)
        return None if regel == "feste Schriftgröße" and symbol else regel
    return "feste Farbe" if feste_farbe(name, wert) else None


# ----- Kommentare und Ausnahmen -----

def _kommentare(text: str, erste_zeile: int, muster: str) -> list[_Kommentar]:
    aus = []
    for m in re.finditer(muster, text, flags=re.S):
        von = erste_zeile + text.count("\n", 0, m.start())
        aus.append(_Kommentar(von, von + m.group(0).count("\n"), bool(AUSNAHME.search(m.group(0)))))
    return aus


def _ausgenommen(zeile: int, kommentare: list[_Kommentar], regelzeile: int | None = None) -> bool:
    for k in kommentare:
        if not k.ausnahme:
            continue
        if k.von <= zeile <= k.bis or k.bis == zeile - 1:
            return True
        if regelzeile is not None and (k.von <= regelzeile <= k.bis or k.bis == regelzeile - 1):
            return True
    return False


# ----- Dateien -----

def _css_pruefen(block: str, erste: int, datei: str, marken: set[str]) -> list[Befund]:
    kommentare = _kommentare(block, erste, r"/\*.*?\*/")
    befunde = []
    for r in regeln(block, erste):
        symbol = _symbol_regel(r.selektoren)
        for name, wert, versatz in deklarationen(r.deklarationen):
            regel = deklaration_pruefen(name, wert, marken, symbol)
            zeile = r.zeile + versatz
            if regel and not _ausgenommen(zeile, kommentare, r.zeile):
                befunde.append(Befund(datei=datei, zeile=zeile, regel=regel, text=f"{name}: {wert}"))
    return befunde


def _stil_angabe_pruefen(angabe: str, zeile: int, datei: str, marken: set[str], kommentare: list[_Kommentar],
                         symbol: bool = False) -> list[Befund]:
    befunde = []
    for name, wert, _ in deklarationen(re.sub(r"\{[^}]*\}", "0", angabe)):
        regel = deklaration_pruefen(name, wert, marken, symbol)
        if regel and not _ausgenommen(zeile, kommentare):
            befunde.append(Befund(datei=datei, zeile=zeile, regel=regel, text=f"{name}: {wert}"))
    return befunde


def _tag_davor(markup: str, stelle: int) -> str:
    """Name des Elements, in dessen Anfangsmarke diese Stelle steht (`<i class="..." style="...">` ergibt `i`)."""
    m = re.search(r"<([A-Za-z][\w:-]*)[^<]*$", markup[:stelle])
    return m.group(1).lower() if m else ""


def _markup_pruefen(text: str, datei: str, marken: set[str]) -> list[Befund]:
    # Skripte und Stilblöcke zählen nicht als Markup; Zeilen bleiben erhalten
    markup = re.sub(r"<(script|style)\b.*?</\1>", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S)
    kommentare = _kommentare(markup, 1, r"<!--.*?-->") + _kommentare(markup, 1, r"/\*.*?\*/")
    befunde: list[Befund] = []
    for m in re.finditer(r'\sstyle="([^"]*)"', markup):
        befunde += _stil_angabe_pruefen(m.group(1), markup.count("\n", 0, m.start()) + 1, datei, marken, kommentare,
                                        _tag_davor(markup, m.start()) in ("i", "svg"))
    for m in re.finditer(r'\sstyle:([a-z-]+)="([^"{]*)"', markup):
        befunde += _stil_angabe_pruefen(f"{m.group(1)}: {m.group(2)}", markup.count("\n", 0, m.start()) + 1, datei, marken,
                                        kommentare)
    for m in re.finditer(r'\s(' + "|".join(MARKUP_FARBE + MARKUP_SCHRIFT) + r')="([^"{]*)"', markup):
        name, wert = m.group(1), m.group(2)
        zeile = markup.count("\n", 0, m.start()) + 1
        if name in MARKUP_FARBE:
            regel = "feste Farbe" if wert.lower() not in ("none", "currentcolor", "transparent", "inherit") and \
                feste_farbe("color", wert) else None
        elif name == "font-size":
            regel = "feste Schriftgröße" if wert.strip() and (feste_groesse(wert) or re.fullmatch(r"\d*\.?\d+", wert.strip())) else None
        else:
            regel = "feste Schrift" if feste_schrift(wert) else None
        if regel and not _ausgenommen(zeile, kommentare):
            befunde.append(Befund(datei=datei, zeile=zeile, regel=regel, text=f'{name}="{wert}"'))
    return befunde


def marken_pruefen(dateien: list[Path], wurzel: Path, marken: set[str] | None = None) -> list[Befund]:
    """Befunde der Gestaltung in den Dateien, die zum Stil gehören. `marken`: Namen der Marken des Appkerns (Vorgabe:
    aus dem Repo gelesen); eine davon mit festem Wert zu belegen ist ein Befund."""
    if marken is None:
        marken = marken_namen(marken_datei(wurzel))
    befunde: list[Befund] = []
    for p in dateien:
        if not gehoert_zum_stil(p, wurzel):
            continue
        name = str(p.relative_to(wurzel))
        text = p.read_text(encoding="utf-8", errors="replace")
        if p.suffix == ".css":
            befunde += _css_pruefen(text, 1, name, marken)
            continue
        for m in re.finditer(r"<style[^>]*>(.*?)</style>", text, flags=re.S):
            befunde += _css_pruefen(m.group(1), text.count("\n", 0, m.start(1)) + 1, name, marken)
        befunde += _markup_pruefen(text, name, marken)
    return sorted(befunde, key=lambda b: (b.datei, b.zeile))


def zusammenfassung(befunde: list[Befund]) -> str:
    """Zahl je Regel, etwa "12 feste Farbe, 3 feste Schriftgröße"."""
    je: dict[str, int] = {}
    for b in befunde:
        je[b.regel] = je.get(b.regel, 0) + 1
    return ", ".join(f"{n} {r}" for r, n in sorted(je.items(), key=lambda x: -x[1]))
