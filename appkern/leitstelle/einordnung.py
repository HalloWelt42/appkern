"""Wie die App einen Auftrag einordnet (Leitstelle, docs/ARBEITSLOGIK.md, LS-23 und LS-24): Masse oder Einzel, und ob der
Nutzer ihn als wichtig markiert hat. Wie die laufende Arbeit (arbeit.py) liegt die Einordnung im Kontext: jede Anfrage
innerhalb von `als_masse()` oder `als_wichtig()` trägt den Kopf, die Aufrufstellen ändern sich nicht.

    with als_masse():                 # Stapel der Masseneinbettung, Vorlesen eines ganzen Buchs
        await leitstelle.einbetten(stapel, modell=...)

    with als_wichtig():               # nur auf ausdrückliche Angabe des Nutzers (Knopf "Wichtig", je App mit Bestätigung)
        await leitstelle.chat(...)

    with halten(300):                 # gleich folgen weitere: das Modell bleibt so lange nach dem letzten Auftrag geladen
        await leitstelle.chat(...)

Ohne Angabe gilt Einzel. Wichtig geht allem vor; eine App setzt es nie von sich aus. Halten (HELF-265) wirkt nur gegen das
Entladen nach Leerlauf, gedeckelt durch die Leitstelle; `halten(0)` gibt einen früheren Antrag der App wieder frei. Es ersetzt
das Bündeln nicht: was zusammengehört, schickt die App am Stück."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

ART_KOPF = "X-Leitstelle-Art"
WICHTIG_KOPF = "X-Leitstelle-Wichtig"
HALTEN_KOPF = "X-Leitstelle-Halten"

MASSE: ContextVar[bool] = ContextVar("leitstelle_masse", default=False)
WICHTIG: ContextVar[bool] = ContextVar("leitstelle_wichtig", default=False)
HALTEN: ContextVar[int | None] = ContextVar("leitstelle_halten", default=None)


@contextmanager
def als_masse() -> Iterator[None]:
    """Alles darin ist Teil einer Massenaufgabe: kommt nach Einzelarbeit und rechnet nur auf einem ruhigen Mac."""
    marke = MASSE.set(True)
    try:
        yield
    finally:
        MASSE.reset(marke)


@contextmanager
def als_wichtig() -> Iterator[None]:
    """Alles darin hat der Nutzer ausdrücklich als wichtig markiert: geht allem vor, auch der Sprachausgabe."""
    marke = WICHTIG.set(True)
    try:
        yield
    finally:
        WICHTIG.reset(marke)


@contextmanager
def halten(sekunden: float) -> Iterator[None]:
    """Alles darin bittet, das genutzte Modell (oder den Dienst) danach so lange geladen zu lassen; 0 gibt es frei."""
    marke = HALTEN.set(max(0, round(sekunden)))
    try:
        yield
    finally:
        HALTEN.reset(marke)


def koepfe() -> dict[str, str]:
    """Die Köpfe der Einordnung im aktuellen Kontext; wichtig schließt Masse aus (ein markierter Auftrag ist nie Masse)."""
    kopf = {} if (s := HALTEN.get()) is None else {HALTEN_KOPF: str(s)}
    if WICHTIG.get():
        return {**kopf, WICHTIG_KOPF: "ja"}
    return {**kopf, ART_KOPF: "masse"} if MASSE.get() else kopf
