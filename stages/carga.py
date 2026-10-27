"""Etapa de carga de varios experimentos."""

import json
import re
from pathlib import Path

from models.experimento import Experimento
from models.observacion import Observacion
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline

PATRON_FPS = re.compile(r"framerate:\s*([\d.]+)\s*fps", re.IGNORECASE)
NOMBRE_METADATA = "metadata.json"
COLUMNAS_ESPERADAS = 5  # id frame x y z


def parsear_linea(linea: str) -> Observacion | None:
    """Convierte una línea de datos en una observación, o ``None`` si está mal formada."""
    campos = linea.split()  # admite espacios o tabuladores
    if len(campos) != COLUMNAS_ESPERADAS:
        return None
    try:
        return Observacion(
            id_peaton=int(campos[0]),
            frame=int(campos[1]),
            x=float(campos[2]),
            y=float(campos[3]),
            z=float(campos[4]),
        )
    except ValueError:
        return None


def leer_fps(cabecera: list[str]) -> float | None:
    """Busca la frecuencia de muestreo en las líneas de comentario del archivo."""
    coincidencias = (PATRON_FPS.search(linea) for linea in cabecera)
    return next((float(m.group(1)) for m in coincidencias if m), None)


class CargaExperimentos(EtapaPipeline[None, list[Experimento]]):
    """Carga una colección de experimentos desde la ruta configurada."""

    def ejecutar(
        self,
        entrada: None,
        contexto: ContextoPipeline,
    ) -> list[Experimento]:
        """Carga los experimentos indicados por la configuración."""
        experimentos = self._cargar_experimentos(contexto.ruta_entrada, contexto.fps)
        for experimento in experimentos:
            print(
                f"  {experimento.nombre}: {len(experimento.observaciones)} observaciones, "
                f"{experimento.fps:g} fps, "
                f"{experimento.reporte_validacion['lineas_mal_formadas']} líneas mal formadas"
            )
        return experimentos

    def _cargar_experimentos(
        self,
        ruta_entrada: Path,
        fps_por_defecto: float | None = None,
    ) -> list[Experimento]:
        """Carga los experimentos disponibles en la ruta recibida."""
        if ruta_entrada.is_file():
            archivos = [ruta_entrada]
        elif ruta_entrada.is_dir():
            archivos = sorted(ruta_entrada.glob("*.txt"))
        else:
            raise FileNotFoundError(f"No existe la ruta de entrada '{ruta_entrada}'")
        if not archivos:
            raise FileNotFoundError(f"No se encontraron archivos .txt en '{ruta_entrada}'")

        metadata = self._cargar_metadata(archivos[0].parent / NOMBRE_METADATA)
        return [
            self._cargar_archivo(archivo, metadata.get(archivo.stem, {}), fps_por_defecto)
            for archivo in archivos
        ]

    def _cargar_metadata(self, ruta: Path) -> dict[str, dict]:
        """Retorna la información de cada corrida indexada por su nombre."""
        if not ruta.exists():
            print(f"  Aviso: no se encontró {ruta}; se continúa sin parámetros experimentales.")
            return {}
        with ruta.open(encoding="utf-8") as archivo:
            corridas = json.load(archivo)["experiment"]["run"]
        return {corrida["run_name"]: corrida for corrida in corridas}

    def _cargar_archivo(
        self,
        ruta: Path,
        corrida: dict,
        fps_por_defecto: float | None,
    ) -> Experimento:
        """Lee un archivo de trayectorias y construye su experimento."""
        with ruta.open(encoding="utf-8") as archivo:
            lineas = [linea for linea in archivo if linea.strip()]

        cabecera = [linea for linea in lineas if linea.startswith("#")]
        fps = leer_fps(cabecera) or fps_por_defecto
        if fps is None:
            raise ValueError(
                f"'{ruta.name}' no indica su framerate; especifíquelo con --fps"
            )

        candidatas = [parsear_linea(linea) for linea in lineas if not linea.startswith("#")]
        observaciones = [obs for obs in candidatas if obs is not None]

        return Experimento(
            nombre=ruta.stem,
            fps=fps,
            parametros=corrida.get("parameter", {}),
            notas=corrida.get("notes"),
            observaciones=observaciones,
            reporte_validacion={
                "lineas_mal_formadas": len(candidatas) - len(observaciones),
            },
        )
