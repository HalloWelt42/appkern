"""Mitteilungen aufs Gerät (Web Push) als Baustein jeder App: das Gerüst baut ihn mit `push=True`; die App sendet über
`geruest.push.senden(konto, Mitteilung(...))`, die Oberfläche richtet Geräte über lib/push.svelte.ts ein. Geht nur über
HTTPS (oder localhost); auf dem iPhone nur aus der App auf dem Home-Bildschirm."""

from .api import push_router
from .dienst import Abo, Geraet, Mitteilung, Push, Versand

__all__ = ["Abo", "Geraet", "Mitteilung", "Push", "Versand", "push_router"]
