"""Harte Architekturregeln einer App, von Git erzwungen (ATL-15).

Jede App beschreibt ihre Regeln in `architektur/regeln.toml`; dieser Prüfer ist für alle Apps derselbe. Er läuft vor jedem
Commit (über `vor-dem-commit`) und beim Ausrollen über das ganze Repo, damit auch ein Commit, der an den Haken vorbei
gelangt ist, nicht in Betrieb geht.

Arten von Regeln:
    verboten   Muster (regulärer Ausdruck) darf in den genannten Dateien nicht vorkommen
    schichten  Einbindungen (import) dürfen nur in die erlaubte Richtung zeigen
    pflicht    Dateien, die es geben muss
    zeilen     höchstens so viele Zeilen je Datei

Ausnahmen stehen in `architektur/ausnahmen.toml` (Regel, Dateien, Grund, Ticket). Eine Ausnahme gilt nur, wenn der Nutzer
sie am Ticket der Pinnwand mit einem eigenen Kommentar freigegeben hat: "Ausnahme freigegeben: <Regel>". Kommentare von
Apps (der Helfer schreibt als App) zählen nicht. Ist die Pinnwand nicht erreichbar, gilt keine Ausnahme (sicher scheitern).
"""

from __future__ import annotations

import json
import re
import ssl
import tomllib
import urllib.request
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, Field

from .befund import Befund

REGELN = Path("architektur/regeln.toml")
AUSNAHMEN = Path("architektur/ausnahmen.toml")


# ----- Daten ---------------------------------------------------------------------------------------------------------

class Schicht(BaseModel):
    name: str
    dateien: list[str]


class Regel(BaseModel):
    kennung: str
    titel: str
    art: str                                   # verboten | schichten | pflicht | zeilen
    warum: str = ""
    dateien: list[str] = Field(default_factory=list)
    ausser: list[str] = Field(default_factory=list)
    muster: str = ""
    schichten: list[Schicht] = Field(default_factory=list)
    erlaubt: dict[str, list[str]] = Field(default_factory=dict)
    hoechstens: int = 0


class Freigabe(BaseModel):
    pinnwand: str
    schluessel: str
    stichwort: str = "Ausnahme freigegeben"


class Regelwerk(BaseModel):
    freigabe: Freigabe
    regel: list[Regel]


class Ausnahme(BaseModel):
    regel: str
    dateien: list[str]
    grund: str
    ticket: str


# ----- Laden -----------------------------------------------------------------------------------------------------------

def regelwerk(wurzel: Path) -> Regelwerk | None:
    datei = wurzel / REGELN
    if not datei.is_file():
        return None
    return Regelwerk.model_validate(tomllib.loads(datei.read_text(encoding="utf-8")))


def ausnahmen(wurzel: Path) -> list[Ausnahme]:
    datei = wurzel / AUSNAHMEN
    if not datei.is_file():
        return []
    return [Ausnahme.model_validate(a) for a in tomllib.loads(datei.read_text(encoding="utf-8")).get("ausnahme", [])]


def _passt(rel: str, muster: list[str]) -> bool:
    return any(fnmatch(rel, m) for m in muster)


# ----- Arten von Regeln -------------------------------------------------------------------------------------------------

def _verboten(r: Regel, rel: str, text: str) -> list[Befund]:
    ausdruck = re.compile(r.muster)
    return [Befund(datei=rel, zeile=nr, regel=r.kennung, text=f"{r.titel}: {zeile.strip()}")
            for nr, zeile in enumerate(text.splitlines(), 1) if ausdruck.search(zeile)]


EINBINDUNG_TS = re.compile(r"""(?:^|\s)(?:import|export)\b[^'"]*?from\s*['"]([^'"]+)['"]|import\(\s*['"]([^'"]+)['"]\s*\)""")
EINBINDUNG_PY = re.compile(r"^\s*(?:from\s+(\.*[\w.]*)\s+import|import\s+([\w.]+))")


def _ziel(rel: str, ziel: str, py: bool) -> str | None:
    """Pfad der eingebundenen Datei im Repo (ohne Endung), soweit er sich bestimmen lässt."""
    if py:
        if ziel.startswith("."):
            punkte = len(ziel) - len(ziel.lstrip("."))
            basis = PurePosixPath(rel).parents[punkte - 1]
            return str(basis / ziel.lstrip(".").replace(".", "/")) if ziel.strip(".") else str(basis)
        return ziel.replace(".", "/")
    if ziel.startswith("."):
        return str(PurePosixPath(rel).parent / ziel).replace("/./", "/")
    return ziel


def _schicht(pfad: str, schichten: list[Schicht]) -> str | None:
    norm = str(PurePosixPath(pfad))
    teile: list[str] = []
    for t in norm.split("/"):
        if t == "..":
            teile and teile.pop()
        elif t not in (".", ""):
            teile.append(t)
    norm = "/".join(teile)
    for s in schichten:
        if any(fnmatch(norm, m) or fnmatch(norm + ".ts", m) or fnmatch(norm + ".py", m) or fnmatch(norm + "/x", m) for m in s.dateien):
            return s.name
    return None


