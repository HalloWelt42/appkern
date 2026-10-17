"""Gerüst einer App aus den Bausteinen des Appkerns (Zusatz `appkern[web]`)."""

from .einstellungen import Grundeinstellungen
from .geruest import AppInfo, Begleiter, Geruest, Verbindung

__all__ = ["AppInfo", "Begleiter", "Geruest", "Grundeinstellungen", "Verbindung"]
