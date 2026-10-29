"""Etapas de carga de experimentos: búsqueda de archivos y lectura de observaciones."""

import json
import re
from dataclasses import replace
from itertools import takewhile
from pathlib import Path

from models.experimento import Experimento
from models.observacion import Observacion
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline, EtapaPorElemento

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


def leer_cabecera(ruta: Path) -> list[str]:
    """Lee solo las líneas de comentario iniciales del archivo, sin recorrer los datos."""
    with ruta.open(encoding="utf-8") as archivo:
        return list(takewhile(lambda linea: linea.startswith("#") or not linea.strip(), archivo))


class CargaExperimentos(EtapaPipeline[None, list[Experimento]]):
    """Identifica los experimentos de la ruta configurada y su condición experimental.

    Solo lee la cabecera de cada archivo (para conocer su FPS) y la metadata;
    las observaciones las lee ``LecturaObservaciones``, que puede ejecutarse
    en paralelo para cada experimento.
    """

    def ejecutar(
        self,
        entrada: None,
        contexto: ContextoPipeline,
    ) -> list[Experimento]:
        """Carga los experimentos indicados por la configuración."""
        experimentos = self._cargar_experimentos(contexto.ruta_entrada, contexto.fps)
        for experimento in experimentos:
            tamano = experimento.ruta.stat().st_size / 1e6
            print(f"  {experimento.nombre}: {experimento.fps:g} fps, {tamano:.1f} MB")
        return experimentos

    def _cargar_experimentos(
        self,
        ruta_entrada: Path,
        fps_por_defecto: float | None = None,
    ) -> list[Experimento]:
        """Crea un experimento (aún sin observaciones) por cada archivo de la ruta."""
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
            self._crear_experimento(archivo, metadata.get(archivo.stem, {}), fps_por_defecto)
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

    def _crear_experimento(
        self,
        ruta: Path,
        corrida: dict,
        fps_por_defecto: float | None,
    ) -> Experimento:
        """Construye el experimento de un archivo con su FPS y su condición experimental."""
        fps = leer_fps(leer_cabecera(ruta)) or fps_por_defecto
        if fps is None:
            raise ValueError(
                f"'{ruta.name}' no indica su framerate; especifíquelo con --fps"
            )
        return Experimento(
            nombre=ruta.stem,
            fps=fps,
            ruta=ruta,
            parametros=corrida.get("parameter", {}),
            notas=corrida.get("notes"),
        )


class LecturaObservaciones(EtapaPorElemento[Experimento]):
    """Lee las observaciones del archivo de un experimento."""

    def procesar(self, experimento: Experimento, contexto: ContextoPipeline) -> Experimento:
        """Retorna el experimento con sus observaciones y el conteo de líneas mal formadas."""
        with experimento.ruta.open(encoding="utf-8") as archivo:
            candidatas = [
                parsear_linea(linea)
                for linea in archivo
                if linea.strip() and not linea.startswith("#")
            ]
        observaciones = [obs for obs in candidatas if obs is not None]
        return replace(
            experimento,
            observaciones=observaciones,
            reporte_validacion={
                **experimento.reporte_validacion,
                "observaciones_leidas": len(observaciones),
                "lineas_mal_formadas": len(candidatas) - len(observaciones),
            },
        )

    def describir(self, experimento: Experimento) -> str:
        """Cantidad de observaciones leídas y descartadas por formato.

        Usa el reporte y no ``observaciones`` porque, si se describe al final
        de una cadena de etapas, esa lista ya está validada.
        """
        reporte = experimento.reporte_validacion
        return (
            f"{experimento.nombre}: {reporte['observaciones_leidas']} observaciones, "
            f"{reporte['lineas_mal_formadas']} líneas mal formadas"
        )
