"""MCP für jede App (Model Context Protocol über HTTP, zustandslos): `POST /api/v1/mcp` nimmt eine JSON-RPC-Nachricht und
antwortet mit JSON. Unterstützt `initialize`, `ping`, `tools/list` und `tools/call`; Benachrichtigungen (ohne `id`)
bekommen 202. Eine App meldet nur ihre Werkzeuge an: Name, Beschreibung (für die KI: was es kann und wann es passt),
Eingabemodell und eine Arbeit, die Text liefert (Text, weil Modelle ihn am besten weiterverwenden). Eine falsche Eingabe
ist ein Ergebnis mit `isError` (die KI kann sie verbessern), ein unbekanntes Werkzeug oder eine unbekannte Methode ein
JSON-RPC-Fehler. Angemeldet wie jeder Weg der App: Sitzung oder App-Schlüssel. Herkunft: Nachschlag (WIKI), hierher
gezogen für alle Apps (Softwareregal GSP-21)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

#: die Fassung des Protokolls, die dieser Weg spricht; fragt ein Client nach einer anderen, antwortet er mit dieser
PROTOKOLL = "2025-06-18"


@dataclass(frozen=True)
class Werkzeug:
    """Ein Werkzeug für die KI."""
    name: str
    beschreibung: str
    eingabe: type[BaseModel]
    arbeit: Callable[[Any], Awaitable[str]]


def _fehler(nr: Any, code: int, text: str) -> dict:
    return {"jsonrpc": "2.0", "id": nr, "error": {"code": code, "message": text}}


def _ergebnis(nr: Any, text: str, fehler: bool = False) -> dict:
    return {"jsonrpc": "2.0", "id": nr, "result": {"content": [{"type": "text", "text": text}], "isError": fehler}}


def router(geruest, werkzeuge: Sequence[Werkzeug], *, hinweis: str = "", zusammenfassung: str = "") -> APIRouter:
    """Der MCP-Weg einer App; `hinweis` sagt der KI, in welcher Reihenfolge die Werkzeuge passen."""
    r = APIRouter(prefix="/api/v1", tags=["mcp"], dependencies=[geruest.pflicht])
    nach_name = {w.name: w for w in werkzeuge}

    @r.post("/mcp", summary=zusammenfassung or f"MCP-Werkzeuge für KI ({geruest.name})")
    async def mcp(request: Request) -> Response:
        """Model Context Protocol über HTTP: eine KI fragt, welche Werkzeuge es gibt (`tools/list`), und ruft sie
        (`tools/call`). Eine JSON-RPC-Nachricht je Anfrage."""
        try:
            n = await request.json()
        except ValueError:
            return JSONResponse(_fehler(None, -32700, "Kein gültiges JSON"))
        if not isinstance(n, dict) or n.get("jsonrpc") != "2.0" or "method" not in n:
            return JSONResponse(_fehler(n.get("id") if isinstance(n, dict) else None, -32600, "Keine JSON-RPC-Nachricht"))
        if "id" not in n:
            return Response(status_code=202)                     # Benachrichtigung (etwa notifications/initialized)
        nr, methode, p = n["id"], n["method"], n.get("params") or {}
        if methode == "initialize":
            return JSONResponse({"jsonrpc": "2.0", "id": nr, "result": {
                "protocolVersion": PROTOKOLL, "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": geruest.kennung, "title": geruest.name, "version": geruest.fassung},
                "instructions": hinweis}})
        if methode == "ping":
            return JSONResponse({"jsonrpc": "2.0", "id": nr, "result": {}})
        if methode == "tools/list":
            return JSONResponse({"jsonrpc": "2.0", "id": nr, "result": {"tools": [
                {"name": w.name, "description": w.beschreibung, "inputSchema": w.eingabe.model_json_schema()}
                for w in werkzeuge]}})
        if methode == "tools/call":
            w = nach_name.get(p.get("name", ""))
            if w is None:
                return JSONResponse(_fehler(nr, -32602, f"Unbekanntes Werkzeug: {p.get('name', '')}"))
            try:
                eingabe = w.eingabe.model_validate(p.get("arguments") or {})
            except ValidationError as f:
                return JSONResponse(_ergebnis(nr, "Eingabe ungültig: " + "; ".join(
                    f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in f.errors()), fehler=True))
            return JSONResponse(_ergebnis(nr, await w.arbeit(eingabe)))
        return JSONResponse(_fehler(nr, -32601, f"Unbekannte Methode: {methode}"))

    return r
