"""Einstellungen einer App als Pydantic-Modell, gespeichert in ihrer Datenbank, Geheimnisse verdeckt.
Die Schnittstelle für FastAPI liegt in `appkern.einstellungen.api` (Zusatz `appkern[web]`)."""

from .dienst import Einstellungen, UnbekanntesFeld, verdeckt
from .modelle import Feld, FeldArt

__all__ = ["Einstellungen", "Feld", "FeldArt", "UnbekanntesFeld", "verdeckt"]
