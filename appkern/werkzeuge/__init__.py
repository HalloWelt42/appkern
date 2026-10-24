"""Werkzeuge der eigenen Apps am Rechner der Entwicklung: Prüfungen vor dem Commit (Zeichen, Stil, Marken der
Gestaltung), Fassung hochzählen.

Jede App ruft sie aus ihrem Backend auf (`backend/.venv/bin/python -m appkern.werkzeuge ...`); so gilt überall dieselbe
Prüfung, und eine Verbesserung erreicht jede App mit dem nächsten Stand des Appkerns.
"""

from .befund import Befund
from .fassung import hochzaehlen
from .marken import marken_pruefen, strenge
from .stil import stil_pruefen, schalen_klassen
from .zeichen import zeichen_pruefen

__all__ = ["Befund", "hochzaehlen", "marken_pruefen", "schalen_klassen", "stil_pruefen", "strenge", "zeichen_pruefen"]
