"""Modelo básico de una trayectoria peatonal."""

import math
from array import array
from dataclasses import dataclass, field
from itertools import pairwise

from .observacion import Observacion


def reconstruir_trayectoria(
    id_peaton: int,
    frames: array,
    xs: array,
    ys: array,
    zs: array,
    velocidades: array,
) -> "Trayectoria":
    """Inverso de ``Trayectoria.__reduce__``: vuelve a crear las observaciones desde columnas."""
    observaciones = [
        Observacion(id_peaton, frame, x, y, z)
        for frame, x, y, z in zip(frames, xs, ys, zs)
    ]
    return Trayectoria(id_peaton, observaciones, list(velocidades))


@dataclass
class Trayectoria:
    """Representa las observaciones y cálculos propios de un peatón.

    Se asume que ``observaciones`` está ordenada por frame; la etapa de
    preparación garantiza esta condición al reconstruir la trayectoria.
    ``velocidades`` guarda la velocidad suavizada [m/s] de cada observación;
    la completa el análisis individual y la reutilizan las etapas siguientes.
    """

    id_peaton: int
    observaciones: list[Observacion] = field(default_factory=list)
    velocidades: list[float] = field(default_factory=list)

    def __reduce__(self):
        """Serializa la trayectoria por columnas (``array``) en vez de observación por observación.

        ``pickle`` lo usa al enviar resultados entre procesos. Guardar cinco
        arreglos numéricos es unas 5 veces más rápido que serializar cientos
        de miles de objetos ``Observacion`` uno a uno.
        """
        obs = self.observaciones
        return (
            reconstruir_trayectoria,
            (
                self.id_peaton,
                array("q", [o.frame for o in obs]),
                array("d", [o.x for o in obs]),
                array("d", [o.y for o in obs]),
                array("d", [o.z for o in obs]),
                array("d", self.velocidades),
            ),
        )

    @property
    def posicion_inicial(self) -> tuple[float, float]:
        """Primera posición (x, y) observada, en metros."""
        return self.observaciones[0].posicion

    @property
    def posicion_final(self) -> tuple[float, float]:
        """Última posición (x, y) observada, en metros."""
        return self.observaciones[-1].posicion

    def calcular_tiempo_total(self, fps: float) -> float:
        """Tiempo observado entre la primera y la última observación, en segundos."""
        if len(self.observaciones) < 2:
            return 0.0
        return (self.observaciones[-1].frame - self.observaciones[0].frame) / fps

    def calcular_distancias(self) -> list[float]:
        """Distancia d_i [m] entre cada par de observaciones consecutivas."""
        return [math.dist(a.posicion, b.posicion) for a, b in pairwise(self.observaciones)]

    def calcular_velocidades_instantaneas(self, fps: float) -> list[float]:
        """Velocidad v_i = d_i / Δt_i [m/s] entre observaciones consecutivas."""
        return [
            math.dist(a.posicion, b.posicion) / ((b.frame - a.frame) / fps)
            for a, b in pairwise(self.observaciones)
        ]

    def calcular_velocidades_suavizadas(self, fps: float, ventana: float) -> list[float]:
        """Velocidad [m/s] en cada observación, medida sobre una ventana centrada.

        Para la observación i se usa el desplazamiento entre las posiciones
        i - h e i + h, con h = ventana · fps / 2 (recortado en los extremos).
        Al medir sobre un intervalo más largo que un frame, el error de
        posición del tracking se divide por un Δt mayor y deja de dominar.
        """
        obs = self.observaciones
        if len(obs) < 2:
            return [0.0] * len(obs)
        ultimo = len(obs) - 1
        medio = max(1, round(ventana * fps / 2))

        def velocidad_en(i: int) -> float:
            a, b = obs[max(0, i - medio)], obs[min(ultimo, i + medio)]
            return math.dist(a.posicion, b.posicion) / ((b.frame - a.frame) / fps)

        return list(map(velocidad_en, range(len(obs))))

    def calcular_distancia_total(self) -> float:
        """Calcula la distancia total recorrida por el peatón."""
        return sum(self.calcular_distancias())

    def calcular_desplazamiento(self) -> float:
        """Calcula el desplazamiento entre el inicio y el final."""
        return math.dist(self.posicion_inicial, self.posicion_final)

    def calcular_velocidad_media(self, fps: float) -> float:
        """Calcula la velocidad media usando la frecuencia del experimento."""
        tiempo = self.calcular_tiempo_total(fps)
        return self.calcular_distancia_total() / tiempo if tiempo > 0 else 0.0

    def calcular_eficiencia(self) -> float:
        """Eficiencia E = D / Dr; 1 indica una trayectoria recta."""
        distancia = self.calcular_distancia_total()
        return self.calcular_desplazamiento() / distancia if distancia > 0 else 0.0
