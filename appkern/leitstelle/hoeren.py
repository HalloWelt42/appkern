"""Hören über die Leitstelle (Dienst wie `klangwerk-hoeren`, Weg `/stt`): Text einer Aufnahme mit Segmenten und Wörtern
samt Zeiten. Gemeinsam für alle Apps, die etwas heraushören (Transkription, Referenztext und Ausspracheprüfung der
Vertonung); die App bildet das Ergebnis auf ihr eigenes Modell ab."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .zugang import Leitstelle

INHALTSTYPEN = {".wav": "audio/wav", ".flac": "audio/flac", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".ogg": "audio/ogg"}


@dataclass(frozen=True)
class GehoertesWort:
    wort: str
    start: float
    ende: float


@dataclass(frozen=True)
class GehoertesSegment:
    start: float
    ende: float
    text: str
    woerter: list[GehoertesWort] = field(default_factory=list)


@dataclass(frozen=True)
class Gehoert:
    segmente: list[GehoertesSegment]
    sprache: str | None = None
    modell: str | None = None

    @property
    def text(self) -> str:
        return " ".join(s.text for s in self.segmente).strip()


def segmente_aus(roh: list[dict], versatz: float = 0.0) -> list[GehoertesSegment]:
    """Segmente des Hördienstes (start, end, text, words mit word, start, end), verschoben um `versatz`; leere fallen weg."""
    aus = []
    for s in roh:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        woerter = [GehoertesWort(wort=w["word"].strip(), start=round(float(w["start"]) + versatz, 3),
                                 ende=round(float(w["end"]) + versatz, 3))
                   for w in s.get("words") or [] if (w.get("word") or "").strip()]
        start, ende = round(float(s["start"]) + versatz, 3), round(float(s["end"]) + versatz, 3)
        aus.append(GehoertesSegment(start=start, ende=max(ende, start), text=text, woerter=woerter))
    return aus


async def hoeren(leitstelle: Leitstelle, dienst: str, datei: Path, sprache: str, *, versatz: float = 0.0, titel: str = "",
                 prioritaet=None) -> Gehoert:
    """`sprache` als Kürzel (de, en) oder "auto"; die Datei wird gestreamt, nie am Stück gelesen."""
    with open(datei, "rb") as inhalt:
        antwort = await leitstelle.dienst(dienst).json(
            "POST", "/stt", titel=titel, prioritaet=prioritaet, data={"language": sprache, "diarize": "false"},
            files={"file": (datei.name, inhalt, INHALTSTYPEN.get(datei.suffix.lower(), "application/octet-stream"))})
    return Gehoert(segmente=segmente_aus(antwort.get("segments") or [], versatz), sprache=antwort.get("language"),
                   modell=antwort.get("model"))
