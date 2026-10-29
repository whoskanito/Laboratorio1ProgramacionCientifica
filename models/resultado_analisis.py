"""Resultados de los análisis realizados sobre varios experimentos."""

from dataclasses import dataclass

from .experimento import Experimento


@dataclass
class ResultadoAnalisis:
    """Conserva los experimentos y los resultados de su comparación.

    - ``resumen``: una fila por experimento con sus indicadores agregados.
    - ``diagrama_fundamental``: velocidad y flujo por rango de densidad,
      combinando los segundos de todas las corridas.
    - ``comparacion``: indicadores globales que relacionan las corridas.
    """

    experimentos: list[Experimento]
    resumen: list[dict[str, float | str]]
    diagrama_fundamental: list[dict[str, float]]
    comparacion: dict[str, float | str]
