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


class AppZugang(_Modell):
    """Ein App-Zugang des Kontos (ohne Schlüssel): unter diesem Namen meldet sich die App bei anderen Apps an."""

    id: UUID
    app: str
    aktiv: bool = True


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
    haupt_id: UUID | None = None  # ein Begleiter: seine Hauptdatei
    rolle: str | None = None      # ein Begleiter: seine Rolle (transkript, untertitel, sprache ...)
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


# --- Aktionen und Anfragen (Kellerwolke ab 0.79) ---------------------------------------------------------------------

AnfrageZustand = Literal["wartet", "laeuft", "fertig", "fehler", "abgebrochen"]
AktionsArt = Literal["hintergrund", "oeffnen"]


class Aktion(BaseModel):
    """Was eine App mit Dateien bestimmter Inhaltstypen kann; die App meldet die Liste beim Start. `hintergrund`:
    die App holt die Anfrage ab und arbeitet; `oeffnen`: der Browser kommt mit der Anfrage in die App."""

    model_config = ConfigDict(frozen=True)

    kennung: str
    titel: str
    symbol: str
    typen: tuple[str, ...]
    art: AktionsArt = "hintergrund"
    titel_erneut: str | None = None   # wenn der Begleiter der Rolle schon da ist (etwa "Neu transkribieren")
    rolle: str | None = None          # Begleiter, um den es geht


class Anfrage(_Modell):
    """App X soll Aktion A auf Datei D ausführen. Solange sie offen ist, darf die App genau diese Datei lesen und ihre
    Begleiter schreiben (`Kellerwolke.mit_anfrage`)."""

    id: UUID
    app: str
    aktion: str
    titel: str
    art: AktionsArt
    knoten_id: UUID
    knoten_name: str
    von: str                        # konto oder die App, die weitergab
    optionen: dict[str, str | int | float | bool] = {}   # kleine Angaben der weitergebenden App (Kellerwolke ab 0.85)
    zustand: AnfrageZustand
    fortschritt: float | None = None
    meldung: str | None = None
    ergebnis_id: UUID | None = None
    ergebnis_name: str | None = None
    erstellt_am: datetime
    gueltig_bis: datetime


class AnfrageNeu(_Modell):
    anfrage: Anfrage
    ziel: str | None = None         # bei Aktionen zum Öffnen: Adresse in der App


class WahlEintrag(_Modell):
    id: UUID
    name: str
    typ: str
    groesse: int | None = None
    inhaltstyp: str | None = None
    geaendert_am: datetime
    kinder_anzahl: int | None = None
    haupt_id: UUID | None = None
    rolle: str | None = None
    begleiter_anzahl: int = 0


class WahlOrt(_Modell):
    id: UUID | None
    name: str


class WahlSeite(_Modell):
    """Eine Seite der Dateiwahl: Ordnerkette vom Konto bis hier und die Einträge (nur Namen und Eckdaten)."""

    kette: list[WahlOrt]
    eintraege: list[WahlEintrag]
