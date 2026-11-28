"""Bilderkennung für alle Apps (LS-35): Texte mit ihren Rahmen und Gesichter in einem Bild finden. Gerechnet wird nur an
einem Ort, am Mac mit Apple Vision (`ErkennenHier`, Wirt: Bildwerk, Dienst `bild-erkennen`); die Apps fragen über die
Leitstelle mit `ErkennenDienst` (Fähigkeit `bild_erkennen`). Rahmen stehen in Anteilen des Bildes, von oben links."""

from .dienst import BILD_FEHLER, ErkennenDienst
from .modelle import Erkannt, Erkennen, Gesicht, Rahmen, Textstelle
from .rechnen import BildFehler, aus_vision

__all__ = ["BILD_FEHLER", "BildFehler", "Erkannt", "Erkennen", "ErkennenDienst", "Gesicht", "Rahmen", "Textstelle", "aus_vision"]
