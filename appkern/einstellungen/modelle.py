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
    beschriftungen: dict[str, str] = {}   # Auswahl: lesbarer Name je Option (nie den Schlüssel zeigen)
    schritt: float | None = None          # Zahl: Schrittweite der Knöpfe (Vorgabe 1)
    kleinste: float | None = None
    groesste: float | None = None
    einheit: str = ""                     # Zahl: Einheit hinter dem Wert ("Minuten")
    angebot: bool = False                 # Auswahl kommt aus dem System (GET .../angebot/{name})
    wert: Any = None              # bei Geheimnissen verdeckt
    gesetzt: bool = True          # bei Geheimnissen: ist einer hinterlegt?
    vorgabe: Any = None
    herkunft: Literal["gespeichert", "umgebung", "vorgabe"]
    gruppe: str | None = None


class Option(BaseModel):
    """Ein Wert zur Auswahl, mit lesbarem Namen und kurzem Hinweis."""

    wert: str
    titel: str
    hinweis: str = ""


class Angebot(BaseModel):
    """Was für ein Feld zur Wahl steht, live aus dem System (etwa die Dienste der Leitstelle), und was gerade gilt.
    `eigener_wert`: ob außer den Optionen auch ein eigener Wert eingetragen werden darf."""

    optionen: list[Option] = []
    eigener_wert: bool = True
    stand: str = ""
