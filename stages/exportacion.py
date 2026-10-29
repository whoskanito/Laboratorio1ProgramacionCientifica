"""Etapa de exportación de resultados."""

import csv
import json
import math
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from models.resultado_analisis import ResultadoAnalisis
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline

# Archivo que identifica un directorio de salida creado por este pipeline.
MARCA_RESULTADOS = ".resultados_pipeline"
DECIMALES = 4


def preparar_directorio(ruta: Path) -> None:
    """Borra y recrea el directorio de salida para que solo contenga la ejecución actual.

    Por seguridad solo se borra un directorio vacío o uno que contenga la
    marca dejada por una ejecución anterior; así un ``--output`` equivocado
    (por ejemplo, la carpeta del proyecto) nunca se elimina.
    """
    if ruta.exists():
        if not ruta.is_dir():
            raise ValueError(f"La salida '{ruta}' existe y no es un directorio")
        if any(ruta.iterdir()) and not (ruta / MARCA_RESULTADOS).exists():
            raise ValueError(
                f"'{ruta}' no está vacío y no fue creado por este pipeline; "
                "no se borrará. Indique otro directorio con --output"
            )
        shutil.rmtree(ruta)
    ruta.mkdir(parents=True)
    (ruta / MARCA_RESULTADOS).write_text(
        "Directorio generado por main.py: se borra y se vuelve a crear en cada ejecución.\n",
        encoding="utf-8",
    )


def formatear_valor(valor: Any) -> Any:
    """Redondea los decimales y deja vacío lo que no está definido (NaN)."""
    if isinstance(valor, float):
        return "" if math.isnan(valor) else round(valor, DECIMALES)
    return valor


def escribir_csv(ruta: Path, filas: list[dict[str, Any]]) -> None:
    """Escribe una tabla (lista de filas con las mismas columnas) en formato CSV."""
    columnas = list(filas[0]) if filas else []
    with ruta.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=columnas)
        escritor.writeheader()
        escritor.writerows({k: formatear_valor(v) for k, v in fila.items()} for fila in filas)


def a_json(valor: Any) -> Any:
    """Convierte recursivamente los valores a tipos válidos en JSON (NaN → null)."""
    if isinstance(valor, dict):
        return {str(k): a_json(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [a_json(v) for v in valor]
    if isinstance(valor, Path):
        return str(valor)
    if isinstance(valor, float):
        return None if math.isnan(valor) else round(valor, DECIMALES)
    return valor


class ExportacionResultados(EtapaPipeline[ResultadoAnalisis, ResultadoAnalisis]):
    """Exporta los resultados de los experimentos y su comparación."""

    def ejecutar(
        self,
        resultados: ResultadoAnalisis,
        contexto: ContextoPipeline,
    ) -> ResultadoAnalisis:
        """Guarda los resultados en la ruta de salida configurada."""
        preparar_directorio(contexto.ruta_salida)
        self._exportar(resultados, contexto)
        archivos = sorted(p.name for p in contexto.ruta_salida.iterdir() if p.suffix in {".csv", ".json"})
        print(f"  {len(archivos)} archivos en {contexto.ruta_salida}: {', '.join(archivos)}")
        return resultados

    def _exportar(self, resultados: ResultadoAnalisis, contexto: ContextoPipeline) -> None:
        """Exporta los resultados a la ruta indicada."""
        ruta = contexto.ruta_salida
        experimentos = resultados.experimentos

        def tabla(atributo: str) -> list[dict[str, Any]]:
            """Une las filas de todos los experimentos, anteponiendo el nombre de cada uno."""
            return [
                {"experimento": e.nombre, **fila}
                for e in experimentos
                for fila in getattr(e, atributo)
            ]

        escribir_csv(ruta / "experimentos.csv", resultados.resumen)
        escribir_csv(
            ruta / "individuales.csv",
            [
                {"experimento": e.nombre, "id_peaton": id_peaton, **indicadores}
                for e in experimentos
                for id_peaton, indicadores in e.resultados_individuales.items()
            ],
        )
        escribir_csv(ruta / "zonas.csv", tabla("resultados_zonas"))
        escribir_csv(ruta / "densidad.csv", tabla("serie_densidad"))
        escribir_csv(ruta / "flujo.csv", tabla("serie_flujo"))
        escribir_csv(ruta / "diagrama_fundamental.csv", resultados.diagrama_fundamental)
        escribir_csv(
            ruta / "validacion.csv",
            [{"experimento": e.nombre, **e.reporte_validacion} for e in experimentos],
        )

        resumen = {
            "generado": datetime.now().isoformat(timespec="seconds"),
            "parametros": contexto.parametros,
            "comparacion": resultados.comparacion,
            "experimentos": {
                e.nombre: {
                    "fps": e.fps,
                    "parametros": e.parametros,
                    "notas": e.notas,
                    "validacion": e.reporte_validacion,
                    "colectivos": e.resultados_colectivos,
                }
                for e in experimentos
            },
        }
        with (ruta / "resumen.json").open("w", encoding="utf-8") as archivo:
            json.dump(a_json(resumen), archivo, ensure_ascii=False, indent=2)
