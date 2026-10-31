"""Beschreibung einer Einstellung für die Oberfläche."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FeldArt = Literal["text", "zahl", "schalter", "auswahl", "geheimnis", "liste", "wert"]


class Paar(BaseModel):
    """Liste von Paaren (eine `list[str]` mit `json_schema_extra={"paar": {...}}`): je Eintrag ein erster Wert und ein
    zweiter, gespeichert als `erster` (ohne zweiten, dann gilt `leer`) oder `erster<trenner>zweiter`. Die Oberfläche
    zeigt je Eintrag zwei Auswahlen; die Optionen kommen aus dem Angebot (`optionen` und `zweite`)."""

    erstes: str                   # Titel des ersten Teils, etwa "App"
    zweites: str                  # Titel des zweiten, etwa "Stimme"
    leer: str                     # Name des leeren zweiten Teils, etwa "alle Stimmen"
    trenner: str = ":"


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
    paar: Paar | None = None              # Liste: je Eintrag ein Paar aus zwei Auswahlen (siehe `Paar`)
    wert: Any = None              # bei Geheimnissen verdeckt
    gesetzt: bool = True          # bei Geheimnissen: ist einer hinterlegt?
    vorgabe: Any = None
    herkunft: Literal["gespeichert", "umgebung", "vorgabe"]
    gruppe: str | None = None


class Option(BaseModel):
    """Ein Wert zur Auswahl, mit lesbarem Namen und kurzem Hinweis. `aufgabe` steht klein hinter dem Titel (bei Diensten
    der Leitstelle: Modellname als Titel, etwa "Whisper Large V3 · Spracherkennung")."""

    wert: str
    titel: str
    hinweis: str = ""
    aufgabe: str = Field(default="", exclude_if=lambda w: not w)    # nur gesendet, wenn es eine gibt


class Angebot(BaseModel):
    """Was für ein Feld zur Wahl steht, live aus dem System (etwa die Dienste der Leitstelle), und was gerade gilt.
    `eigener_wert`: ob außer den Optionen auch ein eigener Wert eingetragen werden darf. `zweite`: bei einer Liste von
    Paaren die Auswahl für den zweiten Teil (`optionen` ist dann die für den ersten)."""

    optionen: list[Option] = []
    zweite: list[Option] = []
    eigener_wert: bool = True
    stand: str = ""
