"""Punto de entrada"""

import argparse
from pathlib import Path
from typing import Sequence

from pipeline.contexto import ContextoPipeline
from pipeline.pipeline import Pipeline
from stages import (
    AnalisisEspacial,
    AnalisisIndividual,
    CargaExperimentos,
    ComparacionExperimentos,
    ExportacionResultados,
    PreparacionTrayectorias,
)


def crear_parser() -> argparse.ArgumentParser:
    """Crea el analizador de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Pipeline inicial: Análisis de Trayectorias Peatonales."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("./data"),
        help="Archivo o directorio de entrada (por defecto: ./data).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./results"),
        help="Directorio de salida (por defecto: ./results).",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=None,
        help=(
            "Frecuencia de muestreo en cuadros por segundo. Solo se usa para "
            "archivos cuya cabecera no indica su framerate."
        ),
    )
    parser.add_argument(
        "--vel-max",
        type=float,
        default=4.0,
        help=(
            "Velocidad [m/s] sobre la cual un desplazamiento entre frames se "
            "considera error de tracking (por defecto: 4.0)."
        ),
    )
    parser.add_argument(
        "--duracion-min",
        type=float,
        default=1.0,
        help="Duración mínima [s] para conservar una trayectoria (por defecto: 1.0).",
    )
    return parser


def main(argumentos: Sequence[str] | None = None) -> int:
    """Configura y ejecuta las etapas del pipeline."""
    configuracion = crear_parser().parse_args(argumentos)
    contexto = ContextoPipeline(
        ruta_entrada=configuracion.input,
        ruta_salida=configuracion.output,
        fps=configuracion.fps,
    )
    etapas = [
        CargaExperimentos(),
        PreparacionTrayectorias(
            velocidad_maxima=configuracion.vel_max,
            duracion_minima=configuracion.duracion_min,
        ),
        AnalisisIndividual(),
        AnalisisEspacial(),
        ComparacionExperimentos(),
        ExportacionResultados(),
    ]
    pipeline = Pipeline(etapas)

    print("Configuración seleccionada:")
    print(f"  Entrada: {contexto.ruta_entrada}")
    print(f"  Salida: {contexto.ruta_salida}")
    frecuencia = str(contexto.fps) if contexto.fps is not None else "según cabecera de cada archivo"
    print(f"  Frecuencia (fps): {frecuencia}")

    return 0 if pipeline.ejecutar(contexto) else 1


if __name__ == "__main__":
    raise SystemExit(main())
