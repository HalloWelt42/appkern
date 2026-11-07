"""Was die Fassade der Leitstelle liefert und was eine App ihr gibt, als Pydantic-Modelle.

Unbekannte Felder werden überlesen: eine neuere Leitstelle mit zusätzlichen Angaben bricht ältere Apps nicht.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Prioritaet = Literal["hintergrund", "normal", "hoch", "dringend"]
Rolle = Literal["system", "user", "assistant", "tool"]


class _Modell(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


def anzeige(name: str, aufgabe: str) -> str:
    """Modellname mit der Aufgabe dahinter, wie Leitstelle und Maschinenraum ihn zeigen."""
    return f"{name} · {aufgabe}" if aufgabe else name


class Messwerte(_Modell):
    """Wie sich ein Modell im Betrieb verhält, gemessen von der Leitstelle."""

    auftraege: int = 0
    rechenzeit_s: float | None = None
    erstes_stueck_s: float | None = None
    token_je_s: float | None = None
    ladezeit_s: float | None = None


class Steckbrief(_Modell):
    """Wofür ein Modell gemacht ist (Selbstauskunft, PROTOKOLL 4.8 der Leitstelle). Wörter bleiben Zeichenketten, damit
    eine neuere Leitstelle mit neuen Wörtern ältere Apps nicht bricht."""

    zweck: str = ""
    eignung: list[str] = Field(default_factory=list)       # denken, programmieren, lange_texte, schnell, gruendlich
    sprachen: list[str] = Field(default_factory=list)
    faehigkeiten: list[str] = Field(default_factory=list)
    kontext: int | None = None
    parameter_mrd: float | None = None
    quantisierung: str | None = None
    zone: str = "heim"                                     # extern heißt: Daten verlassen das Heimnetz
    anfragen_je_minute: int | None = None
    gemessen: Messwerte = Field(default_factory=Messwerte)
    herkunft: dict[str, str] = Field(default_factory=dict)


class Modell(_Modell):
    """Ein Modell oder Dienst, den die App nutzen darf (`GET /v1/models`)."""

    id: str
    name: str = ""                                         # der echte Modellname
    aufgabe: str = ""                                      # ab Leitstelle 0.30, bei Diensten des Maschinenraums: Spracherkennung, Sprachausgabe ...
    geladen: bool = False
    knoten: str | None = None
    knoten_name: str | None = None                         # ab Leitstelle 0.17
    extern: bool = False
    faehigkeiten: list[str] = Field(default_factory=list)
    gb: float | None = None
    steckbrief: Steckbrief | None = None                   # ab Leitstelle 0.15

    @property
    def anzeige(self) -> str:
        """Für Text, wo nichts klein gesetzt werden kann: "Whisper Large V3 · Spracherkennung"."""
        return anzeige(self.name or self.id, self.aufgabe)


class Werkzeugaufruf(_Modell):
    """Ein Werkzeug, das das Modell aufrufen will (OpenAI `tool_calls`). `argumente` bleibt der Text, wie das Modell
    ihn schrieb (JSON); prüfen und auslegen ist Sache der App."""

    id: str
    name: str
    argumente: str = ""

    def fuer_fassade(self) -> dict[str, Any]:
        return {"id": self.id, "type": "function", "function": {"name": self.name, "arguments": self.argumente or "{}"}}


class Nachricht(_Modell):
    """Eine Nachricht im Gespräch. `inhalt` ist Text oder, mit Bildern, eine Liste von Teilen im OpenAI-Format.
    `werkzeugaufrufe`: was das Modell in dieser Antwort aufrufen wollte (Rolle assistant); `aufruf_id`: zu welchem
    Aufruf ein Ergebnis gehört (Rolle tool)."""

    rolle: Rolle
    inhalt: str | list[dict[str, Any]]
    werkzeugaufrufe: list[Werkzeugaufruf] = Field(default_factory=list)
    aufruf_id: str | None = None

    @classmethod
    def system(cls, text: str) -> Nachricht:
        return cls(rolle="system", inhalt=text)

    @classmethod
    def nutzer(cls, inhalt: str | list[dict[str, Any]]) -> Nachricht:
        return cls(rolle="user", inhalt=inhalt)

    @classmethod
    def assistent(cls, text: str, werkzeugaufrufe: Sequence[Werkzeugaufruf] = ()) -> Nachricht:
        return cls(rolle="assistant", inhalt=text, werkzeugaufrufe=list(werkzeugaufrufe))

    @classmethod
    def ergebnis(cls, aufruf_id: str, text: str) -> Nachricht:
        """Das Ergebnis eines Werkzeugaufrufs für das Modell."""
        return cls(rolle="tool", inhalt=text, aufruf_id=aufruf_id)

    def fuer_fassade(self) -> dict[str, Any]:
        teil: dict[str, Any] = {"role": self.rolle, "content": self.inhalt}
        if self.werkzeugaufrufe:
            teil["tool_calls"] = [a.fuer_fassade() for a in self.werkzeugaufrufe]
        if self.aufruf_id is not None:
            teil["tool_call_id"] = self.aufruf_id
        return teil


class Verbrauch(_Modell):
    eingabe: int = 0
    ausgabe: int = 0
    gesamt: int = 0


class ChatAntwort(_Modell):
    """Eine fertige Antwort. `abgebrochen`: in der Leitstelle abgebrochen, `text` ist dann der bisherige Teil.
    `lage`: wie die Leitstelle die Lage beim Antworten sah (Kopf X-Leitstelle-Lage: ruhig, angespannt, engpass)."""

    text: str
    denken: str = ""                 # Denkfeld des Modells (reasoning_content), falls es eins liefert
    werkzeugaufrufe: list[Werkzeugaufruf] = Field(default_factory=list)
    ende: str | None = None
    abgebrochen: bool = False
    modell: str | None = None
    knoten: str | None = None
    auftrag: str | None = None
    lage: str | None = None
    verbrauch: Verbrauch | None = None


class Stueck(_Modell):
    """Ein Stück Text aus einem Strom."""

    art: Literal["stueck"] = "stueck"
    text: str


class Wartet(_Modell):
    """Der Auftrag wartet (alle paar Sekunden, solange er wartet); `grund` im Wortlaut der Leitstelle."""

    art: Literal["wartet"] = "wartet"
    grund: str
    sekunden: int | None = None


class Ende(_Modell):
    """Der Strom ist zu Ende. `abgebrochen`: in der Leitstelle abgebrochen; der Text bis hier ist das Teilergebnis.
    `werkzeugaufrufe`: die im Strom stückweise gekommenen Aufrufe, zusammengesetzt."""

    art: Literal["ende"] = "ende"
    ende: str | None = None
    abgebrochen: bool = False
    werkzeugaufrufe: list[Werkzeugaufruf] = Field(default_factory=list)
    modell: str | None = None
    auftrag: str | None = None
    lage: str | None = None
    verbrauch: Verbrauch | None = None


Ereignis = Stueck | Wartet | Ende


class Bild(_Modell):
    """Ein erzeugtes Bild (PNG), wie die Leitstelle es liefert."""

    daten: bytes
    beschreibung: str = ""                 # wie der Dienst die Beschreibung umgesetzt hat, falls er sie ändert


class AbgelegtesBild(_Modell):
    """Ein erzeugtes Bild in der Bildablage der Leitstelle (PROTOKOLL 6.3 der Leitstelle), das auf die Abholung durch
    ein Bildarchiv wartet: wer es erzeugt hat, mit welcher Beschreibung, welchem Modell und Startwert."""

    kennung: str
    anwendung: str                         # Name der App, die das Bild erzeugt hat
    auftrag: str
    familie: str                           # das Bildmodell
    beschreibung: str                      # der Prompt
    seed: int
    breite: int
    hoehe: int
    schritte: int | None = None
    nummer: int = 0                        # Stelle im Ergebnis, wenn ein Auftrag mehrere Bilder erzeugt hat
    bytes: int
    erzeugt_s: float                       # Unix-Zeit


class Bildablage(_Modell):
    """Die ältesten wartenden Bilder der Bildablage, dazu wie viele insgesamt warten."""

    bilder: list[AbgelegtesBild]
    wartend: int
    bytes: int


class Bilder(_Modell):
    """Ergebnis von `bilder_erzeugen`: die Bilder, der Startwert (gleiche Beschreibung und gleicher Startwert ergeben
    das gleiche Bild) und wer rechnete."""

    art: Literal["bilder"] = "bilder"
    bilder: list[Bild]
    startwert: int | None = None
    modell: str | None = None
    dauer_ms: int | None = None                            # Rechenzeit im Dienst, ohne Warten auf Start oder Platz
    groesse: str | None = None                             # wie gerechnet wurde ("BxH")
    schritte: int | None = None                            # None: nach Vorgabe des Dienstes, ohne dass die Leitstelle sie kennt
    auftrag: str | None = None


class Rechnet(_Modell):
    """Der Dienst rechnet (Bilder: alle paar Sekunden, solange er rechnet); `seit_s` wie die Leitstelle es meldet."""

    art: Literal["rechnet"] = "rechnet"
    seit_s: int


Bildereignis = Wartet | Rechnet | Bilder


class BildGroessen(_Modell):
    """Welche Größen ein Bildmodell annimmt: Raster, Kanten, Pixel, Vorgabe und empfohlene Größen ("BxH")."""

    raster: int = 16
    kante_min: int | None = None
    kante_max: int | None = None
    pixel_min: int | None = None
    pixel_max: int | None = None
    vorgabe: str = "1024x1024"
    empfohlen: list[str] = Field(default_factory=list)


class BildSchritte(_Modell):
    vorgabe: int | None = None
    kleinste: int = 1
    groesste: int | None = None


class Aufgabenbeispiel(_Modell):
    """Was ein Bildmodell an einem festen Motiv macht (Portfolio des Bildwerks, ATL-45 des Ateliers): Vorher und Nachher
    als kleine Bilder (data-URL), dazu die Dauer im Dienst beim Rechnen; zum Vergleichen der Modelle bei der Wahl."""

    motiv: str = ""
    vorher: str
    nachher: str
    dauer_s: float | None = None


class Aufgabenvorlage(_Modell):
    """Wie ein Bildmodell eine Aufgabe (`anweisen`, `entfernen`, `fuellen`, `erweitern`) als Anweisung bekommt (Steckbrief
    des Bildwerks, Leitstelle 0.34.3): `anweisung` mit dem Platzhalter `{wunsch}` für die Worte des Nutzers, `ohne_wunsch`
    für einen leeren Wunsch (fehlt sie, braucht die Aufgabe einen), `sprache`, in die der Wunsch übersetzt wird, und die
    `signalfarbe` (RGB), in der die betroffene Fläche deckend in der Vorlage steht. Zusammensetzen tut die App
    (`anweisung_aus`)."""

    anweisung: str
    ohne_wunsch: str | None = None
    sprache: str
    signalfarbe: tuple[int, int, int] | None = None
    beispiel: Aufgabenbeispiel | None = None               # sobald die Leitstelle es durchreicht (LS-25)

    def anweisung_aus(self, wunsch: str) -> str:
        """Die Anweisung an das Modell mit dem (schon übersetzten) Wunsch; ValueError, wenn die Aufgabe einen Wunsch
        braucht und keiner da ist."""
        wunsch = wunsch.strip()
        if not wunsch:
            if self.ohne_wunsch:
                return self.ohne_wunsch
            if WUNSCH in self.anweisung:
                raise ValueError("Diese Aufgabe braucht einen Wunsch")
            return self.anweisung
        return self.anweisung.replace(WUNSCH, wunsch)

    @property
    def nimmt_wunsch(self) -> bool:
        return WUNSCH in self.anweisung


WUNSCH = "{wunsch}"


class Bildsteckbrief(_Modell):
    """Was ein Bilddienst annimmt (PROTOKOLL 4.8 der Leitstelle), sobald er einmal lief. Was der Dienst nicht nennt, kommt
    als null: Größen (dann gelten die Vorgabegrenzen der Leitstelle), Schritte (gehen ungeprüft an den Dienst), Anzahl,
    Lizenz und Lizenzhinweis."""

    modell: str = ""
    name: str = ""
    kann_bearbeiten: bool = False
    vorlagen_max: int | None = None                        # Bildvorlagen je Anfrage, wenn es bearbeiten kann (Leitstelle 0.32)
    groessen: BildGroessen | None = None
    schritte: BildSchritte | None = None
    anzahl_max: int | None = None
    beschreibung_max_token: int | None = None
    lizenz: str | None = None
    lizenz_hinweis: str | None = None                      # was die Lizenz für die Nutzung der Bilder heißt; die Leitstelle schickt null, wenn keiner da ist
    parameter_mrd: float | None = None
    aufgaben: dict[str, Aufgabenvorlage] = Field(default_factory=dict)   # je Aufgabe die Anweisungsvorlage des Modells (Leitstelle 0.34.3)


class DienstEintrag(_Modell):
    """Ein Dienst im Maschinenraum (`GET /v1/dienste`), den die App nutzen darf. `zustand`: bereit, startet, aus,
    schlaeft, nicht_erreichbar (Wörter bleiben Zeichenketten)."""

    kennung: str
    name: str = ""                                         # der echte Modellname; ohne Modell die Aufgabe
    aufgabe: str = ""                                      # ab Leitstelle 0.30; leer, wenn der Name sie schon nennt
    zweck: str = ""
    faehigkeiten: list[str] = Field(default_factory=list)
    zustand: str = "aus"
    rechner: list[str] = Field(default_factory=list)
    bild: Bildsteckbrief | None = None

    @property
    def anzeige(self) -> str:
        return anzeige(self.name or self.kennung, self.aufgabe)


class Einbettungen(_Modell):
    vektoren: list[list[float]]
    modell: str | None = None
    lage: str | None = None          # Kopf X-Leitstelle-Lage; Stapelarbeit hält sich danach (ANBINDUNG Abschnitt 4)
    verbrauch: Verbrauch | None = None
