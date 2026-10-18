"""Ein Befund einer Prüfung: wo, welche Regel, was dort steht."""

from pydantic import BaseModel


class Befund(BaseModel):
    datei: str
    zeile: int
    regel: str
    text: str

    def __str__(self) -> str:
        return f"{self.datei}:{self.zeile}: {self.regel}: {self.text[:110]}"
