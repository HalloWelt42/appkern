"""Einstellungen von __NAME__. Kellerwolke, Leitstelle und weitere Konten bringt das Gerüst mit; eigene Felder kommen
hier dazu (mit `Field(title=..., description=...)`, Auswahl über `Literal`, Geheimnisse als `SecretStr`). Die Seite
Einstellungen der Oberfläche entsteht daraus von selbst."""

from appkern.app import Grundeinstellungen


class AppEinstellungen(Grundeinstellungen):
    pass