def _schichten(r: Regel, rel: str, text: str) -> list[Befund]:
    eigene = _schicht(rel, r.schichten)
    if eigene is None:
        return []
    py = rel.endswith(".py")
    befunde = []
    for nr, zeile in enumerate(text.splitlines(), 1):
        treffer = (EINBINDUNG_PY if py else EINBINDUNG_TS).search(zeile)
        if not treffer:
            continue
        ziel = _ziel(rel, next(g for g in treffer.groups() if g), py)
        fremde = _schicht(ziel, r.schichten) if ziel else None
        if fremde and fremde != eigene and fremde not in r.erlaubt.get(eigene, []):
            befunde.append(Befund(datei=rel, zeile=nr, regel=r.kennung,
                                  text=f"{r.titel}: Schicht {eigene} darf {fremde} nicht einbinden ({zeile.strip()})"))
    return befunde


def _zeilen(r: Regel, rel: str, text: str) -> list[Befund]:
    n = text.count("\n") + 1
    return [Befund(datei=rel, zeile=n, regel=r.kennung, text=f"{r.titel}: {n} Zeilen, höchstens {r.hoechstens}")] if n > r.hoechstens else []


PRUEFUNGEN = {"verboten": _verboten, "schichten": _schichten, "zeilen": _zeilen}


# ----- Freigaben über die Pinnwand ----------------------------------------------------------------------------------------

def _freigegeben(werk: Regelwerk, ausnahme: Ausnahme) -> tuple[bool, str]:
    """Hat der Nutzer (nicht eine App) die Ausnahme am Ticket freigegeben? Ohne Verbindung: nein."""
    try:
        schluessel = Path(werk.freigabe.schluessel).expanduser().read_text().strip()
        anfrage = urllib.request.Request(werk.freigabe.pinnwand.rstrip("/") + "/stand", headers={"Authorization": "Bearer " + schluessel})
        stand = json.load(urllib.request.urlopen(anfrage, context=ssl._create_unverified_context(), timeout=15))
    except (OSError, ValueError) as f:
        return False, f"Pinnwand nicht erreichbar ({f}); ohne Prüfung gilt keine Ausnahme"
    karte = next((k for k in stand.get("karten", []) if k.get("schluessel") == ausnahme.ticket), None)
    if karte is None:
        return False, f"Ticket {ausnahme.ticket} nicht gefunden"
    stichwort = re.compile(re.escape(werk.freigabe.stichwort) + r"\s*:\s*" + re.escape(ausnahme.regel) + r"\b", re.IGNORECASE)
    for k in karte.get("kommentare", []):
        if ".app-" not in str(k.get("von", "")) and stichwort.search(k.get("text", "")):
            return True, ""
    return False, f"am Ticket {ausnahme.ticket} fehlt ein Kommentar des Nutzers \"{werk.freigabe.stichwort}: {ausnahme.regel}\""


# ----- Prüfen ----------------------------------------------------------------------------------------------------------

def regeln_pruefen(dateien: list[Path], wurzel: Path) -> list[Befund]:
    werk = regelwerk(wurzel)
    if werk is None:
        return []
    befunde: list[Befund] = []
    bekannt = {r.kennung for r in werk.regel}
    for r in werk.regel:
        if r.art == "pflicht":
            befunde += [Befund(datei=m, zeile=1, regel=r.kennung, text=f"{r.titel}: Datei fehlt")
                        for m in r.dateien if not (wurzel / m).exists()]
            continue
        pruefe = PRUEFUNGEN.get(r.art)
        if pruefe is None:
            befunde.append(Befund(datei=str(REGELN), zeile=1, regel=r.kennung, text=f"unbekannte Art {r.art}"))
            continue
        for d in dateien:
            if not d.is_file():
                continue
            rel = d.relative_to(wurzel).as_posix()
            if not _passt(rel, r.dateien) or _passt(rel, r.ausser):
                continue
            befunde += pruefe(r, rel, d.read_text(encoding="utf-8", errors="replace"))

    # Ausnahmen: nur freigegebene heben Befunde auf; jede unbekannte oder nicht freigegebene ist selbst ein Befund
    gueltig: list[Ausnahme] = []
    for a in ausnahmen(wurzel):
        if a.regel not in bekannt:
            befunde.append(Befund(datei=str(AUSNAHMEN), zeile=1, regel="Ausnahme", text=f"Regel {a.regel} gibt es nicht"))
            continue
        if not any(b.regel == a.regel and _passt(b.datei, a.dateien) for b in befunde):
            continue  # greift nirgends: muss nicht gefragt werden
        ok, warum = _freigegeben(werk, a)
        if ok:
            gueltig.append(a)
        else:
            befunde.append(Befund(datei=str(AUSNAHMEN), zeile=1, regel="Ausnahme ohne Freigabe", text=f"{a.regel} für {', '.join(a.dateien)}: {warum}"))
    return [b for b in befunde if not any(b.regel == a.regel and _passt(b.datei, a.dateien) for a in gueltig)]
