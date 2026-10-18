"""Was die Fassade der Leitstelle liefert und was eine App ihr gibt, als Pydantic-Modelle.

Unbekannte Felder werden überlesen: eine neuere Leitstelle mit zusätzlichen Angaben bricht ältere Apps nicht.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Prioritaet = Literal["hintergrund", "normal", "hoch", "dringend"]
Rolle = Literal["system", "user", "assistant", "tool"]


class _Modell(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Modell(_Modell):
    """Ein Modell oder Dienst, den die App nutzen darf (`GET /v1/models`)."""

    id: str
    name: str = ""
    geladen: bool = False
    knoten: str | None = None
    extern: bool = False
    faehigkeiten: list[str] = Field(default_factory=list)
    gb: float | None = None


class Nachricht(_Modell):
    """Eine Nachricht im Gespräch. `inhalt` ist Text oder, mit Bildern, eine Liste von Teilen im OpenAI-Format."""

    rolle: Rolle
    inhalt: str | list[dict[str, Any]]

    @classmethod
    def system(cls, text: str) -> Nachricht:
        return cls(rolle="system", inhalt=text)

    @classmethod
    def nutzer(cls, inhalt: str | list[dict[str, Any]]) -> Nachricht:
        return cls(rolle="user", inhalt=inhalt)

    @classmethod
    def assistent(cls, text: str) -> Nachricht:
        return cls(rolle="assistant", inhalt=text)

    def fuer_fassade(self) -> dict[str, Any]:
        return {"role": self.rolle, "content": self.inhalt}


class Verbrauch(_Modell):
    eingabe: int = 0
    ausgabe: int = 0
    gesamt: int = 0


class ChatAntwort(_Modell):
    """Eine fertige Antwort. `abgebrochen`: in der Leitstelle abgebrochen, `text` ist dann der bisherige Teil."""

    text: str
    denken: str = ""                 # Denkfeld des Modells (reasoning_content), falls es eins liefert
    ende: str | None = None
    abgebrochen: bool = False
    modell: str | None = None
    knoten: str | None = None
    auftrag: str | None = None
    verbrauch: Verbrauch | None = None


class Stueck(_Modell):
    """Ein Stück Text aus einem Strom."""

    art: Literal["stueck"] = "stueck"
    text: str


class Wartet(_Modell):
    """Der Auftrag wartet (alle paar Sekunden, solange er wartet); `grund` im Wortlaut der Leitstelle."""

    art: Literal["wartet"] = "wartet"
    grund: str
    sekunden: int | None = None


class Ende(_Modell):
    """Der Strom ist zu Ende. `abgebrochen`: in der Leitstelle abgebrochen; der Text bis hier ist das Teilergebnis."""

    art: Literal["ende"] = "ende"
    ende: str | None = None
    abgebrochen: bool = False
    modell: str | None = None
    auftrag: str | None = None
    verbrauch: Verbrauch | None = None


Ereignis = Stueck | Wartet | Ende


class Einbettungen(_Modell):
    vektoren: list[list[float]]
    modell: str | None = None
    verbrauch: Verbrauch | None = None
