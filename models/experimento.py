"""Entidad que agrupa los datos y resultados de un experimento."""

from dataclasses import dataclass, field

from .observacion import Observacion
from .trayectoria import Trayectoria


@dataclass
class Experimento:
    """Representa un conjunto de observaciones y sus análisis.

    ``fps`` se obtiene de la cabecera de cada archivo, porque no todas las
    corridas fueron registradas con la misma frecuencia. ``parametros`` y
    ``notas`` provienen de ``metadata.json`` y describen la condición
    experimental (anchos de entrada/salida y sentido de movimiento).
    """

    nombre: str
    fps: float
    parametros: dict[str, str] = field(default_factory=dict)
    notas: str | None = None
    observaciones: list[Observacion] = field(default_factory=list)
    trayectorias: list[Trayectoria] = field(default_factory=list)
    reporte_validacion: dict[str, int] = field(default_factory=dict)
    resultados_individuales: dict[int, dict[str, float]] = field(default_factory=dict)
    resultados_colectivos: dict[str, float] = field(default_factory=dict)
