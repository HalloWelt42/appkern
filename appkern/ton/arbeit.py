"""Tonarbeit: jede Rechnung auf Ton an genau einem Ort (Nutzer 18.10.2026: "pi ist nur datenlieferant").

Drei Arbeitsschritte, jeder nimmt seine Dateien mit und schreibt seine Ergebnisse an Orte, die der Aufrufer nennt:

- `aufbereiten`: eine Datei (auch Video) mit beliebig vielen Ausgaben (Format, Zeitbereich, auf Wunsch begrenzt,
  an den Rändern geblendet, mit Stille davor und danach) und Messungen (Eigenschaften, Pausen, Wellenform,
  Pegelverlauf, laute Spanne);
- `blenden`: Stücke (mit Schnittgrenzen) mit Gleichleistungsblende zu einem;
- `legen`: Stücke an ihre Zeiten (gestaucht, mit glatten Rändern), mindestens so lang wie verlangt, begrenzt, genau
  einmal ins Zielformat; auf Wunsch mit Wellenform.

Zwei Seiten derselben Schnittstelle: `TonHier` rechnet (ffmpeg und numpy; nur im Tondienst auf dem Mac und in
Tests), `TonDienst` (dienst.py) reicht dieselben Aufträge über die Leitstelle an den Tondienst. Was eine App daraus
macht (Prüfen eines Sprechstücks, Zeitlage, Wahl einer Referenzstelle), bleibt in der App.
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from ..leitstelle.geduld import geduldig
from ..leitstelle.modelle import Prioritaet
from . import rechnen
from .ton import Eigenschaften, Pause, Ton, TonFehler, Tonformat

ENDUNG = r"^\.[a-z0-9]{2,5}$"


class Ausgabe(BaseModel):
    """Eine Datei aus der Eingabe. Die Endung bestimmt den Behälter. Bearbeitet (Spitze, Blende, Vor- und Nachlauf)
    wird in Gleitkomma bei der Rate des Formats, mono."""

    model_config = ConfigDict(frozen=True)
    format: Tonformat
    endung: str = Field(".wav", pattern=ENDUNG)
    beginn_s: float | None = Field(None, ge=0)
    ende_s: float | None = Field(None, ge=0)
    spitze: float | None = Field(None, gt=0, le=1, description="liegt die Spitze darüber, wird das Ganze leiser")
    blende_ms: float = Field(0, ge=0, le=1000, description="Ein- und Ausblenden an den Rändern")
    vorlauf_s: float = Field(0, ge=0, le=10)
    nachlauf_s: float = Field(0, ge=0, le=10)

    @property
    def bearbeitet(self) -> bool:
        return self.spitze is not None or self.blende_ms > 0 or self.vorlauf_s > 0 or self.nachlauf_s > 0


class PausenWahl(BaseModel):
    schwelle_db: float = Field(-35.0, ge=-90, le=0)
    mindestens_s: float = Field(0.4, gt=0, le=60)


class LautWahl(BaseModel):
    """Laute Spanne: vom ersten bis zum letzten Wert über der Schwelle, samt Rand."""

    rate: int = Field(24000, ge=8000, le=192000)
    schwelle_db: float = Field(-45.0, ge=-90, le=0)
    rand_ms: float = Field(40, ge=0, le=1000)


class Messen(BaseModel):
    pausen: PausenWahl | None = None
    wellenform: int | None = Field(None, ge=10, le=10000, description="so viele Punkte")
    pegel_ms: int | None = Field(None, ge=10, le=1000, description="Rahmen des Pegelverlaufs")
    laut: LautWahl | None = None


class Aufbereiten(BaseModel):
    ausgaben: list[Ausgabe] = Field(default_factory=list, max_length=64)
    messen: Messen = Field(default_factory=Messen)


class Pegelverlauf(BaseModel):
    """Je Rahmen Effektivwert und Spitze (linear, 0 bis 1), vom Anfang der Datei an."""

    rahmen_ms: int
    rms: list[float]
    spitze: list[float]


class LauteSpanne(BaseModel):
    von_s: float
    bis_s: float
    spitze: float

    @property
    def dauer_s(self) -> float:
        return self.bis_s - self.von_s


class Messwerte(BaseModel):
    eigenschaften: Eigenschaften
    pausen: list[Pause] | None = None
    wellenform: list[int] | None = None
    pegel: Pegelverlauf | None = None
    laut: LauteSpanne | None = None


class Datei(BaseModel):
    """Eine erzeugte Datei; `name` gilt nur beim Tondienst (zum Abholen)."""

    name: str = ""
    groesse: int
    dauer_s: float


class Aufbereitet(BaseModel):
    messwerte: Messwerte
    ausgaben: list[Datei]


class Stueck(BaseModel):
    datei: int = Field(ge=0, description="Nummer der mitgegebenen Datei")
    von_s: float | None = Field(None, ge=0)
    bis_s: float | None = Field(None, ge=0)


class Blenden(BaseModel):
    rate: int = Field(24000, ge=8000, le=192000)
    stuecke: list[Stueck] = Field(min_length=1, max_length=500)
    blende_ms: float = Field(30, ge=0, le=1000)
    format: Tonformat
    endung: str = Field(".wav", pattern=ENDUNG)


class Lage(BaseModel):
    datei: int = Field(ge=0)
    beginn_s: float = Field(ge=0)
    stauchung: float = Field(1.0, ge=0.5, le=4.0, description="über 1 schneller (kürzer), gleiche Tonhöhe")


class Legen(BaseModel):
    rate: int = Field(24000, ge=8000, le=192000)
    lagen: list[Lage] = Field(min_length=1, max_length=20000)
    rand_ms: float = Field(5, ge=0, le=1000)
    mindestens_s: float = Field(0, ge=0)
    spitze: float = Field(0.98, gt=0, le=1)
    format: Tonformat
    endung: str = Field(".wav", pattern=ENDUNG)
    wellenform: int | None = Field(None, ge=10, le=10000)


class Gelegt(BaseModel):
    datei: Datei
    spitze_vorher: float
    wellenform: list[int] | None = None


class Tonarbeit(abc.ABC):
    """Die drei Arbeitsschritte; `titel` und `prioritaet` gelten für den Weg über die Leitstelle."""

    @abc.abstractmethod
    async def aufbereiten(self, quelle: Path, auftrag: Aufbereiten, ziele: Sequence[Path], *, titel: str = "",
                          prioritaet: Prioritaet | None = None) -> Aufbereitet:
        """Je Ausgabe ein Ziel (gleiche Reihenfolge)."""

    @abc.abstractmethod
    async def blenden(self, dateien: Sequence[Path], auftrag: Blenden, ziel: Path, *, titel: str = "",
                      prioritaet: Prioritaet | None = None) -> Datei: ...

    @abc.abstractmethod
    async def legen(self, dateien: Sequence[Path], auftrag: Legen, ziel: Path, *, titel: str = "",
                    prioritaet: Prioritaet | None = None) -> Gelegt: ...

    # --- häufige Fälle ---------------------------------------------------------------------------------------------

    async def eigenschaften(self, datei: Path, *, titel: str = "", prioritaet: Prioritaet | None = None) -> Eigenschaften:
        return (await self.aufbereiten(datei, Aufbereiten(), [], titel=titel, prioritaet=prioritaet)).messwerte.eigenschaften

    async def dauer(self, datei: Path, *, titel: str = "", prioritaet: Prioritaet | None = None) -> float:
        e = await self.eigenschaften(datei, titel=titel, prioritaet=prioritaet)
        if e.dauer_s <= 0:
            raise TonFehler("Dauer nicht lesbar (keine Ton- oder Videodatei?)")
        return e.dauer_s

    async def wandeln(self, quelle: Path, ziel: Path, format: Tonformat, *, beginn: float | None = None,
                      ende: float | None = None, titel: str = "", prioritaet: Prioritaet | None = None) -> Path:
        ausgabe = Ausgabe(format=format, endung=ziel.suffix.lower() or ".wav", beginn_s=beginn, ende_s=ende)
        await self.aufbereiten(quelle, Aufbereiten(ausgaben=[ausgabe]), [ziel], titel=titel, prioritaet=prioritaet)
        return ziel


class TonHier(Tonarbeit):
    """Rechnet selbst, mit ffmpeg und numpy."""

    def __init__(self, ton: Ton | None = None) -> None:
        self.ton = ton or Ton()

    async def aufbereiten(self, quelle: Path, auftrag: Aufbereiten, ziele: Sequence[Path], *, titel: str = "",
                          prioritaet: Prioritaet | None = None) -> Aufbereitet:
        if len(ziele) != len(auftrag.ausgaben):
            raise ValueError(f"{len(auftrag.ausgaben)} Ausgaben, aber {len(ziele)} Ziele")
        m = auftrag.messen
        werte = Messwerte(eigenschaften=await self.ton.eigenschaften(quelle))
        if m.pausen:
            werte.pausen = await self.ton.pausen(quelle, schwelle_db=m.pausen.schwelle_db, mindestens_s=m.pausen.mindestens_s)
        if m.wellenform:
            werte.wellenform = await self.ton.wellenform(quelle, m.wellenform)
        if m.pegel_ms:
            werte.pegel = await self._pegel(quelle, m.pegel_ms)
        if m.laut:
            werte.laut = await self._laut(quelle, m.laut)
        return Aufbereitet(messwerte=werte, ausgaben=[await self._ausgabe(quelle, a, z) for a, z in zip(auftrag.ausgaben, ziele)])

    async def _pegel(self, quelle: Path, rahmen_ms: int) -> Pegelverlauf:
        rate = 24000
        r = rechnen.Pegelrechner(rate, rahmen_ms)
        async for block in self.ton.bloecke(quelle, rate):
            r.fuettern(block)
        return Pegelverlauf(rahmen_ms=rahmen_ms, rms=[round(v, 6) for v in r.rms], spitze=[round(v, 5) for v in r.spitzen])

    async def _laut(self, quelle: Path, wahl: LautWahl) -> LauteSpanne:
        werte = await self.ton.lesen(quelle, wahl.rate)
        von, bis = rechnen.laute_spanne(werte, wahl.rate, wahl.schwelle_db, wahl.rand_ms)
        return LauteSpanne(von_s=von / wahl.rate, bis_s=bis / wahl.rate, spitze=round(rechnen.spitze(werte[von:bis]), 6))

    async def _ausgabe(self, quelle: Path, a: Ausgabe, ziel: Path) -> Datei:
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if not a.bearbeitet:
            await self.ton.wandeln(quelle, ziel, a.format, beginn=a.beginn_s, ende=a.ende_s)
            return Datei(groesse=ziel.stat().st_size, dauer_s=round((await self.ton.eigenschaften(ziel)).dauer_s, 4))
        rate = a.format.rate
        werte = await self.ton.lesen(quelle, rate, beginn=a.beginn_s, ende=a.ende_s)
        if a.spitze is not None:
            werte = rechnen.begrenzen(werte, a.spitze)
        werte = rechnen.raender(werte, rate, a.blende_ms)
        werte = np.concatenate([np.zeros(int(rate * a.vorlauf_s), np.float32), werte,
                                np.zeros(int(rate * a.nachlauf_s), np.float32)])
        await self.ton.schreiben(werte, rate, ziel, a.format)
        return Datei(groesse=ziel.stat().st_size, dauer_s=round(werte.size / rate, 4))

    async def blenden(self, dateien: Sequence[Path], auftrag: Blenden, ziel: Path, *, titel: str = "",
                      prioritaet: Prioritaet | None = None) -> Datei:
        rate = auftrag.rate
        gelesen: dict[int, np.ndarray] = {}
        teile = []
        for s in auftrag.stuecke:
            if s.datei >= len(dateien):
                raise ValueError(f"Stück nennt Datei {s.datei}, mitgegeben sind {len(dateien)}")
            if s.datei not in gelesen:
                gelesen[s.datei] = await self.ton.lesen(dateien[s.datei], rate)
            w = gelesen[s.datei]
            von = round((s.von_s or 0.0) * rate)
            bis = w.size if s.bis_s is None else round(s.bis_s * rate)
            teile.append(w[von:bis])
        werte = rechnen.blenden(teile, rate, auftrag.blende_ms)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        await self.ton.schreiben(werte, rate, ziel, auftrag.format)
        return Datei(groesse=ziel.stat().st_size, dauer_s=round(werte.size / rate, 4))

    async def legen(self, dateien: Sequence[Path], auftrag: Legen, ziel: Path, *, titel: str = "",
                    prioritaet: Prioritaet | None = None) -> Gelegt:
        rate = auftrag.rate
        stuecke = []
        for lage in auftrag.lagen:
            if lage.datei >= len(dateien):
                raise ValueError(f"Lage nennt Datei {lage.datei}, mitgegeben sind {len(dateien)}")
            w = await self.ton.lesen(dateien[lage.datei], rate)
            if abs(lage.stauchung - 1.0) > 1e-4:
                w = await self.ton.stauchen(w, rate, lage.stauchung)
            stuecke.append((w, lage.beginn_s))
        werte = rechnen.legen(stuecke, rate, mindestens_s=auftrag.mindestens_s, rand_ms=auftrag.rand_ms)
        vorher = rechnen.spitze(werte)
        werte = rechnen.begrenzen(werte, auftrag.spitze)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        await self.ton.schreiben(werte, rate, ziel, auftrag.format)
        welle = await self.ton.wellenform(ziel, auftrag.wellenform) if auftrag.wellenform else None
        return Gelegt(datei=Datei(groesse=ziel.stat().st_size, dauer_s=round(werte.size / rate, 4)),
                      spitze_vorher=round(vorher, 6), wellenform=welle)


class GeduldigeTonarbeit(Tonarbeit):
    """Hülle um eine Tonarbeit: jeder Schritt wird wiederholt, solange die Leitstelle sagt, dass es gerade nicht geht
    (`appkern.leitstelle.geduldig`). Für Aufträge: `melden` zeigt, worauf gewartet wird, `pruefen` lässt abbrechen."""

    def __init__(self, innen: Tonarbeit, *, melden: Callable[[str], Awaitable[None]] | None = None,
                 pruefen: Callable[[], Awaitable[None]] | None = None, geduld_s: float | None = None) -> None:
        self.innen = innen
        self._weiter = {"melden": melden, "pruefen": pruefen, **({"geduld_s": geduld_s} if geduld_s is not None else {})}

    async def aufbereiten(self, quelle: Path, auftrag: Aufbereiten, ziele: Sequence[Path], *, titel: str = "",
                          prioritaet: Prioritaet | None = None) -> Aufbereitet:
        return await geduldig(lambda: self.innen.aufbereiten(quelle, auftrag, ziele, titel=titel, prioritaet=prioritaet),
                              was="Tondienst", **self._weiter)

    async def blenden(self, dateien: Sequence[Path], auftrag: Blenden, ziel: Path, *, titel: str = "",
                      prioritaet: Prioritaet | None = None) -> Datei:
        return await geduldig(lambda: self.innen.blenden(dateien, auftrag, ziel, titel=titel, prioritaet=prioritaet),
                              was="Tondienst", **self._weiter)

    async def legen(self, dateien: Sequence[Path], auftrag: Legen, ziel: Path, *, titel: str = "",
                    prioritaet: Prioritaet | None = None) -> Gelegt:
        return await geduldig(lambda: self.innen.legen(dateien, auftrag, ziel, titel=titel, prioritaet=prioritaet),
                              was="Tondienst", **self._weiter)
