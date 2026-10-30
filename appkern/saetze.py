"""Text in Sätze teilen, zum Sprechen Satz für Satz (Vorlesen, Vertonung). Abkürzungen ("z. B.", "Nr.") und
Ordnungszahlen ("12. September", "im 3. Stock") beenden keinen Satz; Absätze (Leerzeile) beenden immer einen. Jeder
Satz kennt seine Lage im Eingabetext (zum Mitlesen). Ein Satz, der für einen Aufruf eines Sprechdienstes zu lang ist,
zerfällt mit `stuecke` an Teilsatz-, dann an Wortgrenzen, zuletzt hart; nichts geht verloren.

Typografische Zeichen stehen hier über ihre Nummer (der Haken des Repos lässt sie im Code nicht zu)."""

from __future__ import annotations

import re
from dataclasses import dataclass

#: so lang darf ein Stück für einen Aufruf des Sprechdienstes höchstens sein (längere Sätze zerfallen in Stücke)
GRENZE = 180
ELLIPSE = chr(0x2026)
SCHLUSSZEICHEN = '"' + "'" + ")" + chr(0x00BB) + chr(0x00AB) + chr(0x201C) + chr(0x201D) + chr(0x201E) + chr(0x2019)
ABKUERZUNGEN = {
    "z", "b", "d", "h", "u", "a", "o", "s", "v", "usw", "bzw", "ca", "dr", "prof", "nr", "str", "vgl", "evtl", "ggf",
    "inkl", "etc", "hr", "fr", "jh", "mio", "mrd", "tel", "abs", "art", "bd", "min", "max", "bspw", "zzgl", "geb",
    "gest", "st", "sog", "allg", "bzgl", "insb", "ff", "mr", "mrs", "ms", "vs", "e", "i", "w",
}
MONATE = {"januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november",
          "dezember", "jan", "feb", "mär", "apr", "jun", "jul", "aug", "sep", "sept", "okt", "nov", "dez"}
#: vor einer Zahl mit Punkt: dann ist sie eine Ordnungszahl ("im 3. Stock")
ARTIKEL = {"der", "die", "das", "den", "dem", "des", "am", "im", "vom", "zum", "zur", "beim"}
_ENDE = re.compile("([.!?" + ELLIPSE + "]+)([" + re.escape(SCHLUSSZEICHEN) + "]*)(\\s+)")
_TEILSATZ = re.compile(r"(?<=[,;:])\s+|(?<=\s-)\s+")   # nach Komma, Semikolon, Doppelpunkt, Gedankenstrich
_WORT_AM_ENDE = re.compile(r"([\wÄÖÜäöüß]+)$")
_WORT_AM_ANFANG = re.compile(r"[\wÄÖÜäöüß]+")
_ARTIKEL_ZAHL = re.compile(r"(\w+)\s+\d+$")


@dataclass(frozen=True)
class Satz:
    text: str              # Leerraum zu je einem Leerzeichen zusammengefasst
    absatz_ende: bool      # nach ihm endet ein Absatz
    von: int = 0           # Lage im Eingabetext: eingabe[von:bis] ist der Satz mit seinem ursprünglichen Leerraum
    bis: int = 0


def _endet_satz(vorher: str, zeichen: str, danach: str) -> bool:
    if zeichen != ".":
        return True
    wort = _WORT_AM_ENDE.search(vorher)
    if wort is None:
        return True
    w = wort.group(1)
    if w.lower() in ABKUERZUNGEN:
        return False
    naechstes = _WORT_AM_ANFANG.match(danach)
    if w.isdigit() and naechstes and (naechstes.group(0).lower() in MONATE or naechstes.group(0)[0].islower()):
        return False                          # Ordnungszahl: "12. September", "3. bis 5."
    davor = _ARTIKEL_ZAHL.search(vorher)
    if w.isdigit() and naechstes and davor and davor.group(1).lower() in ARTIKEL:
        return False                          # Ordnungszahl nach Artikel: "im 3. Stock"
    if naechstes and naechstes.group(0)[0].islower():
        return False                          # klein weiter: eher Abkürzung als Satzende
    return True


