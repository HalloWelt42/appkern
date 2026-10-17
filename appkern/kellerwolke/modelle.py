"""Was die Ablage-Schnittstelle der Kellerwolke (/api/v1/ablage) liefert, als Pydantic-Modelle.

Unbekannte Felder werden überlesen: eine neuere Kellerwolke mit zusätzlichen Angaben bricht ältere Apps nicht.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

Recht = Literal["lesen", "schreiben"]


class _Modell(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Rechtseintrag(_Modell):
    knoten_id: UUID
    pfad: str
    recht: Recht


class Ich(_Modell):
    """Wer mit diesem Schlüssel spricht: App, Konto und die freigegebenen Ordner."""

    app: str
    konto: str
    konto_id: UUID | None = None  # ältere Kellerwolken nennen nur den Namen
    rechte: list[Rechtseintrag]

    @property
    def zweig(self) -> str:
        """Der eigene Ordner der App (Vorgabe der Kellerwolke beim Ausstellen des Schlüssels)."""
        return f"Apps/{self.app}"


class Sperre(_Modell):
    app: str
    grund: str
    seit: datetime
    bis: datetime


class Knoten(_Modell):
    id: UUID
    parent_id: UUID | None = None
    name: str
    typ: str  # datei, ordner
    pfad: str
    recht: Recht
    etag: str | None = None  # Stand der Datei: beim Überschreiben als `stand` mitgeben
    groesse: int | None = None
    inhaltstyp: str | None = None
    app: str | None = None  # App, die zuletzt geschrieben hat
    felder: dict[str, Any] = Field(default_factory=dict)
    sperre: Sperre | None = None
    erstellt_am: datetime
    geaendert_am: datetime

    @property
    def ist_ordner(self) -> bool:
        return self.typ == "ordner"


class Version(_Modell):
    """Eine Fassung einer Datei; ändert sich nie. Zurückholen: Inhalt lesen und als neue Version schreiben."""

    id: UUID
    groesse: int
    erstellt_am: datetime
    aktuell: bool = False


class Herkunft(_Modell):
    von_id: UUID
    zu_id: UUID
    art: str
    app: str | None = None
    erstellt_am: datetime


AenderungsTyp = Literal["erstellt", "geaendert", "verschoben", "geloescht", "entfernt"]


class Aenderung(_Modell):
    seq: int
    knoten_id: UUID
    typ: str  # AenderungsTyp; als Text, damit neue Arten ältere Apps nicht brechen
    version_id: UUID | None = None
    von_parent_id: UUID | None = None  # beim Verschieben: der alte Elternordner
    zeit: datetime


class Aenderungen(_Modell):
    eintraege: list[Aenderung]
    bis: int  # beim nächsten Mal als `seit` angeben
    luecke: bool  # das Journal reicht nicht mehr so weit zurück: den Ordner neu lesen
