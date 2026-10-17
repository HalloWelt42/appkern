"""Protokolleinträge, wie sie nach außen gehen."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel

Stufe = Literal["info", "warnung", "fehler"]


class Eintrag(BaseModel):
    id: str
    zeit: datetime
    ereignis: str
    stufe: Stufe
    bezug_art: str | None = None
    bezug_id: str | None = None
    bezug_name: str | None = None
    text: str = ""
    daten: dict[str, Any] | None = None


class Seite(BaseModel):
    eintraege: list[Eintrag]
    gesamt: int
