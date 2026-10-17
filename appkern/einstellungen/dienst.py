"""Einstellungen einer App, alle in der Oberfläche änderbar.

Die App beschreibt ihre Einstellungen als Pydantic-Modell (Vorgaben, `Field(title=..., description=...)`, Auswahl über
`Literal`, Geheimnisse als `SecretStr`). Gespeichert wird, was in der Oberfläche gesetzt wurde; `None` setzt zurück.
Ein Wert kommt aus der Datenbank (was in der Oberfläche gesetzt wurde), sonst aus der Umgebung (`<PRAEFIX><FELD>` in Großbuchstaben, etwa beim ersten Start),
sonst aus der Vorgabe des Modells.

Geheimnisse gehen in `felder()` nur verdeckt hinaus (bis auf die letzten vier Zeichen); `geheimnis()` deckt eines auf
(für das Auge in der Oberfläche). In Protokoll und Ausgaben erscheinen sie nie.
"""

from __future__ import annotations

import json
import os
import types
import typing
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, SecretStr, ValidationError

from appkern.datenbank import Datenbank

from .modelle import Angebot, Feld, FeldArt

M = TypeVar("M", bound=BaseModel)
SCHEMA = [
    """
    CREATE TABLE einstellung (
        schluessel   TEXT PRIMARY KEY,
        wert         TEXT NOT NULL,
        geaendert_am TEXT NOT NULL
    );
    """,
]


class UnbekanntesFeld(KeyError):
    pass


def verdeckt(wert: str) -> str:
    """Bis auf die letzten vier Zeichen verdeckt; kurze Werte ganz."""
    if not wert:
        return ""
    return "•" * 8 + (wert[-4:] if len(wert) > 8 else "")


def _klartext(wert: Any) -> Any:
    return wert.get_secret_value() if isinstance(wert, SecretStr) else wert


def _kern(annotation: Any) -> Any:
    """`X | None` zu `X`."""
    if typing.get_origin(annotation) in (typing.Union, types.UnionType):
        rest = [a for a in typing.get_args(annotation) if a is not type(None)]
        if len(rest) == 1:
            return rest[0]
    return annotation


def _art(annotation: Any) -> tuple[FeldArt, list[str]]:
    kern = _kern(annotation)
    if kern is SecretStr:
        return "geheimnis", []
    if typing.get_origin(kern) is Literal:
        return "auswahl", [str(a) for a in typing.get_args(kern)]
    if kern is bool:
        return "schalter", []
    if kern in (int, float):
        return "zahl", []
    if kern is str:
        return "text", []
    return "liste" if typing.get_origin(kern) in (list, tuple) else "wert", []


