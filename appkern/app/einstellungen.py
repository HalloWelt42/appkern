"""Einstellungen, die jede App hat. Die App erbt davon und ergänzt ihre eigenen Felder."""

from __future__ import annotations

from pydantic import BaseModel, Field, SecretStr

from appkern.sicherung import VORGABE

VERBINDUNGEN = {"gruppe": "Verbindungen"}
ZUGANG = {"gruppe": "Zugang"}
SICHERUNG = {"gruppe": "Sicherung"}


class Grundeinstellungen(BaseModel):
    kellerwolke_adresse: str = Field("", title="Kellerwolke", json_schema_extra=VERBINDUNGEN,
                                     description="Adresse der Kellerwolke; die Dateien der App liegen dort in ihrem eigenen Zweig unter Apps.")
    kellerwolke_schluessel: SecretStr = Field(SecretStr(""), title="App-Schlüssel der Kellerwolke", json_schema_extra=VERBINDUNGEN,
                                              description="In der Kellerwolke unter Einstellungen, Zugänge ausgestellt. Dem Konto des "
                                                          "Schlüssels gehört die App.")
    leitstelle_adresse: str = Field("", title="Leitstelle", json_schema_extra=VERBINDUNGEN,
                                    description="Adresse der Leitstelle, über die alle KI-Aufträge gehen.")
    leitstelle_schluessel: SecretStr = Field(SecretStr(""), title="Schlüssel der Leitstelle", json_schema_extra=VERBINDUNGEN,
                                             description="In der Leitstelle unter Anwendungen erzeugt.")
    leitstelle_extern: list[str] = Field(default_factory=list, title="Ausweichen nach extern", json_schema_extra=VERBINDUNGEN,
                                         description="Externe Modelle (etwa bei Hetzner), auf die die Leitstelle ausweichen darf, "
                                                     "wenn die eigenen Rechner lange belegt sind; dabei verlassen Texte das Heimnetz. "
                                                     "Nur wählen, wo die Qualität reicht. Leer: alles bleibt im Heimnetz.")
    leitstelle_geduld_min: int = Field(30, ge=1, le=1440, title="Geduld bei Ausfall",
                                       json_schema_extra={**VERBINDUNGEN, "einheit": "Minuten", "schritt": 5},
                                       description="So lange wartet ein Auftrag, wenn Leitstelle oder Dienst gerade nicht können "
                                                   "(Neustart, Dienst startet, nicht erreichbar); danach gilt der Fehler. Schläft "
                                                   "der Rechner mit dem Dienst, wartet er ohne Grenze, bis er wach ist.")
    ca_datei: str = Field("", title="Zertifikatsstelle", json_schema_extra=VERBINDUNGEN,
                          description="Pfad zur Datei einer eigenen Zertifikatsstelle (rootCA.pem) für Kellerwolke und "
                                      "Leitstelle über HTTPS. Leer: die üblichen Stellen und die Hausstelle dieses "
                                      "Rechners, wenn es eine gibt.")
    adresse: str = Field("", title="Adresse dieser App", json_schema_extra=VERBINDUNGEN,
                         description="Unter dieser Adresse öffnet man die App im Browser; dorthin führt die Kellerwolke, "
                                     "wenn man eine Datei aus ihrem Dateimenü in dieser App öffnet. Wird beim ersten "
                                     "Öffnen nach der Anmeldung eingetragen.")
    weitere_konten: list[str] = Field(default_factory=list, title="Weitere Konten", json_schema_extra=ZUGANG,
                                      description="Wer außer dem Konto des App-Schlüssels diese App nutzen darf "
                                                  "(Namen von Konten der Kellerwolke).")
    anmeldung_ausfall_h: int = Field(24, ge=0, le=168, title="Anmeldung bei Ausfall",
                                     json_schema_extra={**ZUGANG, "einheit": "Stunden"},
                                     description="So lange nach der letzten Bestätigung durch die Kellerwolke gilt eine "
                                                 "Anmeldung weiter, wenn die Kellerwolke gerade nicht erreichbar ist; so "
                                                 "bleibt die App bedienbar, und ihre Adresse lässt sich hier berichtigen. "
                                                 "Neue Anmeldungen brauchen die Kellerwolke immer. 0: keine.")
    sicherung_abstand_tage: int = Field(VORGABE.abstand_tage, ge=1, le=365, title="Regelmäßige Sicherung",
                                        json_schema_extra={**SICHERUNG, "einheit": "Tage"},
                                        description="So viele Tage nach der jüngsten Sicherung legt die App von selbst "
                                                    "eine neue an, aber nur, wenn sich ihre Datenbank seitdem geändert hat.")
    sicherung_vor_ausrollen_ab_stunden: int = Field(VORGABE.vor_ausrollen_ab_stunden, ge=0, le=8760,
                                                    title="Sicherung vor dem Ausrollen",
                                                    json_schema_extra={**SICHERUNG, "einheit": "Stunden"},
                                                    description="Vor dem Neustart beim Ausrollen entsteht eine Sicherung "
                                                                "nur, wenn die jüngste älter ist als so viele Stunden und "
                                                                "sich die Datenbank seitdem geändert hat. 0: vor jedem "
                                                                "Ausrollen, sofern geändert.")
    sicherung_behalten: int = Field(VORGABE.behalten, ge=1, le=100, title="Aufbewahrte Sicherungen",
                                    json_schema_extra={**SICHERUNG, "einheit": "Stände"},
                                    description="So viele Sicherungen bleiben im Ordner der Sicherungen; ältere entfernt "
                                                "die App, sobald es mehr sind.")
