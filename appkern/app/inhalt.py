"""Inhalte aus der Kellerwolke an den Browser reichen: mit Bereichen (Range) zum Spulen im Spieler, als Download mit
Namen; wer etwas tut (für Notizen und Aufträge). Für jede App gleich."""

from __future__ import annotations

import re
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import Response, StreamingResponse

from appkern.anmeldung import Konto
from appkern.kellerwolke import Kellerwolke, Knoten

_BEREICH = re.compile(r"^bytes=(\d*)-(\d*)$")


def von(konto: Konto) -> str:
    """Für Notizen und Aufträge: das Konto, bei einer anderen App auch deren Name."""
    return f"{konto.name} über {konto.app}" if konto.app else konto.name


def herunterladen_kopf(dateiname: str) -> dict[str, str]:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(dateiname)}"}


async def inhalt_reichen(kw: Kellerwolke, knoten: Knoten, request: Request) -> Response:
    """Inhalt einer Datei durchreichen, mit Bereichen (Range) für Spulen im Spieler."""
    gesamt = knoten.groesse or 0
    typ = knoten.inhaltstyp or "application/octet-stream"
    kopf = {"Accept-Ranges": "bytes", "Cache-Control": "private, max-age=3600"}
    if knoten.etag:
        kopf["ETag"] = f'"{knoten.etag}"'
    m = _BEREICH.match(request.headers.get("range", "").strip())
    if m and gesamt and (m.group(1) or m.group(2)):
        if m.group(1):
            start = int(m.group(1))
            ende = min(int(m.group(2)) if m.group(2) else gesamt - 1, gesamt - 1)
        else:
            start, ende = max(0, gesamt - int(m.group(2))), gesamt - 1
        if start > ende or start >= gesamt:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{gesamt}"})
        kopf.update({"Content-Range": f"bytes {start}-{ende}/{gesamt}", "Content-Length": str(ende - start + 1)})
        return StreamingResponse(kw.lesen(knoten.id, start=start, ende=ende), status_code=206, media_type=typ,
                                 headers=kopf)
    kopf["Content-Length"] = str(gesamt)
    return StreamingResponse(kw.lesen(knoten.id), media_type=typ, headers=kopf)
