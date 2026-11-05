"""Startet den Anmeldeposten: python -m appkern.posten (Einstellungen aus POSTEN_*, siehe dienst.Einstellungen)."""

from __future__ import annotations

import logging

import uvicorn

from .dienst import Einstellungen, erstellen


def starten(e: Einstellungen) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # nicht jede Rückfrage bei der Kellerwolke ins Protokoll
    uvicorn.run(erstellen(e), host=e.adresse, port=e.port, log_level="warning", access_log=False, proxy_headers=False)


if __name__ == "__main__":
    starten(Einstellungen())