class Einstellungen(Generic[M]):
    def __init__(self, db: Datenbank, modell: type[M], *, umgebung_praefix: str = "",
                 umgebung: Mapping[str, str] | None = None) -> None:
        self.db = db
        self.modell = modell
        self.praefix = umgebung_praefix
        self._umgebung = umgebung if umgebung is not None else os.environ
        self._gespeichert: dict[str, Any] = {}
        self._stand: M | None = None
        self._beobachter: list[Callable[[M, set[str]], Awaitable[None] | None]] = []
        self._anbieter: dict[str, Callable[[], Awaitable[Angebot]]] = {}

    async def starten(self) -> M:
        await self.db.einrichten("einstellungen", SCHEMA)
        zeilen = await self.db.zeilen("SELECT schluessel, wert FROM einstellung")
        self._gespeichert = {z["schluessel"]: json.loads(z["wert"]) for z in zeilen if z["schluessel"] in self.modell.model_fields}
        self._stand = self._bauen(self._gespeichert)
        return self._stand

    def _aus_umgebung(self) -> dict[str, Any]:
        werte: dict[str, Any] = {}
        if not self.praefix:
            return werte
        for name, feld in self.modell.model_fields.items():
            roh = self._umgebung.get(f"{self.praefix}{name}".upper())
            if roh is None:
                continue
            art, _ = _art(feld.annotation)
            if art in ("liste", "wert"):
                werte[name] = json.loads(roh)
            elif art == "schalter":
                werte[name] = roh.strip().lower() in ("1", "true", "ja", "an")
            else:
                werte[name] = roh
        return werte

    def _bauen(self, gespeichert: dict[str, Any]) -> M:
        return self.modell.model_validate({**self._aus_umgebung(), **gespeichert})

    @property
    def stand(self) -> M:
        """Die gültigen Einstellungen (nach `starten`)."""
        if self._stand is None:
            raise RuntimeError("Einstellungen sind nicht gestartet")
        return self._stand

    def anbieten(self, name: str, anbieter: Callable[[], Awaitable[Angebot]]) -> None:
        """Für ein Feld eine Auswahl aus dem System anbieten (siehe `Angebot`); die Oberfläche zeigt sie statt eines
        bloßen Textfelds."""
        if name not in self.modell.model_fields:
            raise UnbekanntesFeld(name)
        self._anbieter[name] = anbieter

    async def angebot(self, name: str) -> Angebot:
        anbieter = self._anbieter.get(name)
        if anbieter is None:
            raise UnbekanntesFeld(name)
        return await anbieter()

    def bei_aenderung(self, beobachter: Callable[[M, set[str]], Awaitable[None] | None]) -> None:
        """`beobachter(neuer_stand, geaenderte_felder)` nach jeder Änderung, etwa um einen Zugang neu aufzubauen."""
        self._beobachter.append(beobachter)

    async def aendern(self, werte: Mapping[str, Any]) -> set[str]:
        """Prüft alle Werte zusammen (alles oder nichts) und speichert, was sich ändert. Liefert die geänderten
        Felder. Ein leerer Wert für ein Geheimnis heißt: unverändert lassen; `None` heißt: auf die Vorgabe zurück."""
        unbekannt = set(werte) - set(self.modell.model_fields)
        if unbekannt:
            raise UnbekanntesFeld(", ".join(sorted(unbekannt)))
        alt = self.stand
        neu_gespeichert = dict(self._gespeichert)
        for name, wert in werte.items():
            art, _ = _art(self.modell.model_fields[name].annotation)
            if art == "geheimnis" and wert == "":
                continue
            if wert is None:
                neu_gespeichert.pop(name, None)
            else:
                neu_gespeichert[name] = wert
        neu = self._bauen(neu_gespeichert)               # wirft ValidationError, bevor etwas gespeichert ist
        geaendert = {n for n in self.modell.model_fields if _klartext(getattr(neu, n)) != _klartext(getattr(alt, n))}
        gespeichert = {n: _json(_klartext(getattr(neu, n))) for n in neu_gespeichert}
        jetzt = datetime.now(timezone.utc).isoformat()

        def schreiben(v) -> None:
            for name in self.modell.model_fields:
                if name in gespeichert:
                    v.execute("INSERT INTO einstellung (schluessel, wert, geaendert_am) VALUES (?,?,?) "
                              "ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert, geaendert_am=excluded.geaendert_am",
                              (name, json.dumps(gespeichert[name], ensure_ascii=False), jetzt))
                else:
                    v.execute("DELETE FROM einstellung WHERE schluessel=?", (name,))

        await self.db.transaktion(schreiben)
        self._gespeichert = gespeichert
        self._stand = neu
        if geaendert:
            for b in self._beobachter:
                ergebnis = b(neu, geaendert)
                if isinstance(ergebnis, Awaitable):
                    await ergebnis
        return geaendert

    def felder(self) -> list[Feld]:
        """Beschreibung für die Oberfläche; Geheimnisse verdeckt."""
        vorgabe = self.modell()
        aus_umgebung = self._aus_umgebung()
        felder = []
        for name, info in self.modell.model_fields.items():
            art, optionen = _art(info.annotation)
            wert = _klartext(getattr(self.stand, name))
            herkunft = "gespeichert" if name in self._gespeichert else ("umgebung" if name in aus_umgebung else "vorgabe")
            extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
            kleinste, groesste = _grenzen(info)
            felder.append(Feld(
                name=name, titel=info.title or name, beschreibung=info.description or "", art=art, optionen=optionen,
                beschriftungen={str(k): str(v) for k, v in (extra.get("beschriftungen") or {}).items()},
                schritt=extra.get("schritt"), kleinste=kleinste, groesste=groesste, einheit=str(extra.get("einheit", "")),
                angebot=name in self._anbieter,
                wert=verdeckt(wert) if art == "geheimnis" else _json(wert), gesetzt=bool(wert) if art == "geheimnis" else True,
                vorgabe=None if art == "geheimnis" else _json(_klartext(getattr(vorgabe, name))), herkunft=herkunft,
                gruppe=str(extra.get("gruppe", "")) or None))
        return felder

    def geheimnis(self, name: str) -> str:
        """Ein Geheimnis im Klartext, nur für das Auge in der Verwaltung."""
        info = self.modell.model_fields.get(name)
        if info is None or _art(info.annotation)[0] != "geheimnis":
            raise UnbekanntesFeld(name)
        return _klartext(getattr(self.stand, name)) or ""


def _grenzen(info: Any) -> tuple[float | None, float | None]:
    """Untere und obere Grenze aus `Field(ge=..., le=...)` (auch gt und lt)."""
    kleinste = groesste = None
    for m in info.metadata:
        for attr in ("ge", "gt"):
            if getattr(m, attr, None) is not None:
                kleinste = float(getattr(m, attr))
        for attr in ("le", "lt"):
            if getattr(m, attr, None) is not None:
                groesste = float(getattr(m, attr))
    return kleinste, groesste


def _json(wert: Any) -> Any:
    if isinstance(wert, BaseModel):
        return wert.model_dump(mode="json")
    if isinstance(wert, (list, tuple)):
        return [_json(w) for w in wert]
    return wert


__all__ = ["Einstellungen", "UnbekanntesFeld", "ValidationError", "verdeckt"]
