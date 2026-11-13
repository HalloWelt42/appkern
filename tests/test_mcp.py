"""MCP-Baustein (appkern.mcp): Handschlag, Werkzeugliste mit Eingabeschema, Aufruf mit Text als Ergebnis, ungültige
Eingabe als Ergebnis mit isError, unbekanntes Werkzeug und unbekannte Methode als JSON-RPC-Fehler, Benachrichtigung 202,
kaputtes JSON. Die Anmeldung ist hier nachgestellt (pflicht lässt alles durch)."""

from types import SimpleNamespace

import httpx
from fastapi import Depends, FastAPI
from pydantic import BaseModel, Field

from appkern.mcp import PROTOKOLL, Werkzeug, router


class Eingabe(BaseModel):
    wort: str = Field(min_length=1, description="ein Wort")


async def echo(e: Eingabe) -> str:
    return f"gelesen: {e.wort}"


def app() -> FastAPI:
    geruest = SimpleNamespace(pflicht=Depends(lambda: None), kennung="probe", name="Probe", fassung="1.0.0")
    a = FastAPI()
    a.include_router(router(geruest, [Werkzeug("probe_echo", "gibt das Wort zurück", Eingabe, echo)], hinweis="erst echo"))
    return a


async def rufe(c, methode, params=None, nr=1):
    n = {"jsonrpc": "2.0", "method": methode, **({"params": params} if params is not None else {})}
    if nr is not None:
        n["id"] = nr
    return await c.post("/api/v1/mcp", json=n)


async def test_mcp_ablauf():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app()), base_url="http://t") as c:
        i = (await rufe(c, "initialize", {"protocolVersion": "2024-01-01"})).json()["result"]
        assert i["protocolVersion"] == PROTOKOLL and i["serverInfo"]["name"] == "probe" and i["instructions"] == "erst echo"
        assert (await rufe(c, "notifications/initialized", nr=None)).status_code == 202
        werkzeuge = (await rufe(c, "tools/list")).json()["result"]["tools"]
        assert werkzeuge[0]["name"] == "probe_echo" and werkzeuge[0]["inputSchema"]["properties"]["wort"]["description"] == "ein Wort"
        r = (await rufe(c, "tools/call", {"name": "probe_echo", "arguments": {"wort": "Regal"}})).json()["result"]
        assert r == {"content": [{"type": "text", "text": "gelesen: Regal"}], "isError": False}
        falsch = (await rufe(c, "tools/call", {"name": "probe_echo", "arguments": {"wort": ""}})).json()["result"]
        assert falsch["isError"] and "wort" in falsch["content"][0]["text"]
        assert (await rufe(c, "tools/call", {"name": "gibt_es_nicht"})).json()["error"]["code"] == -32602
        assert (await rufe(c, "resources/list")).json()["error"]["code"] == -32601
        assert (await rufe(c, "ping")).json()["result"] == {}
        assert (await c.post("/api/v1/mcp", content=b"{kaputt")).json()["error"]["code"] == -32700
