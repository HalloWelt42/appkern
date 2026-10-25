"""Was eine App mit dem Text eines Sprachmodells tut, bevor sie ihn zeigt oder speichert: eine feste Antwortform
verlangen (`antwortform`), die Antwort nachsichtig als JSON lesen (`json_lesen`) und Prosa auf gerade Zeichen bringen
(`gerade`, `saeubern`).

Modelle halten "nur gerade Zeichen" in der Anweisung nicht zuverlässig ein; die Säuberung ist die Garantie, der Hinweis
in der Anweisung bleibt trotzdem. Nur auf Text anwenden, den das Modell verfasst hat, nie auf wörtlich übernommene
Werte (Namen, Nummern). Umlaute bleiben unangetastet."""

from __future__ import annotations

import json
import re
from typing import Any

#: Gedankenstriche, Minus und Ziffernstrich werden zum Bindestrich, typografische Anführungszeichen zu geraden,
#: Auslassungspunkte zu drei Punkten, besondere Leerzeichen zu gewöhnlichen
_ERSATZ = str.maketrans({
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2013: "-", 0x2014: "-", 0x2015: "-", 0x2212: "-",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"', 0x00AB: '"', 0x00BB: '"',
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'", 0x2039: "'", 0x203A: "'",
    0x2026: "...", 0x00A0: " ", 0x202F: " ", 0x2009: " ", 0x200A: " ", 0x2007: " ", 0x200B: "",
})
_ZAUN = re.compile(r"^\s*```[a-zA-Z]*\s*\n?|\n?\s*```\s*$")


def gerade(text: str) -> str:
    """Nur gerade Zeichen: Bindestrich, gerade Anführungszeichen, drei Punkte, gewöhnliche Leerzeichen."""
    return text.translate(_ERSATZ)


def saeubern(wert: Any) -> Any:
    """`gerade` auf alle Texte in Listen und Wörterbüchern (die Schlüssel bleiben)."""
    if isinstance(wert, str):
        return gerade(wert)
    if isinstance(wert, list):
        return [saeubern(w) for w in wert]
    if isinstance(wert, dict):
        return {k: saeubern(w) for k, w in wert.items()}
    return wert


def antwortform(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    """`response_format` für `Leitstelle.chat`: die Antwort muss diesem JSON-Schema folgen. Längen, Stufen und Beispiele
    gehören trotzdem in die Anweisung; Beschreibungen im Schema lesen Modelle kaum."""
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}


def json_lesen(text: str) -> Any:
    """Die Antwort eines Modells als JSON, auch mit Codezaun drumherum oder Text davor und danach (dann gilt das
    äußerste Objekt). ValueError, wenn sich nichts lesen lässt."""
    roh = _ZAUN.sub("", text.strip())
    try:
        return json.loads(roh)
    except json.JSONDecodeError:
        pass
    anfang, ende = roh.find("{"), roh.rfind("}")
    if anfang < 0 or ende <= anfang:
        raise ValueError("Die Antwort enthält kein JSON")
    try:
        return json.loads(roh[anfang:ende + 1])
    except json.JSONDecodeError as f:
        raise ValueError(f"Die Antwort ist kein gültiges JSON: {f.msg}") from f
