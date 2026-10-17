"""__NAME__: __ROLLE__. Backend auf dem Gerüst des Appkerns.

    uvicorn app.main:app --port __PORT__
"""

from pathlib import Path

import httpx
from fastapi import FastAPI

from appkern.app import Geruest

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
    app.include_router(router(geruest))
    geruest.oberflaeche_ausliefern(app)
    return app


app = app_bauen(WURZEL / "daten")
