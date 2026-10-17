"""Protokoll einer App: Ereignisse mit Stufe, Bezug und Text, seitenweise und durchsuchbar.
Die Schnittstelle für FastAPI liegt in `appkern.protokoll.api` (Zusatz `appkern[web]`)."""

from .dienst import Protokoll
from .modelle import Eintrag, Seite, Stufe

__all__ = ["Eintrag", "Protokoll", "Seite", "Stufe"]
