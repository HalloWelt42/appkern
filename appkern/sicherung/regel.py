"""Regel der Sicherung, für alle Apps gleich; die Werte stellt jede App in ihren Einstellungen ein (Gruppe Sicherung,
`sicherung_abstand_tage`, `sicherung_vor_ausrollen_ab_stunden`, `sicherung_behalten`):

- regelmäßig: eine neue, wenn die jüngste älter ist als `abstand_tage` (Vorgabe 7: einmal je Woche, nicht jede Nacht);
- vor dem Ausrollen: eine neue nur, wenn die jüngste älter ist als `vor_ausrollen_ab_stunden` (Vorgabe 24);
- nie ohne Änderung: hat sich die Datenbank seit der jüngsten nicht geändert, entsteht keine neue;
- höchstens `behalten` Stände (Vorgabe 3); durchgesetzt bei jedem Blick, nicht erst beim Anlegen, so räumt der erste
  Lauf einer neuen Fassung alte Stapel ab.

Eine Sicherung ist eine stimmige Kopie der SQLite-Datenbank über deren Sicherungsschnittstelle (auch während die App
schreibt): `<kennung>-JJJJMMTT-HHMMSS.sqlite` im Ordner der Sicherungen. Sie entsteht unter einem Namen mit Punkt vorn
(`.<name>.teil`), den weder diese Regel noch das Werkzeug Sicherungen am Mac als Stand zählt, und heißt erst fertig so.
Ihre Änderungszeit ist der Beginn der Kopie. Damit ist "geändert" billig und ohne die Datei zu lesen: Datenbankdatei
oder WAL wurden nach dem Beginn der jüngsten Kopie geschrieben. Deshalb liegt kein Merkzettel neben den Sicherungen
(das Werkzeug am Mac zählt jeden Eintrag des Ordners), und die Sicherung schreibt nie in die Datenbank (das wäre selbst
eine Änderung). Ein Neustart ohne neue Daten kann einmal als Änderung zählen (SQLite überträgt dabei das WAL in die
Datei); das nimmt die Regel hin, statt die ganze Datenbank zu vergleichen.
"""

from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

TAG_S = 24 * 3600
STUNDE_S = 3600
#: eine Teildatei, die so lange nicht fertig wurde, ist von einer abgebrochenen Kopie übrig (etwa ein Neustart mitten
#: in der Kopie) und geht beim Aufräumen; keine Kopie dauert annähernd so lange
TEIL_VERWAIST_S = TAG_S


class Regel(BaseModel):
    """Die Werte der Regel; eine App bildet sie aus ihren Einstellungen."""

    model_config = ConfigDict(frozen=True)

    abstand_tage: int = Field(ge=1)
    vor_ausrollen_ab_stunden: int = Field(ge=0)
    behalten: int = Field(ge=1)


#: die Vorgaben, eine Stelle für alle Apps (die Grundeinstellungen nehmen sie als Vorgabe ihrer Felder)
VORGABE = Regel(abstand_tage=7, vor_ausrollen_ab_stunden=24, behalten=3)


class Ergebnis(BaseModel):
    """Was ein Blick ergab: ob eine neue Sicherung entstand und warum (nicht), was weg ist, was bleibt."""

    angelegt: str | None = None
    grund: str
    entfernt: list[str] = []
    staende: int = 0

    def zeile(self) -> str:
        teile = [f"gesichert: {self.angelegt}" if self.angelegt else f"keine neue Sicherung: {self.grund}"]
        if self.entfernt:
            teile.append(f"entfernt: {', '.join(self.entfernt)}")
        teile.append(f"{self.staende} {'Stand' if self.staende == 1 else 'Stände'} im Ordner")
        return "; ".join(teile)


def kopieren(quelle: Path, ziel: Path) -> None:
    """Stimmige Kopie über die Sicherungsschnittstelle von SQLite, auch während die App schreibt."""
    q = sqlite3.connect(quelle)
    z = sqlite3.connect(ziel)
    try:
        q.backup(z)
    finally:
        z.close()
        q.close()


def dauer(sekunden: float) -> str:
    """Eine Dauer in Worten, grob genug für eine Meldung."""
    if sekunden < 2 * STUNDE_S:
        return f"{int(sekunden // 60)} Minuten"
    if sekunden < 2 * TAG_S:
        return f"{int(sekunden // STUNDE_S)} Stunden"
    return f"{int(sekunden // TAG_S)} Tage"


