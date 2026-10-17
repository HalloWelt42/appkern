"""Einstellungen, die jede App hat. Die App erbt davon und ergänzt ihre eigenen Felder."""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr

VERBINDUNGEN = {"gruppe": "Verbindungen"}
ZUGANG = {"gruppe": "Zugang"}


class Grundeinstellungen(BaseModel):
    kellerwolke_adresse: str = Field("", title="Kellerwolke", json_schema_extra=VERBINDUNGEN,
                                     description="Adresse der Kellerwolke; die Dateien der App liegen in ihrem Zweig Apps/<App>.")
    kellerwolke_schluessel: SecretStr = Field(SecretStr(""), title="App-Schlüssel der Kellerwolke", json_schema_extra=VERBINDUNGEN,
                                              description="In der Kellerwolke unter Einstellungen, Zugänge ausgestellt. Dem Konto des "
                                                          "Schlüssels gehört die App.")
    leitstelle_adresse: str = Field("", title="Leitstelle", json_schema_extra=VERBINDUNGEN,
                                    description="Adresse der Leitstelle, über die alle KI-Aufträge gehen.")
    leitstelle_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel der Leitstelle", json_schema_extra=VERBINDUNGEN,
                                             description="In der Leitstelle unter Anwendungen erzeugt.")
    ca_datei: str = Field("", title="Zertifikatsstelle", json_schema_extra=VERBINDUNGEN,
                          description="Pfad zur Datei der Hausstelle (rootCA.pem), wenn Kellerwolke oder Leitstelle über "
                                      "HTTPS mit eigenem Zertifikat laufen. Leer: die üblichen Stellen.")
    weitere_konten: list[str] = Field(default_factory=list, title="Weitere Konten", json_schema_extra=ZUGANG,
                                      description="Wer außer dem Konto des App-Schlüssels diese App nutzen darf "
                                                  "(Namen von Konten der Kellerwolke).")
