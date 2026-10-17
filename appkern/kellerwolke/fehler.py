"""Fehler der Kellerwolke als eigene Arten: eine App fängt genau den Fall, den sie behandeln kann (etwa einen
veralteten Stand neu lesen), statt Statuszahlen zu vergleichen."""

from __future__ import annotations


class KellerwolkeFehler(Exception):
    """Grundart; `status` ist der HTTP-Status (0 ohne Antwort), `meldung` der Text der Kellerwolke."""

    status = 0

    def __init__(self, meldung: str, status: int | None = None) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        if status is not None:
            self.status = status


class NichtErreichbar(KellerwolkeFehler):
    """Keine Verbindung oder der Speicher ist gerade abgehängt (503): später erneut versuchen, nichts ist verloren."""


class SchluesselUngueltig(KellerwolkeFehler):
    """Schlüssel fehlt, ist unbekannt oder gesperrt (401)."""

    status = 401


class KeinRecht(KellerwolkeFehler):
    """Der Ordner ist für diese App nur lesbar (403)."""

    status = 403


class NichtGefunden(KellerwolkeFehler):
    """Gibt es nicht oder ist für diese App unsichtbar (404) - die Kellerwolke unterscheidet das bewusst nicht."""

    status = 404


class Konflikt(KellerwolkeFehler):
    """Name vergeben oder Ordner statt Datei (409)."""

    status = 409


class StandVeraltet(KellerwolkeFehler):
    """Die Datei wurde inzwischen geändert (412): neu lesen, dann mit dem neuen Stand schreiben."""

    status = 412


class ZuGross(KellerwolkeFehler):
    """Über der Obergrenze der Kellerwolke (413)."""

    status = 413


class Ungueltig(KellerwolkeFehler):
    """Die Eingabe passt nicht (422), etwa ein unerlaubter Name."""

    status = 422


class Gesperrt(KellerwolkeFehler):
    """Eine andere App hält die Bearbeitungssperre (423); lesen geht weiter."""

    status = 423


class StandFehlt(KellerwolkeFehler):
    """Überschreiben nur mit dem zuletzt gelesenen Stand (428)."""

    status = 428


_NACH_STATUS: dict[int, type[KellerwolkeFehler]] = {
    401: SchluesselUngueltig, 403: KeinRecht, 404: NichtGefunden, 409: Konflikt, 412: StandVeraltet,
    413: ZuGross, 422: Ungueltig, 423: Gesperrt, 428: StandFehlt, 502: NichtErreichbar, 503: NichtErreichbar,
    504: NichtErreichbar,
}


def fehler_aus(status: int, meldung: str) -> KellerwolkeFehler:
    return _NACH_STATUS.get(status, KellerwolkeFehler)(meldung or f"Fehler {status}", status)
