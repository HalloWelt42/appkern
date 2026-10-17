"""Arten von Aufträgen. Der Probeauftrag zeigt den Ablauf (Phasen, Fortschritt, Abbruch, Fortsetzen) und wird durch
die eigentlichen Arten der App ersetzt."""

import asyncio

from pydantic import BaseModel, Field

from appkern.app import Geruest
from appkern.auftraege import Art, Kontext, Phase


class ProbeEingabe(BaseModel):
    schritte: int = Field(10, ge=1, le=1000)
    pause_s: float = Field(0.5, ge=0, le=10)


def arten(geruest: Geruest) -> list[Art]:
    async def probe(k: Kontext):
        await k.fortschritt(0.0, "Vorbereiten", phase="vorbereiten")
        fertig = int(k.zwischenstand.get("fertig", 0))
        await k.fortschritt(fertig / k.eingabe.schritte, "Rechnen", phase="rechnen")
        for n in range(fertig, k.eingabe.schritte):
            await k.pruefen()
            await asyncio.sleep(k.eingabe.pause_s)
            await k.merken(fertig=n + 1)
            await k.fortschritt((n + 1) / k.eingabe.schritte, f"Schritt {n + 1} von {k.eingabe.schritte}")
        await k.fortschritt(1.0, "Abschließen", phase="abschliessen")
        return {"schritte": k.eingabe.schritte}

    return [
        Art("probe", "Probeauftrag", probe, eingabe=ProbeEingabe, fortsetzbar=True, nach_neustart="fortsetzen",
            phasen=[Phase(schluessel="vorbereiten", titel="Vorbereiten", symbol="box-open"),
                    Phase(schluessel="rechnen", titel="Rechnen", symbol="gears"),
                    Phase(schluessel="abschliessen", titel="Abschließen", symbol="flag-checkered")]),
    ]
