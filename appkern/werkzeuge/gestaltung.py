"""Gestaltung aus der einen Wahrheit erzeugen: aus den Marken (`oberflaeche/stil/marken.css`, je Marke ihr Zweck als
Kommentar) und dem Katalog (`oberflaeche/gestaltung/katalog.json`: Muster mit Grund, Bausteine mit Beispiel, wann und
warum) entstehen

- `oberflaeche/gestaltung/marken.json`: die Marken als Daten für die Seite Gestaltung in jeder App
  (`teile/Gestaltung.svelte`, unter Einstellungen), dort hell und dunkel echt gerendert;
- `docs/gestaltung.md`: die Seite für das Handbuch (Farben, Schriften, Größen, Muster, Bausteine mit Markup), die das
  Werkzeug Handbuch übernimmt und die über Fundus (Quelle Entwicklung) auffindbar ist.

    python -m appkern.werkzeuge gestaltung            beide Dateien neu schreiben
    python -m appkern.werkzeuge gestaltung --pruefen  nur prüfen, ob sie zum Stand der Wahrheit passen

Der Haken des Appkerns schreibt sie bei jedem Commit neu, der Marken oder Katalog ändert; `pruefen` meldet veraltete.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

MARKEN = Path("oberflaeche") / "stil" / "marken.css"
KATALOG = Path("oberflaeche") / "gestaltung" / "katalog.json"
DATEN = Path("oberflaeche") / "gestaltung" / "marken.json"
SEITE = Path("docs") / "gestaltung.md"
QUELLEN = (MARKEN, KATALOG)

GRUPPENKOPF = re.compile(r"^/\*\s*==\s*(.+?)\s*==\s*(.*?)\s*\*/$", re.S)
DEKLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+?)\s*;[ \t]*(?:/\*(.*?)\*/)?", re.S)
FARBE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?|color-mix|linear-gradient)\(")
ART_DER_GRUPPE = {"Schriften": "schrift", "Schriftgrößen": "schriftgroesse", "Maße": "mass", "Abstände": "mass",
                  "Ecken": "mass", "Bewegung": "zeit", "Schatten und Schleier": "schatten"}
STUFEN = ("dicht", "klein", "mittel", "gross")
THEMEN = ("hell", "dunkel")


@dataclass
class Marke:
    name: str
    gruppe: str
    zweck: str = ""
    werte: dict[str, str] = field(default_factory=dict)   # alle, hell, dunkel, stufe:<name>

    @property
    def art(self) -> str:
        if self.gruppe in ART_DER_GRUPPE:
            return ART_DER_GRUPPE[self.gruppe]
        return "farbe" if any(FARBE.search(w) or w.startswith("var(") for w in self.werte.values()) else "wert"


@dataclass
class Gruppe:
    name: str
    text: str
    marken: list[Marke] = field(default_factory=list)


@dataclass
class Marken:
    einleitung: str
    gruppen: list[Gruppe]
    stufen: dict[str, str]          # Stufe -> Erklärung

    def alle(self) -> list[Marke]:
        return [m for g in self.gruppen for m in g.marken]


def _ohne_rahmen(kommentar: str) -> str:
    text = re.sub(r"^/\*|\*/$", "", kommentar.strip())
    return re.sub(r"\s*\n\s*", " ", text).strip()


def _kontexte(selektor: str) -> list[str]:
    kontexte = []
    for teil in selektor.split(","):
        teil = teil.strip()
        if m := re.search(r'data-theme="(\w+)"', teil):
            kontexte.append(m.group(1))
        elif m := re.search(r'data-schrift="(\w+)"', teil):
            kontexte.append("stufe:" + m.group(1))
        elif teil == ":root":
            kontexte.append("alle")
    # ":root, [data-theme=hell]" ist das helle Thema (Vorgabe), ":root, [data-schrift=dicht]" die Vorgabe für alle
    if "hell" in kontexte:
        return ["hell"]
    return ["alle"] if "alle" in kontexte else kontexte


def marken_lesen(text: str) -> Marken:
    """Liest die Marken mit Gruppen, Zweck und Werten je Thema und Stufe."""
    einleitung, gruppen, stufen = "", [], {}
    nach_name: dict[str, Marke] = {}
    gruppe: Gruppe | None = None
    letzter_kommentar = ""
    i = 0
    for m in re.finditer(r"/\*.*?\*/|[^{}/]+\{[^}]*\}", text, flags=re.S):
        stueck = m.group(0).strip()
        if stueck.startswith("/*"):
            if kopf := GRUPPENKOPF.match(stueck):
                gruppe = Gruppe(kopf.group(1), re.sub(r"\s*\n\s*", " ", kopf.group(2)).strip())
                gruppen.append(gruppe)
            elif not einleitung and i == 0:
                einleitung = _ohne_rahmen(stueck)
            else:
                letzter_kommentar = re.sub(r"^Stufe \w+:\s*", "", _ohne_rahmen(stueck))
            i += 1
            continue
        i += 1
        selektor, rumpf = stueck.split("{", 1)
        rumpf = rumpf.rstrip("}")
        # Kommentare vor einer Deklaration gehören nicht zu ihr (nur der nach ihr in derselben Zeile)
        rumpf_ohne = re.sub(r"^\s*/\*.*?\*/", "", rumpf, flags=re.S | re.M)
        kontexte = _kontexte(selektor)
        for k in kontexte:
            if k.startswith("stufe:") and letzter_kommentar:
                stufen[k.split(":", 1)[1]] = letzter_kommentar
        letzter_kommentar = ""
        for d in DEKLARATION.finditer(rumpf_ohne):
            name, wert, zweck = d.group(1), re.sub(r"\s+", " ", d.group(2)), _ohne_rahmen(d.group(3) or "")
            marke = nach_name.get(name)
            if marke is None:
                if gruppe is None:
                    raise ValueError(f"{name} steht vor der ersten Gruppe (/* == Name == ... */)")
                marke = nach_name[name] = Marke(name, gruppe.name)
                gruppe.marken.append(marke)
            if zweck and not marke.zweck:
                marke.zweck = zweck
            for k in kontexte:
                marke.werte[k] = wert
    stufen.setdefault("dicht", "Vorgabe der Schale: eine feste, dichte Schrift")
    return Marken(einleitung, gruppen, {s: stufen.get(s, "") for s in STUFEN})


def wert(marke: Marke, thema: str = "hell", stufe: str = "dicht") -> str:
    if stufe != "dicht" and f"stufe:{stufe}" in marke.werte:
        return marke.werte[f"stufe:{stufe}"]
    return marke.werte.get(thema) or marke.werte.get("alle", "")


# ----- Ausgaben -----

def daten(marken: Marken, katalog: dict) -> dict:
    """Was die Seite Gestaltung braucht (Werte zeigt sie live aus dem Browser, hier stehen Name, Zweck und Stand)."""
    return {
        "quelle": str(MARKEN),
        "einleitung": marken.einleitung,
        "stufen": [{"name": s, "text": t} for s, t in marken.stufen.items()],
        "gruppen": [{"name": g.name, "text": g.text,
                     "marken": [{"name": m.name, "art": m.art, "zweck": m.zweck, "werte": m.werte} for m in g.marken]}
                    for g in marken.gruppen],
        "muster": katalog.get("muster", []),
        "bausteine": katalog.get("bausteine", []),
        "nutzen": katalog.get("nutzen", []),
    }


def _zelle(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _code(text: str) -> str:
    return f"`{text}`" if text else "-"


def seite(marken: Marken, katalog: dict) -> str:
    teile = ["# Gestaltung", "",
             f"> Erzeugt aus `{MARKEN}` und `{KATALOG}` im Appkern (`python -m appkern.werkzeuge gestaltung`, bei "
             "jedem Commit des Appkerns). Dort ändern, nicht hier.", "",
             marken.einleitung, "",
             "In jeder App steht dieselbe Seite unter Einstellungen, Gestaltung: alle Bausteine echt gerendert, hell "
             "und dunkel nebeneinander.", "",
             "## So nutzt eine App die Gestaltung", ""]
    teile += [f"- {_zelle(z)}" for z in katalog.get("nutzen", [])]
    teile += ["", "## Muster mit Grund", "", "| Muster | Grund |", "|---|---|"]
    teile += [f"| {_zelle(m['regel'])} | {_zelle(m['grund'])} |" for m in katalog.get("muster", [])]
    teile += ["", "## Marken", ""]
    for g in marken.gruppen:
        teile += [f"### {g.name}", "", g.text, ""]
        if g.name == "Schriftgrößen" or any(f"stufe:{s}" in m.werte for m in g.marken for s in STUFEN):
            teile += ["| Marke | dicht | klein | mittel | gross | Zweck |", "|---|---|---|---|---|---|"]
            teile += [f"| `{m.name}` | " + " | ".join(_code(wert(m, stufe=s)) for s in STUFEN) + f" | {_zelle(m.zweck)} |"
                      for m in g.marken]
        elif any(t in m.werte for m in g.marken for t in THEMEN):
            teile += ["| Marke | hell | dunkel | Zweck |", "|---|---|---|---|"]
            teile += [f"| `{m.name}` | {_code(wert(m, 'hell'))} | {_code(wert(m, 'dunkel'))} | {_zelle(m.zweck)} |"
                      for m in g.marken]
        else:
            teile += ["| Marke | Wert | Zweck |", "|---|---|---|"]
            teile += [f"| `{m.name}` | {_code(wert(m))} | {_zelle(m.zweck)} |" for m in g.marken]
        teile.append("")
    teile += ["### Schriftstufen", "", "| Stufe | Wofür |", "|---|---|"]
    teile += [f"| {s} | {_zelle(t)} |" for s, t in marken.stufen.items()]
    teile += ["", "## Bausteine", "",
              "Zwei Sätze Bausteine auf denselben Marken: die Schale (Apps in `<Schale>`, dicht) und der Leitstand "
              "(Apps, die ihre Schale selbst zeichnen, mit Schriftstufen). Das Markup unten ergibt mit dem Stil des "
              "Appkerns genau den Baustein; Svelte-Teile sind als solche genannt.", ""]
    for familie, titel in (("schale", "Schale"), ("leitstand", "Leitstand")):
        eintraege = [b for b in katalog.get("bausteine", []) if b.get("familie") == familie]
        if not eintraege:
            continue
        teile += [f"### {titel}", ""]
        for b in eintraege:
            teile += [f"#### {b['name']}", "",
                      f"Klassen: {', '.join('`' + k + '`' for k in b.get('klassen', []))}" +
                      (f"; Svelte: `{b['svelte']}`" if b.get("svelte") else ""), "",
                      f"Wann: {b['wann']}", "", f"Warum: {b['warum']}", "", "```html", b["html"].strip(), "```", ""]
    teile += ["## Prüfung", "", katalog.get("pruefung", ""), ""]
    return "\n".join(teile).rstrip() + "\n"


def erzeugen(wurzel: Path) -> dict[Path, str]:
    """Inhalt der erzeugten Dateien aus dem Stand der Wahrheit."""
    marken = marken_lesen((wurzel / MARKEN).read_text(encoding="utf-8"))
    katalog = json.loads((wurzel / KATALOG).read_text(encoding="utf-8"))
    return {DATEN: json.dumps(daten(marken, katalog), ensure_ascii=False, indent=1) + "\n",
            SEITE: seite(marken, katalog)}


def veraltet(wurzel: Path) -> list[Path]:
    """Erzeugte Dateien, die nicht zum Stand der Wahrheit passen."""
    return [rel for rel, inhalt in erzeugen(wurzel).items()
            if not (wurzel / rel).is_file() or (wurzel / rel).read_text(encoding="utf-8") != inhalt]


def schreiben(wurzel: Path) -> list[Path]:
    geaendert = []
    for rel, inhalt in erzeugen(wurzel).items():
        ziel = wurzel / rel
        if not ziel.is_file() or ziel.read_text(encoding="utf-8") != inhalt:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(inhalt, encoding="utf-8")
            geaendert.append(rel)
    return geaendert


def ist_quelle(wurzel: Path) -> bool:
    """Nur der Appkern trägt die Wahrheit der Gestaltung."""
    return all((wurzel / q).is_file() for q in QUELLEN)
