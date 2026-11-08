"""Ablage der Dateien einer App (WIKI-11): im eigenen Zweig der Kellerwolke, wenn eine eingerichtet ist, sonst im Ordner
`ablage` des Datenordners der App. So laufen Funktionen, die Dateien nur ablegen und wieder lesen (etwa Notizen als
Markdown, fertige Bücher, Vorlagen, Bilder an Notizen), auch ohne Kellerwolke. Welche gilt, entscheidet das Gerüst an
einer Stelle (`Geruest.ablage`); die App fragt sie bei jeder Arbeit neu, denn sie wechselt mit den Einstellungen.

Beide können dasselbe und nur das: eine Datei unter einem Pfad schreiben (relativ zur Wurzel der App, Teile mit /
getrennt; eine vorhandene bekommt einen neuen Stand, fehlende Ordner entstehen mit), finden, lesen, einen Ordner
auflisten und löschen. Gelesen und gelöscht wird über die Kennung eines Eintrags (Kellerwolke: der Knoten, Ordner: der
Pfad), die eine App sich merken kann. Was nur die Kellerwolke kann (Versionen, Begleiter, Herkunft, Anfragen,
Beobachten), bleibt bei `appkern.kellerwolke`.

Löschen heißt in der Kellerwolke: in den Papierkorb des Kontos (wiederherstellbar); im Ordner ist es endgültig.
Fehler kommen als `AblageFehler` mit einer Meldung für Menschen, eine fehlende Datei beim Lesen als `NichtDa`.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .kellerwolke import Kellerwolke, KellerwolkeFehler, NichtGefunden, StandVeraltet
from .kellerwolke.modelle import Knoten

AblageArt = Literal["kellerwolke", "ordner"]
_STUECK = 256 * 1024
_ZWISCHEN = ".teil-"          # Name einer Datei, die gerade im Ordner entsteht (nie in der Liste)


class AblageFehler(Exception):
    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


class NichtDa(AblageFehler):
    """Die Datei (oder der Ordner) liegt nicht (mehr) in der Ablage."""


@dataclass(frozen=True)
class Eintrag:
    kennung: str          # zum Lesen und Löschen: Knoten der Kellerwolke oder Pfad im Ordner
    pfad: str             # relativ zur Wurzel der App
    name: str
    ordner: bool = False
    groesse: int = 0
    stand: str = ""       # wechselt mit jedem Schreiben


class Ablage(ABC):
    art: AblageArt
    name: str             # für Menschen: wo die Dateien liegen ("Kellerwolke", "Datenordner")

    @abstractmethod
    async def ort(self, pfad: str = "") -> str:
        """Wo ein Pfad liegt, für Menschen (Kellerwolke: im Zweig der App, Ordner: im Datenordner der App)."""

    @abstractmethod
    async def schreiben(self, pfad: str, daten: bytes, *, inhaltstyp: str, nur_neu: bool = False) -> Eintrag:
        """Anlegen oder überschreiben; `nur_neu` legt nur an (gibt es die Datei schon, `AblageFehler`)."""

    @abstractmethod
    async def finden(self, pfad: str) -> Eintrag | None:
        """Der Eintrag unter einem Pfad, oder None."""

    @abstractmethod
    def lesen(self, kennung: str) -> AsyncIterator[bytes]:
        """Inhalt stückweise; `NichtDa`, wenn die Datei fehlt (beim ersten Stück)."""

    @abstractmethod
    async def liste(self, ordner: str) -> list[Eintrag]:
        """Was in einem Ordner liegt (Ordner vor Dateien, nach Namen); leer, wenn es ihn nicht gibt."""

    @abstractmethod
    async def loeschen(self, kennung: str) -> bool:
        """Datei oder Ordner samt Inhalt löschen; False, wenn es sie nicht (mehr) gab."""

    async def lesen_ganz(self, kennung: str) -> bytes:
        """Nur für kleine Inhalte (Texte, Vorlagen)."""
        return b"".join([d async for d in self.lesen(kennung)])

    async def weg(self, pfad: str) -> bool:
        """Was unter einem Pfad liegt, löschen; False, wenn dort nichts lag."""
        eintrag = await self.finden(pfad)
        return eintrag is not None and await self.loeschen(eintrag.kennung)


def _geordnet(eintraege: list[Eintrag]) -> list[Eintrag]:
    return sorted(eintraege, key=lambda e: (not e.ordner, e.name.casefold()))


def teile(pfad: str) -> list[str]:
    """Die Teile eines Pfads relativ zur Wurzel; nie aus ihr heraus (kein leerer Teil, kein . oder .., kein \\)."""
    stuecke = [t for t in pfad.strip("/").split("/")] if pfad.strip("/") else []
    for t in stuecke:
        if t in ("", ".", "..") or "\\" in t or "\0" in t:
            raise AblageFehler(f"Ungültiger Pfad in der Ablage: {pfad!r}")
    return stuecke


# ----- Kellerwolke ----------------------------------------------------------------------------------------------------

class KellerwolkeAblage(Ablage):
    """Im Zweig der App in der Kellerwolke (`Apps/<App>`). `ersatz_zweig` nennt `ort` den Ort, solange die Kellerwolke
    ihren Zweig nicht genannt hat (etwa wenn sie gerade nicht antwortet)."""

    art: AblageArt = "kellerwolke"
    name = "Kellerwolke"

    def __init__(self, kellerwolke: Kellerwolke, ersatz_zweig: str = "") -> None:
        self.kw = kellerwolke
        self._ersatz = ersatz_zweig
        self._zweig: str | None = None

    async def zweig(self) -> str:
        if self._zweig is None:
            try:
                self._zweig = (await self.kw.ich()).zweig
            except KellerwolkeFehler as f:
                raise AblageFehler(f"Die Kellerwolke antwortet nicht: {f}") from f
        return self._zweig

    async def _voll(self, pfad: str) -> str:
        return "/".join([await self.zweig(), *teile(pfad)])

    def _eintrag(self, k: Knoten, zweig: str) -> Eintrag:
        pfad = k.pfad[len(zweig) + 1:] if k.pfad.startswith(f"{zweig}/") else k.pfad
        return Eintrag(kennung=str(k.id), pfad=pfad, name=k.name, ordner=k.ist_ordner, groesse=k.groesse or 0,
                       stand=k.etag or "")

    async def ort(self, pfad: str = "") -> str:
        try:
            zweig = await self.zweig()
        except AblageFehler:
            zweig = self._ersatz
        return "/".join(t for t in [zweig, *teile(pfad)] if t)

    async def schreiben(self, pfad: str, daten: bytes, *, inhaltstyp: str, nur_neu: bool = False) -> Eintrag:
        voll = await self._voll(pfad)
        try:
            await self.kw.ordner(voll.rsplit("/", 1)[0])
            if nur_neu:
                k = await self.kw.schreiben(voll, daten, nur_neu=True, inhaltstyp=inhaltstyp)
            else:
                alt = await self.kw.finden(voll)
                k = await self.kw.schreiben(voll, daten, stand=alt.etag if alt else None, inhaltstyp=inhaltstyp)
        except StandVeraltet as f:
            raise AblageFehler(f"{pfad} liegt schon in der Kellerwolke") from f
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Die Kellerwolke nimmt {pfad} nicht an: {f}") from f
        return self._eintrag(k, await self.zweig())

    async def finden(self, pfad: str) -> Eintrag | None:
        voll = await self._voll(pfad)
        try:
            k = await self.kw.finden(voll)
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Die Kellerwolke antwortet nicht: {f}") from f
        return self._eintrag(k, await self.zweig()) if k is not None else None

    async def lesen(self, kennung: str) -> AsyncIterator[bytes]:
        try:
            async for stueck in self.kw.lesen(kennung):
                yield stueck
        except NichtGefunden as f:
            raise NichtDa("Die Datei liegt nicht mehr in der Kellerwolke") from f
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Die Kellerwolke ist gerade nicht erreichbar: {f}") from f

    async def liste(self, ordner: str) -> list[Eintrag]:
        voll, zweig = await self._voll(ordner), await self.zweig()
        try:
            k = await self.kw.finden(voll)
            if k is None or not k.ist_ordner:
                return []
            return _geordnet([self._eintrag(x, zweig) async for x in self.kw.alle_kinder(k.id)])
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Die Kellerwolke antwortet nicht: {f}") from f

    async def loeschen(self, kennung: str) -> bool:
        try:
            await self.kw.loeschen(kennung)                 # in den Papierkorb des Kontos, wiederherstellbar
        except NichtGefunden:
            return False
        except KellerwolkeFehler as f:
            raise AblageFehler(f"Die Kellerwolke löscht nicht: {f}") from f
        return True


# ----- Ordner ---------------------------------------------------------------------------------------------------------

class OrdnerAblage(Ablage):
    """In einem Ordner auf dem Rechner der App (im Gerüst `<daten>/ablage`). Eine Datei entsteht unter einem
    Zwischennamen und heißt erst fertig so, wie sie soll; so liest nie jemand eine halbe."""

    art: AblageArt = "ordner"
    name = "Datenordner"

    def __init__(self, wurzel: Path) -> None:
        self.wurzel = Path(wurzel)

    def _datei(self, pfad: str) -> Path:
        return self.wurzel.joinpath(*teile(pfad))

    def _eintrag(self, pfad: str, p: Path) -> Eintrag:
        s = p.stat()
        return Eintrag(kennung=pfad, pfad=pfad, name=p.name, ordner=p.is_dir(), groesse=0 if p.is_dir() else s.st_size,
                       stand=f"{s.st_mtime_ns:x}-{s.st_size:x}")

    async def ort(self, pfad: str = "") -> str:
        return "/".join([self.wurzel.name, *teile(pfad)])

    async def schreiben(self, pfad: str, daten: bytes, *, inhaltstyp: str, nur_neu: bool = False) -> Eintrag:
        stuecke = teile(pfad)
        if not stuecke:
            raise AblageFehler("Ohne Namen lässt sich nichts ablegen")
        ziel = self._datei(pfad)

        def schreiben() -> Eintrag:
            ziel.parent.mkdir(parents=True, exist_ok=True)
            if nur_neu and ziel.exists():
                raise AblageFehler(f"{pfad} liegt schon im Datenordner")
            teil = ziel.with_name(f"{_ZWISCHEN}{uuid.uuid4().hex}")
            try:
                teil.write_bytes(daten)
                os.replace(teil, ziel)
            finally:
                teil.unlink(missing_ok=True)
            return self._eintrag("/".join(stuecke), ziel)

        try:
            return await asyncio.to_thread(schreiben)
        except OSError as f:
            raise AblageFehler(f"{pfad} ließ sich im Datenordner nicht ablegen: {f.strerror or f}") from f

    async def finden(self, pfad: str) -> Eintrag | None:
        datei = self._datei(pfad)
        try:
            return await asyncio.to_thread(lambda: self._eintrag("/".join(teile(pfad)), datei) if datei.exists() else None)
        except OSError as f:
            raise AblageFehler(f"Der Datenordner ist nicht lesbar: {f.strerror or f}") from f

    async def lesen(self, kennung: str) -> AsyncIterator[bytes]:
        datei = self._datei(kennung)
        try:
            datei_objekt = await asyncio.to_thread(datei.open, "rb")
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError) as f:
            raise NichtDa("Die Datei liegt nicht mehr im Datenordner") from f
        except OSError as f:
            raise AblageFehler(f"Der Datenordner ist nicht lesbar: {f.strerror or f}") from f
        try:
            while stueck := await asyncio.to_thread(datei_objekt.read, _STUECK):
                yield stueck
        finally:
            datei_objekt.close()

    async def liste(self, ordner: str) -> list[Eintrag]:
        stuecke, verzeichnis = teile(ordner), self._datei(ordner)

        def lesen() -> list[Eintrag]:
            if not verzeichnis.is_dir():
                return []
            eintraege = [self._eintrag("/".join([*stuecke, p.name]), p) for p in verzeichnis.iterdir()
                         if not p.name.startswith(_ZWISCHEN)]
            return _geordnet(eintraege)

        try:
            return await asyncio.to_thread(lesen)
        except OSError as f:
            raise AblageFehler(f"Der Datenordner ist nicht lesbar: {f.strerror or f}") from f

    async def loeschen(self, kennung: str) -> bool:
        if not teile(kennung):
            raise AblageFehler("Die Wurzel der Ablage lässt sich nicht löschen")
        ziel = self._datei(kennung)

        def loeschen() -> bool:
            if ziel.is_dir():
                shutil.rmtree(ziel)
                return True
            try:
                ziel.unlink()
            except FileNotFoundError:
                return False
            return True

        try:
            return await asyncio.to_thread(loeschen)
        except OSError as f:
            raise AblageFehler(f"Im Datenordner ließ sich {kennung} nicht löschen: {f.strerror or f}") from f


__all__ = ["Ablage", "AblageArt", "AblageFehler", "Eintrag", "KellerwolkeAblage", "NichtDa", "OrdnerAblage", "teile"]
