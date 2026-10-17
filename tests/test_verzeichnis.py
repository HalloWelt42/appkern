"""App-Verzeichnis: eingetragen vor Stellwerk, Teil backend mit Port, Merken, Stellwerk weg."""

import httpx
import pytest

from appkern import verzeichnis as v
from appkern.verzeichnis import AppUnbekannt, Verzeichnis

STAND = {"apps": [
    {"kennung": "transkription", "name": "Transkription",
     "teile": [{"kennung": "backend", "port": 8601, "zustand": "laeuft"}, {"kennung": "oberflaeche", "port": 5601}]},
    {"kennung": "stimmenausgabe", "name": "Stimmenausgabe", "teile": [{"kennung": "backend", "port": 8611, "zustand": "aus"}]},
    {"kennung": "nur-docker", "name": "Nur Docker", "teile": [{"kennung": "db", "port": 5432}]},
]}


def verzeichnis(handler, **art) -> Verzeichnis:
    return Verzeichnis(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), **art)


async def test_stellwerk_und_eingetragen():
    abrufe = []

    def handler(request):
        abrufe.append(request.url.path)
        return httpx.Response(200, json=STAND)

    vz = verzeichnis(handler, eingetragen={"Stimmenausgabe": "http://studio:8611/"})
    assert await vz.adresse("transkription") == "http://127.0.0.1:8601"
    assert await vz.adresse("Stimmenausgabe") == "http://studio:8611"                    # eingetragen geht vor
    alle = {e.kennung: e for e in await vz.alle()}
    assert set(alle) == {"transkription", "stimmenausgabe"}                               # ohne Teil backend: nicht dabei
    assert alle["transkription"].laeuft is True and alle["stimmenausgabe"].quelle == "eingetragen"
    assert abrufe == ["/api/stand"]                                                       # gemerkt
    with pytest.raises(AppUnbekannt):
        await vz.adresse("nur-docker")


async def test_stellwerk_weg_und_merken(monkeypatch):
    zustand = {"weg": False}

    def handler(request):
        if zustand["weg"]:
            raise httpx.ConnectError("weg")
        return httpx.Response(200, json=STAND)

    vz = verzeichnis(handler)
    assert await vz.adresse("transkription") == "http://127.0.0.1:8601"
    zustand["weg"] = True
    monkeypatch.setattr(v, "MERKEN_S", 0.0)
    assert await vz.adresse("transkription") == "http://127.0.0.1:8601"                  # letzter bekannter Stand
    leer = verzeichnis(handler)
    with pytest.raises(AppUnbekannt):
        await leer.adresse("transkription")
    ohne = Verzeichnis(stellwerk=None, eingetragen={"a": "http://x"})
    assert [e.kennung for e in await ohne.alle()] == ["a"]
