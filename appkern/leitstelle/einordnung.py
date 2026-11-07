"""Wie die App einen Auftrag einordnet (Leitstelle, docs/ARBEITSLOGIK.md, LS-23 und LS-24): Masse oder Einzel, und ob der
Nutzer ihn als wichtig markiert hat. Wie die laufende Arbeit (arbeit.py) liegt die Einordnung im Kontext: jede Anfrage
innerhalb von `als_masse()` oder `als_wichtig()` trägt den Kopf, die Aufrufstellen ändern sich nicht.

    with als_masse():                 # Stapel der Masseneinbettung, Vorlesen eines ganzen Buchs
        await leitstelle.einbetten(stapel, modell=...)

    with als_wichtig():               # nur auf ausdrückliche Angabe des Nutzers (Knopf "Wichtig", je App mit Bestätigung)
        await leitstelle.chat(...)

Ohne Angabe gilt Einzel. Wichtig geht allem vor; eine App setzt es nie von sich aus."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

ART_KOPF = "X-Leitstelle-Art"
WICHTIG_KOPF = "X-Leitstelle-Wichtig"

MASSE: ContextVar[bool] = ContextVar("leitstelle_masse", default=False)
WICHTIG: ContextVar[bool] = ContextVar("leitstelle_wichtig", default=False)


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


def koepfe() -> dict[str, str]:
    """Die Köpfe der Einordnung im aktuellen Kontext; wichtig schließt Masse aus (ein markierter Auftrag ist nie Masse)."""
    if WICHTIG.get():
        return {WICHTIG_KOPF: "ja"}
    return {ART_KOPF: "masse"} if MASSE.get() else {}
