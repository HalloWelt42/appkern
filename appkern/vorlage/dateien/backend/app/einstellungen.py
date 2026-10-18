"""Einstellungen von __NAME__. Kellerwolke, Leitstelle und weitere Konten bringt das Gerüst mit; eigene Felder kommen
hier dazu (mit `Field(title=..., description=...)`, Auswahl über `Literal`, Geheimnisse als `SecretStr`). Die Seite
Einstellungen der Oberfläche entsteht daraus von selbst."""

from appkern.app import Grundeinstellungen
# ton:anfang
from pydantic import Field
# ton:ende


class AppEinstellungen(Grundeinstellungen):
    # ton:anfang
    dienst_ton: str = Field("klangwerk-ton", title="Tondienst",
                            description="Dienst der Leitstelle für alle Tonarbeit; gerechnet wird auf dem Mac, nie hier")
    # ton:ende
    pass