def _verdichtet(text: str, versatz: int) -> tuple[str, list[int]]:
    """Leerraum zu je einem Leerzeichen, vorn und hinten weg; dazu für jedes Zeichen seine Lage im Eingabetext."""
    aus: list[str] = []
    lage: list[int] = []
    for i, z in enumerate(text):
        if z.isspace():
            if aus and aus[-1] != " ":
                aus.append(" ")
                lage.append(versatz + i)
            continue
        aus.append(z)
        lage.append(versatz + i)
    if aus and aus[-1] == " ":
        aus.pop()
        lage.pop()
    return "".join(aus), lage


def _absaetze(text: str):
    """(Absatz, Lage seines Anfangs) für jeden Absatz; Absätze trennt eine Leerzeile."""
    anfang = 0
    for trenner in re.finditer(r"\n\s*\n", text):
        yield text[anfang:trenner.start()], anfang
        anfang = trenner.end()
    yield text[anfang:], anfang


def _ohne_rand(text: str, a: int, b: int) -> tuple[int, int]:
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return a, b


def saetze(text: str) -> list[Satz]:
    """Die Sätze des Texts in ihrer Folge; leere fallen weg."""
    aus: list[Satz] = []
    for roh, versatz in _absaetze(text):
        absatz, lage = _verdichtet(roh, versatz)
        if not absatz:
            continue
        spannen: list[tuple[int, int]] = []
        anfang = 0
        for m in _ENDE.finditer(absatz):
            if _endet_satz(absatz[anfang:m.start()], m.group(1)[-1], absatz[m.end():]):
                spannen.append((anfang, m.end(2)))
                anfang = m.end()
        spannen.append((anfang, len(absatz)))
        teile = [(a, b) for a, b in (_ohne_rand(absatz, a, b) for a, b in spannen) if b > a]
        for i, (a, b) in enumerate(teile):
            aus.append(Satz(text=absatz[a:b], absatz_ende=i == len(teile) - 1, von=lage[a], bis=lage[b - 1] + 1))
    return aus


def _woerter(text: str, grenze: int) -> list[str]:
    stuecke: list[str] = []
    jetzt = ""
    for wort in text.split():
        while len(wort) > grenze:                 # ein Wort länger als die Grenze: hart teilen
            if jetzt:
                stuecke.append(jetzt)
                jetzt = ""
            stuecke.append(wort[:grenze])
            wort = wort[grenze:]
        if jetzt and len(jetzt) + 1 + len(wort) > grenze:
            stuecke.append(jetzt)
            jetzt = wort
        else:
            jetzt = f"{jetzt} {wort}".strip()
    if jetzt:
        stuecke.append(jetzt)
    return stuecke


def stuecke(satz: str, grenze: int = GRENZE) -> list[str]:
    """Ein Satz in Stücke von höchstens `grenze` Zeichen: Teilsätze zusammenfassen, solange sie passen; zu lange
    Teilsätze an Wortgrenzen."""
    satz = re.sub(r"\s+", " ", satz).strip()
    if len(satz) <= grenze:
        return [satz] if satz else []
    aus: list[str] = []
    jetzt = ""
    for teil in (t.strip() for t in _TEILSATZ.split(satz) if t.strip()):
        kandidat = f"{jetzt} {teil}".strip()
        if len(kandidat) <= grenze:
            jetzt = kandidat
            continue
        if jetzt:
            aus.append(jetzt)
        if len(teil) <= grenze:
            jetzt = teil
        else:
            *voll, jetzt = _woerter(teil, grenze)
            aus.extend(voll)
    if jetzt:
        aus.append(jetzt)
    return aus


def hat_worte(text: str) -> bool:
    """Gibt es etwas zu sprechen (mindestens ein Buchstabe oder eine Ziffer)?"""
    return any(z.isalnum() for z in text)
