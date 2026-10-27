"""Modelo básico de una observación peatonal."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Observacion:
    """Representa la posición registrada de un peatón en un cuadro.

    Es inmutable (``frozen``) porque una observación es un dato medido que no
    debe alterarse durante el procesamiento; ``slots`` reduce la memoria, ya
    que un experimento puede contener cientos de miles de observaciones.
    """

    id_peaton: int
    frame: int
    x: float
    y: float
    z: float

    @property
    def posicion(self) -> tuple[float, float]:
        """Posición planar (x, y) en metros."""
        return (self.x, self.y)
