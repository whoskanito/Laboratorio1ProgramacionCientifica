"""Modelo básico de una trayectoria peatonal."""

from dataclasses import dataclass, field

from .observacion import Observacion


@dataclass
class Trayectoria:
    """Representa las observaciones y cálculos propios de un peatón.

    Se asume que ``observaciones`` está ordenada por frame; la etapa de
    preparación garantiza esta condición al reconstruir la trayectoria.
    """

    id_peaton: int
    observaciones: list[Observacion] = field(default_factory=list)

    def calcular_tiempo_total(self, fps: float) -> float:
        """Tiempo observado entre la primera y la última observación, en segundos."""
        if len(self.observaciones) < 2:
            return 0.0
        return (self.observaciones[-1].frame - self.observaciones[0].frame) / fps

    def calcular_distancia_total(self) -> float:
        """Calcula la distancia total recorrida por el peatón."""
        raise NotImplementedError

    def calcular_desplazamiento(self) -> float:
        """Calcula el desplazamiento entre el inicio y el final."""
        raise NotImplementedError

    def calcular_velocidad_media(self, fps: float) -> float:
        """Calcula la velocidad media usando la frecuencia del experimento."""
        raise NotImplementedError
