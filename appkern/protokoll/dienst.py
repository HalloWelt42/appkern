"""Protokoll einer App: was geschah, nachvollziehbar und durchsuchbar (Aufträge, Dateien, Änderungen).

Ein Eintrag hat Zeit, Ereignis (Punkt-Schreibweise, etwa `auftrag.fertig`, `datei.geloescht`), Stufe, Bezug (Art,
Kennung, Name) und Text. Eintragen wirft nie: ein Protokoll darf die eigentliche Arbeit nicht kippen. Geheimnisse
gehören nicht hinein; die App schreibt Namen von Einstellungen, nie ihre Werte.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from appkern.datenbank import Datenbank

from .modelle import Eintrag, Seite, Stufe

logger = logging.getLogger("appkern.protokoll")

SCHEMA = [
    """
    CREATE TABLE protokoll (
        id         TEXT PRIMARY KEY,
        zeit       TEXT NOT NULL,
        ereignis   TEXT NOT NULL,
        stufe      TEXT NOT NULL CHECK (stufe IN ('info','warnung','fehler')),
        bezug_art  TEXT,
        bezug_id   TEXT,
        bezug_name TEXT,
        text       TEXT NOT NULL DEFAULT '',
        daten      TEXT
    );
    CREATE INDEX protokoll_zeit_idx ON protokoll (zeit);
    CREATE INDEX protokoll_bezug_idx ON protokoll (bezug_id);
    """,
]


class Protokoll:
    def __init__(self, db: Datenbank, *, aufbewahren_tage: int = 90) -> None:
        self.db = db
        self.aufbewahren_tage = aufbewahren_tage

    async def starten(self) -> None:
        await self.db.einrichten("protokoll", SCHEMA)

    async def eintragen(self, ereignis: str, text: str = "", *, stufe: Stufe = "info", bezug_art: str | None = None,
                        bezug_id: str | None = None, bezug_name: str | None = None,
                        daten: dict[str, Any] | None = None) -> None:
        try:
            await self.db.ausfuehren(
                "INSERT INTO protokoll (id, zeit, ereignis, stufe, bezug_art, bezug_id, bezug_name, text, daten) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), ereignis, stufe, bezug_art, bezug_id,
                 bezug_name, text, json.dumps(daten, ensure_ascii=False) if daten else None))
        except Exception:  # noqa: BLE001 - siehe oben: nie die Arbeit kippen
            logger.exception("Protokolleintrag %s ging nicht", ereignis)

    async def liste(self, *, ereignis: str | None = None, stufe: Stufe | None = None, bezug_id: str | None = None,
                    tag: str | None = None, ab: str | None = None, suche: str | None = None, grenze: int = 100,
                    versatz: int = 0) -> Seite:
        """Neueste zuerst, seitenweise. `ereignis` als Anfang (`auftrag.` trifft alle Auftragsereignisse), `tag` als
        JJJJ-MM-TT (UTC) für genau diesen Tag, `ab` für alles ab diesem Tag, `suche` in Name und Text."""
        bedingungen, werte = [], []
        if ab:
            bedingungen.append("substr(zeit, 1, 10) >= ?")
            werte.append(ab)
        if ereignis:
            bedingungen.append("ereignis LIKE ? ESCAPE '\\'")
            werte.append(_like(ereignis) + "%")
        if stufe:
            bedingungen.append("stufe=?")
            werte.append(stufe)
        if bezug_id:
            bedingungen.append("bezug_id=?")
            werte.append(bezug_id)
        if tag:
            bedingungen.append("substr(zeit, 1, 10)=?")
            werte.append(tag)
        if suche:
            bedingungen.append("(coalesce(bezug_name, '') LIKE ? ESCAPE '\\' OR text LIKE ? ESCAPE '\\')")
            werte += [f"%{_like(suche)}%"] * 2
        wo = f"WHERE {' AND '.join(bedingungen)}" if bedingungen else ""
        gesamt = (await self.db.zeile(f"SELECT count(*) AS n FROM protokoll {wo}", werte))["n"]
        zeilen = await self.db.zeilen(f"SELECT * FROM protokoll {wo} ORDER BY zeit DESC, id LIMIT ? OFFSET ?",
                                      [*werte, max(1, min(grenze, 500)), max(0, versatz)])
        return Seite(eintraege=[Eintrag(**{**z, "daten": json.loads(z["daten"]) if z["daten"] else None}) for z in zeilen],
                     gesamt=gesamt)

    async def aufraeumen(self) -> int:
        grenze = (datetime.now(timezone.utc) - timedelta(days=self.aufbewahren_tage)).isoformat()
        return await self.db.ausfuehren("DELETE FROM protokoll WHERE zeit < ?", (grenze,))


def _like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
