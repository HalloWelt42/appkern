"""Einmaliger Code für die erste Einrichtung, wenn die Anfrage nicht vom Rechner der App selbst kommt (Lehre 34).

Hinter einem Vorschaltdienst oder in Docker sieht jede Anfrage fremd aus; die erste Einrichtung ginge dann nie im
Browser. Solange die App nicht eingerichtet ist, erzeugt sie bei jedem Start einen zufälligen Code und legt ihn in eine
Datei (Modus 0600), die nur jemand am Rechner lesen kann; Protokoll und Oberfläche nennen nur den Ort, nie den Code.
Nach der Einrichtung ist die Datei weg. Falsche Codes sperren nach wenigen Versuchen für eine Weile.

Ort der Datei: `<KENNUNG>_EINRICHTUNGSCODE_DATEI` (Vorgabe `<daten>/einrichtungscode`); wie ein Mensch ihn findet,
etwa der Pfad auf dem Rechner außerhalb des Containers: `<KENNUNG>_EINRICHTUNGSCODE_ORT` (Vorgabe: der Pfad selbst)."""

from __future__ import annotations

import hmac
import math
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

# Ohne leicht verwechselbare Zeichen (0/O, 1/I/L), damit man den Code abtippen kann
ZEICHEN = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
GRUPPEN, LAENGE = 4, 4


class Gesperrt(Exception):
    """Zu viele falsche Codes; `sekunden` bis zum nächsten Versuch."""

    def __init__(self, sekunden: int) -> None:
        super().__init__(f"gesperrt für {sekunden} s")
        self.sekunden = sekunden


def normal(code: str) -> str:
    """Wie eingegeben verglichen wird: ohne Leerzeichen und Striche, in Großbuchstaben."""
    return "".join(z for z in code.upper() if z.isalnum())


class Einrichtungscode:
    def __init__(self, datei: Path, ort: str = "", *, versuche: int = 5, sperre_s: float = 600,
                 uhr: Callable[[], float] = time.monotonic) -> None:
        self.datei = Path(datei)
        self.ort = ort or str(self.datei)
        self.versuche = versuche
        self.sperre_s = sperre_s
        self.uhr = uhr
        self._code: str | None = None
        self._fehler: list[float] = []

    @classmethod
    def aus_umgebung(cls, kennung: str, daten: Path) -> Einrichtungscode:
        praefix = kennung.upper()
        datei = os.environ.get(f"{praefix}_EINRICHTUNGSCODE_DATEI") or str(Path(daten) / "einrichtungscode")
        return cls(Path(datei), os.environ.get(f"{praefix}_EINRICHTUNGSCODE_ORT", ""))

    @property
    def aktiv(self) -> bool:
        return self._code is not None

    def erzeugen(self) -> None:
        """Neuer Code in die Datei (Modus 0600, ersetzt einen alten); der Code steht nirgends sonst."""
        code = "-".join("".join(secrets.choice(ZEICHEN) for _ in range(LAENGE)) for _ in range(GRUPPEN))
        self.datei.parent.mkdir(parents=True, exist_ok=True)
        neu = self.datei.with_name(self.datei.name + ".neu")
        neu.unlink(missing_ok=True)
        fd = os.open(neu, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code + "\n")
        os.replace(neu, self.datei)
        self._code = code
        self._fehler.clear()

    def pruefen(self, eingabe: str) -> bool:
        """Ob der Code stimmt; nach `versuche` falschen innerhalb der Sperrzeit `Gesperrt` bis zum Ablauf."""
        jetzt = self.uhr()
        self._fehler = [t for t in self._fehler if jetzt - t < self.sperre_s]
        if len(self._fehler) >= self.versuche:
            raise Gesperrt(math.ceil(self.sperre_s - (jetzt - self._fehler[0])))
        if self._code is not None and hmac.compare_digest(normal(eingabe), normal(self._code)):
            return True
        self._fehler.append(jetzt)
        return False

    def entfernen(self) -> None:
        """Nach der Einrichtung (oder wenn keine nötig ist): Datei weg, kein Code mehr gültig."""
        self._code = None
        self.datei.unlink(missing_ok=True)
