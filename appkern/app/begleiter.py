"""Hintergrundarbeit einer App, die mit dem Gerüst lebt. Ein eigenes Modul, damit Bausteine, die das Gerüst selbst
mitbringt (etwa die Sicherung), davon ableiten, ohne dass Gerüst und Baustein einander beim Laden brauchen."""

from __future__ import annotations


class Begleiter:
    """Hintergrundarbeit einer App, die mit dem Gerüst lebt, etwa ein Abgleich mit der Kellerwolke. Eine App leitet
    davon ab und überschreibt, was sie braucht; angemeldet mit `geruest.begleiter_anmelden`.

    Reihenfolge beim Start: Datenbank, Einstellungen, Protokoll, Zugänge, dann `starten` und `verbunden` jedes
    Begleiters, danach erst die Aufträge (die sich auf den Begleiter verlassen dürfen). `verbunden` kommt nach jedem
    Neuaufbau der Zugänge wieder (geänderte Kellerwolke oder Leitstelle). Beim Stoppen enden erst die Aufträge, dann die
    Begleiter in umgekehrter Reihenfolge. Ein Fehler eines Begleiters steht im Log und hält die App nicht an."""

    async def starten(self) -> None:
        """Einmal beim Start, etwa das eigene Datenbankschema einrichten."""

    async def verbunden(self) -> None:
        """Nach jedem Aufbau der Zugänge (auch dem ersten)."""

    async def stoppen(self) -> None:
        """Beim Beenden: eigene Aufgaben beenden."""
