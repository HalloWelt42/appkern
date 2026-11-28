"""Der Erkennen-Dienst: Protokoll der Bilderkennung über HTTP, beide Seiten an einem Ort.

- `ErkennenDienst` (hier): für die Apps, über die Leitstelle (`/v1/dienste/<name>/erkennen`, Fähigkeit `bild_erkennen`).
- `routen(hier)` (`gegenseite.py`): die Gegenseite, läuft im Dienst auf dem Mac (Wirt: Bildwerk, Dienst `bild-erkennen`).

Ein Aufruf ist ein POST mit dem Bild und dem Auftrag als JSON; die Antwort ist `Erkannt`. Ein unlesbares Bild kommt als
422 mit dem Grundwort `bild_fehler` und wird beim Aufrufer wieder zum `BildFehler`.
"""

from __future__ import annotations

from collections.abc import Callable

from ..leitstelle import Leitstelle, LeitstellenFehler
from ..leitstelle.modelle import Prioritaet
from .modelle import Erkannt, Erkennen
from .rechnen import BildFehler

BILD_FEHLER = "bild_fehler"
NAME = "bild-erkennen"


class ErkennenDienst:
    """Bilderkennung über die Leitstelle; `leitstelle` und `name` werden bei jedem Aufruf gefragt (Einstellungen)."""

    def __init__(self, leitstelle: Callable[[], Leitstelle | None], name: Callable[[], str] = lambda: NAME) -> None:
        self._leitstelle, self._name = leitstelle, name

    async def erkennen(self, inhalt: bytes, auftrag: Erkennen | None = None, *, dateiname: str = "bild.jpg", typ: str = "image/jpeg",
                       titel: str = "", prioritaet: Prioritaet | None = None) -> Erkannt:
        ls = self._leitstelle()
        if ls is None:
            raise BildFehler("Keine Leitstelle eingerichtet: ohne sie gibt es keine Bilderkennung")
        try:
            antwort = await ls.dienst(self._name()).json("POST", "/erkennen", titel=titel, prioritaet=prioritaet,
                                                         data={"auftrag": (auftrag or Erkennen()).model_dump_json()},
                                                         files=[("bild", (dateiname, inhalt, typ))])
        except LeitstellenFehler as f:
            if f.grund == BILD_FEHLER:
                raise BildFehler(f.meldung) from None
            raise
        return Erkannt.model_validate(antwort)
