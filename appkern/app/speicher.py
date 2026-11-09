"""Speicherwache: wie viel Arbeitsspeicher die App belegt und wofür (HELF-209).

Ein Python-Dienst kann wachsen, ohne mehr Daten zu halten. Der Speicherverwalter von C (glibc) gibt Freigegebenes nur
vom Ende des Heaps an das System zurück; was mitten im Heap frei wird, bleibt dem Prozess (Verschnitt). Von außen sieht
das aus wie echte Daten, auch in der Auslagerung. Die Wache misst darum von innen, in festem Takt:

- Arbeitsspeicher und Auslagerung des Prozesses (`/proc/self/status`)
- den Heap des Speicherverwalters (`mallinfo2`): belegt, frei gehalten und große Blöcke in eigenen Seiten

Wächst der Prozess über die nächste Stufe, sagen Log und Protokoll (`app.speicher`), wie viel davon belegt und wie viel
nur frei gehalten ist. Unter der ersten Stufe bleibt sie still.

Hält der Heap viel frei (etwa nach einer großen Abfrage, deren Zeilen längst weg sind), gibt die Wache es an das System
zurück (`malloc_trim`, auch mitten im Heap) und sagt, wie viel (`app.speicher_zurueck`). Gemessen im Fundus: nach einer
Spitze von fast 11 GB beim Start hielt er 5,5 GB frei und nur 0,2 GB belegt.

Ohne `/proc` oder ohne glibc (Entwicklung am Mac) misst sie nichts und gibt nichts zurück."""

from __future__ import annotations

import asyncio
import ctypes
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..protokoll import Protokoll
from .begleiter import Begleiter

logger = logging.getLogger("appkern.app")

TAKT_S = 300.0                   # so oft sieht die Wache nach
AB = 1 << 30                     # erste Stufe, ab der sie meldet (Arbeitsspeicher und Auslagerung zusammen)
STUFE = 512 << 20                # danach meldet sie bei jedem weiteren Schritt dieser Größe
ZURUECK_AB = 256 << 20           # so viel frei Gehaltenes im Heap gibt sie an das System zurück
STATUS = Path("/proc/self/status")
GB = 1 << 30
MB = 1 << 20


@dataclass(frozen=True)
class Speicherbild:
    """Ein Blick auf den Speicher des Prozesses, alles in Bytes; die Werte des Heaps nur mit glibc."""

    arbeitsspeicher: int
    ausgelagert: int
    heap_belegt: int | None = None
    heap_frei: int | None = None          # freigegeben, aber dem Prozess geblieben (Verschnitt)
    eigene_seiten: int | None = None      # große Blöcke in eigenen Seiten, gehen beim Freigeben gleich zurück

    @property
    def gesamt(self) -> int:
        return self.arbeitsspeicher + self.ausgelagert

    def zeile(self) -> str:
        text = f"{_gb(self.gesamt)} ({_gb(self.arbeitsspeicher)} im Arbeitsspeicher, {_gb(self.ausgelagert)} ausgelagert)"
        if self.heap_belegt is None:
            return text
        return (f"{text}; im Heap belegt {_gb(self.heap_belegt)}, frei gehalten {_gb(self.heap_frei or 0)}, "
                f"große Blöcke {_gb(self.eigene_seiten or 0)}")

    def daten(self) -> dict[str, int | None]:
        """Für das Protokoll, in MB."""
        def mb(wert: int | None) -> int | None:
            return None if wert is None else round(wert / MB)
        return {"gesamt_mb": mb(self.gesamt), "arbeitsspeicher_mb": mb(self.arbeitsspeicher), "ausgelagert_mb": mb(self.ausgelagert),
                "heap_belegt_mb": mb(self.heap_belegt), "heap_frei_mb": mb(self.heap_frei), "eigene_seiten_mb": mb(self.eigene_seiten)}


def _gb(wert: int) -> str:
    return f"{wert / GB:.1f}".replace(".", ",") + " GB"


def status_lesen(text: str) -> tuple[int, int] | None:
    """Arbeitsspeicher (VmRSS) und Auslagerung (VmSwap) aus dem Inhalt von /proc/self/status, in Bytes."""
    werte: dict[str, int] = {}
    for zeile in text.splitlines():
        name, _, rest = zeile.partition(":")
        if name in ("VmRSS", "VmSwap") and rest.strip().endswith("kB"):
            werte[name] = int(rest.split()[0]) * 1024
    if "VmRSS" not in werte:
        return None
    return werte["VmRSS"], werte.get("VmSwap", 0)


class _Mallinfo2(ctypes.Structure):
    _fields_ = [(n, ctypes.c_size_t) for n in ("arena", "ordblks", "smblks", "hblks", "hblkhd", "usmblks", "fsmblks",
                                                "uordblks", "fordblks", "keepcost")]


def _mallinfo2() -> Callable[[], _Mallinfo2] | None:
    """`mallinfo2` der glibc im eigenen Prozess (ab glibc 2.33); sonst nichts."""
    try:
        f = ctypes.CDLL(None).mallinfo2
    except (OSError, AttributeError):
        return None
    f.restype, f.argtypes = _Mallinfo2, []
    return f


