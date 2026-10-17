"""Anfragen aus der Kellerwolke: Aktionen melden, Anfragen abholen und als Aufträge ausführen, Dateiwahl und Öffnen.
Die Schnittstelle für FastAPI liegt in `appkern.anfragen.api` (Zusatz `appkern[web]`)."""

from .dienst import Abholer, Angebot, AnfrageEingabe

__all__ = ["Abholer", "Angebot", "AnfrageEingabe"]
