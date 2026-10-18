"""Bindung an eine Instanz: zusammengehörige Aufrufe eines Dienstes (rechnen, dann das Ergebnis abholen) müssen an
dieselbe Instanz gehen, sobald ein Dienst mehrfach läuft (weitere Instanz auf demselben Rechner, zweiter Rechner). Die
Leitstelle nennt in jeder Antwort einer Durchleitung die Instanz (Kopf `X-Leitstelle-Instanz`); innerhalb einer Bindung
merkt sich der erste Aufruf sie und die folgenden schicken sie mit (PROTOKOLL 6 der Leitstelle)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

KOPF = "X-Leitstelle-Instanz"


@dataclass
class Bindung:
    dienst: str
    instanz: str | None = None        # aus der ersten Antwort


# je Dienstname die laufende Bindung; verschachtelte Bindungen verschiedener Dienste bestehen nebeneinander
GEBUNDEN: ContextVar[dict[str, Bindung]] = ContextVar("leitstelle_bindungen", default={})
