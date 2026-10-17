"""Gerüst einer App aus den Bausteinen des Appkerns (Zusatz `appkern[web]`)."""

from .einstellungen import Grundeinstellungen
from .geruest import AppInfo, Geruest, Verbindung

__all__ = ["AppInfo", "Geruest", "Grundeinstellungen", "Verbindung"]
