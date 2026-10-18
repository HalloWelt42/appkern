"""__NAME__: __ROLLE__. Backend auf dem Gerüst des Appkerns.

    uvicorn app.main:app --port __PORT__
"""

import os
from pathlib import Path

import httpx
from fastapi import FastAPI

from appkern.app import Geruest
# ton:anfang
from appkern.ton import TonDienst
# ton:ende

from .api import router
from .arten import arten
from .einstellungen import AppEinstellungen
from .fassung import FASSUNG, WURZEL


def app_bauen(daten: Path, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """`transport` nur für Tests (Kellerwolke und Leitstelle nachgestellt)."""
    geruest = Geruest(name="__NAME__", kennung="__KENNUNG__", rolle="__ROLLE__", symbol="__SYMBOL__", fassung=FASSUNG,
                      daten=daten, einstellungen=AppEinstellungen, oberflaeche=WURZEL / "frontend" / "dist",
                      transport=transport)
    geruest.auftraege.anmelden(*arten(geruest))
    app = geruest.fastapi()
    app.state.geruest = geruest
    # ton:anfang
    # Tonarbeit nur über den Tondienst (der Pi rechnet nicht); die Arten der App bekommen sie von hier
    geruest.einstellungen.anbieten("dienst_ton", geruest.leitstelle_angebot("ton"))
    app.state.ton = TonDienst(lambda: geruest.leitstelle, lambda: geruest.einstellungen.stand.dienst_ton)
    # ton:ende
    app.include_router(router(geruest))
    geruest.oberflaeche_ausliefern(app)
    return app


def daten_ordner() -> Path:
    """Wo die App ihre Daten hält: `__UMGEBUNG___DATEN` (im Container /app/daten), sonst daten/ im Repo."""
    return Path(os.environ.get("__UMGEBUNG___DATEN") or WURZEL / "daten")


app = app_bauen(daten_ordner())