class Ablage:
    """Die Sicherungen einer App: ihre Datenbank und der Ordner, in dem die Kopien liegen."""

    def __init__(self, datenbank: Path, ordner: Path, kennung: str) -> None:
        self.datenbank = Path(datenbank)
        self.ordner = Path(ordner)
        self.kennung = kennung

    def staende(self) -> list[Path]:
        """Die fertigen Sicherungen, die jüngste zuerst (nach Änderungszeit, also nach dem Beginn der Kopie)."""
        if not self.ordner.is_dir():
            return []
        fertig = [p for p in self.ordner.glob(f"{self.kennung}-*.sqlite") if p.is_file()]
        return sorted(fertig, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)

    def zuletzt_geschrieben(self) -> float | None:
        """Wann Datenbankdatei oder WAL zuletzt geschrieben wurden; None ohne Datenbank."""
        if not self.datenbank.is_file():
            return None
        wal = self.datenbank.with_name(self.datenbank.name + "-wal")
        return max(p.stat().st_mtime for p in (self.datenbank, wal) if p.exists())

    def geaendert_seit(self, sicherung: Path) -> bool:
        geschrieben = self.zuletzt_geschrieben()
        return geschrieben is not None and geschrieben >= sicherung.stat().st_mtime

    def anlegen(self, beginn: float) -> Path:
        """Neue Sicherung mit dem Beginn der Kopie als Name und Änderungszeit."""
        self.ordner.mkdir(parents=True, exist_ok=True)
        stempel = time.strftime("%Y%m%d-%H%M%S", time.localtime(beginn))
        ziel = self.ordner / f"{self.kennung}-{stempel}.sqlite"
        zaehler = 2
        while ziel.exists():
            ziel = self.ordner / f"{self.kennung}-{stempel}-{zaehler}.sqlite"
            zaehler += 1
        teil = self.ordner / f".{ziel.name}.teil"
        try:
            kopieren(self.datenbank, teil)
            os.utime(teil, (beginn, beginn))
            teil.rename(ziel)
        finally:
            teil.unlink(missing_ok=True)
        return ziel

    def aufraeumen(self, behalten: int, jetzt: float) -> list[Path]:
        """Höchstens `behalten` Sicherungen; dazu Teildateien abgebrochener Kopien. Nur, was zum eigenen Muster passt."""
        weg = self.staende()[behalten:]
        if self.ordner.is_dir():
            weg += [p for p in self.ordner.glob(f".{self.kennung}-*.teil")
                    if p.is_file() and jetzt - p.stat().st_mtime > TEIL_VERWAIST_S]
        for p in weg:
            p.unlink(missing_ok=True)
        return weg


def sichern_wenn_faellig(ablage: Ablage, mindestalter_s: float, behalten: int, jetzt: float) -> Ergebnis:
    """Der eine Blick hinter beiden Anlässen: neu, wenn die jüngste mindestens `mindestalter_s` alt ist (oder es keine
    gibt) und sich die Datenbank seitdem geändert hat; danach bleiben höchstens `behalten`."""
    staende = ablage.staende()
    juengste = staende[0] if staende else None
    angelegt: Path | None = None
    if ablage.zuletzt_geschrieben() is None:
        grund = "noch keine Datenbank"
    elif juengste is not None and (alter := jetzt - juengste.stat().st_mtime) < mindestalter_s:
        grund = f"die jüngste ist {dauer(alter)} alt, eine neue erst ab {dauer(mindestalter_s)}"
    elif juengste is not None and not ablage.geaendert_seit(juengste):
        grund = "die Datenbank ist seit der jüngsten unverändert"
    else:
        angelegt = ablage.anlegen(jetzt)
        grund = "fällig und geändert" if juengste is not None else "noch keine Sicherung"
    entfernt = ablage.aufraeumen(behalten, jetzt)
    return Ergebnis(angelegt=angelegt.name if angelegt else None, grund=grund, entfernt=[p.name for p in entfernt],
                    staende=len(ablage.staende()))


def regelmaessig(ablage: Ablage, regel: Regel, jetzt: float) -> Ergebnis:
    return sichern_wenn_faellig(ablage, regel.abstand_tage * TAG_S, regel.behalten, jetzt)


def vor_ausrollen(ablage: Ablage, regel: Regel, jetzt: float) -> Ergebnis:
    return sichern_wenn_faellig(ablage, regel.vor_ausrollen_ab_stunden * STUNDE_S, regel.behalten, jetzt)
