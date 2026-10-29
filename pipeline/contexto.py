"""Configuración de una ejecución del pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ContextoPipeline:
    """Contiene únicamente las opciones de ejecución del programa.

    ``parametros`` guarda todos los argumentos recibidos por línea de
    comandos, para registrarlos junto a los resultados y poder reproducirlos.
    """

    ruta_entrada: Path
    ruta_salida: Path
    fps: float | None = None
    parametros: dict[str, Any] = field(default_factory=dict)
