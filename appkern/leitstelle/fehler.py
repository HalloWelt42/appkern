"""Fehler der Leitstelle als eigene Arten.

Die Leitstelle nennt in `error.code` ein Grundwort (ANBINDUNG.md Abschnitt 2.2); danach richtet sich die Art, nicht
nach der Statuszahl. Bei 429 und 503 sagt `nochmal_in` (Sekunden aus `Retry-After`), wann ein neuer Versuch Sinn hat.
Nichts hier wiederholt von selbst: abgelehnte oder gesperrte Aufträge gehen an den Menschen, nicht in eine Schleife.
"""

from __future__ import annotations


class LeitstellenFehler(Exception):
    """Grundart; `status` ist der HTTP-Status (0 ohne Antwort), `grund` das Grundwort, `meldung` der Wortlaut."""

    status = 0

    def __init__(self, meldung: str, status: int | None = None, grund: str = "", nochmal_in: int | None = None) -> None:
        super().__init__(meldung)
        self.meldung = meldung
        self.grund = grund
        self.nochmal_in = nochmal_in
        if status is not None:
            self.status = status


class NichtErreichbar(LeitstellenFehler):
    """Keine Verbindung zur Leitstelle."""


class SchluesselUngueltig(LeitstellenFehler):
    """Schlüssel falsch oder widerrufen (401): Hinweis zeigen, nicht wiederholen."""

    status = 401


class NichtErlaubt(LeitstellenFehler):
    """Fähigkeit, Zone oder Herkunft ist für diese App nicht freigegeben (403)."""

    status = 403


class KeinModell(LeitstellenFehler):
    """Modell oder Dienst unbekannt, oder kein Modell genannt und keine Kette eingerichtet (404)."""

    status = 404


class NichtGefunden(LeitstellenFehler):
    """Der Dienst kennt den Pfad nicht (404 aus dem Dienst selbst)."""

    status = 404


class Gesperrt(LeitstellenFehler):
    """Die App ist gesperrt oder ihr Kontingent ist erschöpft (429)."""

    status = 429


class Halt(LeitstellenFehler):
    """Der Hauptregler steht auf Halt oder Wartung (503)."""

    status = 503


class DienstWeg(LeitstellenFehler):
    """Kein Dienst da, nicht erreichbar oder das Modell passt gerade nicht in den Speicher (503)."""

    status = 503


class DienstFehler(LeitstellenFehler):
    """Der Dienst hat den Auftrag nicht geschafft (502 oder ein anderer Fehler des Dienstes)."""

    status = 502


class Abgebrochen(LeitstellenFehler):
    """Der Auftrag wurde in der Leitstelle abgebrochen, ohne dass ein Teilergebnis vorliegt."""

    status = 409


class Ungueltig(LeitstellenFehler):
    """Die Eingabe passt nicht (400 oder 422)."""

    status = 400


_NACH_GRUND: dict[str, type[LeitstellenFehler]] = {
    "unbekannter_schluessel": SchluesselUngueltig,
    "faehigkeit_nicht_erlaubt": NichtErlaubt, "zone_nicht_erlaubt": NichtErlaubt, "herkunft_nicht_erlaubt": NichtErlaubt,
    "kein_modell": KeinModell, "unbekannt": KeinModell,
    "gesperrt": Gesperrt, "kontingent": Gesperrt,
    "halt": Halt, "wartung": Halt,
    "kein_dienst": DienstWeg, "dienst_nicht_erreichbar": DienstWeg, "modell_passt_nicht": DienstWeg,
    "dienst_fehler": DienstFehler,
    "nutzer": Abgebrochen, "anwendung": Abgebrochen,
    "eingabe": Ungueltig,
}

# Antworten ohne Grundwort kommen vom Dienst selbst (Durchleitung unter /v1/dienste).
_NACH_STATUS: dict[int, type[LeitstellenFehler]] = {
    400: Ungueltig, 401: SchluesselUngueltig, 403: NichtErlaubt, 404: NichtGefunden, 422: Ungueltig,
    429: Gesperrt, 502: DienstFehler, 503: DienstWeg,
}


def fehler_aus(status: int, grund: str, meldung: str, nochmal_in: int | None = None) -> LeitstellenFehler:
    art = _NACH_GRUND.get(grund) or _NACH_STATUS.get(status) or (DienstFehler if status >= 500 else LeitstellenFehler)
    return art(meldung or f"Fehler {status}", status, grund, nochmal_in)
