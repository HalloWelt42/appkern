"""Aufträge, wie sie nach außen gehen (Schnittstelle, Ereignisstrom)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Zustand = Literal["wartet", "laeuft", "fertig", "fehler", "abgebrochen", "unterbrochen"]
OFFEN: tuple[Zustand, ...] = ("wartet", "laeuft")
WIEDERHOLBAR: tuple[Zustand, ...] = ("fehler", "abgebrochen", "unterbrochen")


class Phase(BaseModel):
    """Ein Abschnitt eines Auftrags für die Schrittanzeige. `schluessel` ist ein technischer Bezeichner (ASCII),
    `titel` die Beschriftung, `symbol` ein Symbolname ohne Vorsilbe."""

    model_config = ConfigDict(frozen=True)

    schluessel: str
    titel: str
    symbol: str = ""


class Auftrag(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    art: str
    titel: str
    zustand: Zustand
    eingabe: dict[str, Any]
    ergebnis: dict[str, Any] | None = None
    fehler: str | None = None             # für Menschen; nie leer, wenn zustand "fehler" ist
    fortschritt: float | None = None      # 0 bis 1; None heißt: unbestimmt
    schritt: str = ""                     # was gerade geschieht, in Worten
    phase: str | None = None              # Schlüssel der laufenden Phase
    phasen: list[Phase] = Field(default_factory=list)
    abbruch_gewuenscht: bool = False
    fortsetzbar: bool = False             # Wiederholen setzt am Zwischenstand an
    stapel: str | None = None
    wiederholung_von: str | None = None
    erstellt_am: datetime
    begonnen_am: datetime | None = None
    beendet_am: datetime | None = None


class Seite(BaseModel):
    eintraege: list[Auftrag]
    gesamt: int


class Zahlen(BaseModel):
    """Wie viele Aufträge in jedem Zustand sind (für Kopf und Navigation, eine Abfrage statt einer je Zustand)."""

    wartet: int = 0
    laeuft: int = 0
    fertig: int = 0
    fehler: int = 0
    abgebrochen: int = 0
    unterbrochen: int = 0
