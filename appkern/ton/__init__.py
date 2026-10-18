"""Ton mit ffmpeg für alle Apps: Formate als Modell, Eigenschaften einer Datei messen, genau wandeln (hochwertiges
Resampling, gemessen ob soxr da ist), Dauer, Sprechpausen, Ausschneiden, Wellenform, Abspielfassungen; Gleitkomma lesen, stauchen, genau einmal schreiben."""

from .abspielen import Abspielfassungen
from .ton import ABSPIELEN, ARBEIT, HOEREN, Eigenschaften, Pause, Ton, TonFehler, Tonformat, programm

__all__ = ["ABSPIELEN", "ARBEIT", "Abspielfassungen", "Eigenschaften", "HOEREN", "Pause", "Ton", "TonFehler", "Tonformat", "programm"]
