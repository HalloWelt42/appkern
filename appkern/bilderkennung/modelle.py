"""Protokoll der Bilderkennung: was gefragt wird und was herauskommt. Rahmen in Anteilen des Bildes (0 bis 1), der Ursprung
oben links, wie im Browser; so passen sie auf jedes angezeigte Bild, gleich wie groß."""

from __future__ import annotations

from pydantic import BaseModel, Field

SPRACHEN = ["de-DE", "en-US"]


class Rahmen(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    b: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)


class Textstelle(BaseModel):
    """Eine Zeile Text, wie Apple Vision sie liest."""
    text: str
    rahmen: Rahmen
    sicherheit: float = Field(ge=0, le=1)


class Gesicht(BaseModel):
    rahmen: Rahmen
    sicherheit: float = Field(ge=0, le=1)


class Erkennen(BaseModel):
    """Der Auftrag. `genau`: die gründliche Texterkennung (langsamer); `sprachen` in der Reihenfolge, in der sie gelten."""
    sprachen: list[str] = Field(default_factory=lambda: list(SPRACHEN), max_length=8)
    texte: bool = True
    gesichter: bool = True
    genau: bool = True


class Erkannt(BaseModel):
    breite: int
    hoehe: int
    texte: list[Textstelle] = Field(default_factory=list)
    gesichter: list[Gesicht] = Field(default_factory=list)
    ms: float                                   # gerechnet am Mac, ohne den Weg dorthin
