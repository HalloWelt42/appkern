"""Die laufende Arbeit: jede Anfrage an die Leitstelle, die innerhalb eines Auftrags der App läuft, trägt dessen
Kennung im Kopf `X-Leitstelle-Arbeit`. So sieht die Leitstelle, welche Modelle eine begonnene lange Arbeit nutzt, und
entlädt sie für andere nicht (Nutzer 18.10.2026: "Begonnenes nicht wegnehmen"). Gesetzt wird die Kennung vom
Auftragsdienst; die Aufrufstellen merken davon nichts."""

from __future__ import annotations

from contextvars import ContextVar

LAUFENDE_ARBEIT: ContextVar[str | None] = ContextVar("leitstelle_laufende_arbeit", default=None)
KOPF = "X-Leitstelle-Arbeit"
