"""Beschreibung einer Einstellung für die Oberfläche."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

FeldArt = Literal["text", "zahl", "schalter", "auswahl", "geheimnis", "liste", "wert"]


class Feld(BaseModel):
    name: str
    titel: str
    beschreibung: str = ""
    art: FeldArt
    optionen: list[str] = []
    wert: Any = None              # bei Geheimnissen verdeckt
    gesetzt: bool = True          # bei Geheimnissen: ist einer hinterlegt?
    vorgabe: Any = None
    herkunft: Literal["gespeichert", "umgebung", "vorgabe"]
    gruppe: str | None = None