_MALLINFO2 = _mallinfo2()


def _malloc_trim() -> Callable[[int], int] | None:
    try:
        f = ctypes.CDLL(None).malloc_trim
    except (OSError, AttributeError):
        return None
    f.restype, f.argtypes = ctypes.c_int, [ctypes.c_size_t]
    return f


_MALLOC_TRIM = _malloc_trim()


def zurueckgeben() -> bool:
    """Gibt frei Gehaltenes des Heaps an das System zurück, auch mitten im Heap; ob etwas zurückging. Ohne glibc nichts.
    Läuft nicht in der Ereignisschleife (geht jeden Bereich des Heaps durch)."""
    return bool(_MALLOC_TRIM and _MALLOC_TRIM(0))


def messen(status: Path = STATUS) -> Speicherbild | None:
    """Ein Speicherbild des eigenen Prozesses; ohne /proc keins. Läuft nicht in der Ereignisschleife (`mallinfo2` geht
    jeden Bereich des Heaps durch)."""
    try:
        prozess = status_lesen(status.read_text(encoding="ascii", errors="replace"))
    except OSError:
        return None
    if prozess is None:
        return None
    if _MALLINFO2 is None:
        return Speicherbild(*prozess)
    m = _MALLINFO2()
    return Speicherbild(*prozess, heap_belegt=m.uordblks, heap_frei=m.fordblks, eigene_seiten=m.hblkhd)


class Speicherwache(Begleiter):
    def __init__(self, protokoll: Protokoll, *, takt_s: float = TAKT_S, ab: int = AB, stufe: int = STUFE,
                 zurueck_ab: int = ZURUECK_AB, messen: Callable[[], Speicherbild | None] = messen,
                 zurueckgeben: Callable[[], bool] = zurueckgeben) -> None:
        """`messen` und `zurueckgeben` nur für Tests."""
        self.protokoll = protokoll
        self.takt_s = takt_s
        self.ab = ab
        self.stufe = stufe
        self.zurueck_ab = zurueck_ab
        self.messen = messen
        self.zurueckgeben = zurueckgeben
        self._naechste = ab
        self._nach_rueckgabe: int | None = None     # Größe nach dem letzten Zurückgeben
        self._aufgabe: asyncio.Task[None] | None = None

    async def starten(self) -> None:
        self._aufgabe = asyncio.create_task(self._laufen(), name="speicherwache")

    async def stoppen(self) -> None:
        if self._aufgabe:
            self._aufgabe.cancel()
            await asyncio.gather(self._aufgabe, return_exceptions=True)
            self._aufgabe = None

    async def blick(self) -> Speicherbild | None:
        """Ein Blick: über der nächsten Stufe sagen Log und Protokoll, wie es um den Speicher steht; hält der Heap viel
        frei, geht es an das System zurück. Das Bild danach."""
        bild = await asyncio.to_thread(self.messen)
        if bild is None:
            return None
        if bild.gesamt >= self._naechste:
            self._naechste = self._stufe_ueber(bild)
            text = f"Speicher gewachsen auf {bild.zeile()}"
            logger.warning(text)
            await self.protokoll.eintragen("app.speicher", text, stufe="warnung", daten=bild.daten())
        if self._lohnt_zurueckgeben(bild):
            return await self._zurueckgeben(bild)
        return bild

    def _stufe_ueber(self, bild: Speicherbild) -> int:
        return max(self.ab, (bild.gesamt // self.stufe + 1) * self.stufe)

    def _lohnt_zurueckgeben(self, bild: Speicherbild) -> bool:
        """Viel frei Gehaltenes im Heap, und seit dem letzten Zurückgeben ist der Prozess um so viel gewachsen (der
        Speicherverwalter zählt Zurückgegebenes weiter als frei; neu belegt sein kann es nur, wenn der Prozess wuchs)."""
        if (bild.heap_frei or 0) < self.zurueck_ab:
            return False
        return self._nach_rueckgabe is None or bild.gesamt - self._nach_rueckgabe >= self.zurueck_ab

    async def _zurueckgeben(self, vorher: Speicherbild) -> Speicherbild:
        """Frei Gehaltenes an das System; Log und Protokoll sagen, wie viel ging. Danach zählen die Stufen von dort."""
        if not await asyncio.to_thread(self.zurueckgeben):
            return vorher
        nachher = await asyncio.to_thread(self.messen) or vorher
        self._nach_rueckgabe = nachher.gesamt
        weniger = vorher.gesamt - nachher.gesamt
        text = f"Speicher zurückgegeben: {_gb(max(weniger, 0))} weniger, jetzt {nachher.zeile()}"
        (logger.warning if weniger >= self.stufe else logger.info)(text)
        await self.protokoll.eintragen("app.speicher_zurueck", text,
                                       daten={**nachher.daten(), "zurueck_mb": round(weniger / MB)})
        self._naechste = self._stufe_ueber(nachher)
        return nachher

    async def _laufen(self) -> None:
        while True:
            try:
                await self.blick()
            except Exception:  # noqa: BLE001 - der nächste Blick versucht es wieder
                logger.exception("Speicherwache")
            await asyncio.sleep(self.takt_s)
