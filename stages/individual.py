"""Etapa de análisis individual de los experimentos."""

import statistics
from dataclasses import replace
from itertools import groupby

from models.experimento import Experimento
from models.observacion import Observacion
from models.trayectoria import Trayectoria
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline


def detectar_detenciones(
    observaciones: list[Observacion],
    velocidades: list[float],
    fps: float,
    umbral: float,
    duracion_minima: float,
) -> list[tuple[int, int]]:
    """Retorna los intervalos (frame inicial, frame final) en que el peatón está detenido.

    Una detención es una secuencia de observaciones consecutivas con velocidad
    menor a ``umbral`` que se mantiene al menos ``duracion_minima`` segundos.
    """
    rachas = [
        (lento, [obs.frame for obs, _ in grupo])
        for lento, grupo in groupby(zip(observaciones, velocidades), key=lambda par: par[1] < umbral)
    ]
    intervalos = [(frames[0], frames[-1]) for lento, frames in rachas if lento]
    return [(ini, fin) for ini, fin in intervalos if (fin - ini) / fps >= duracion_minima]


class AnalisisIndividual(EtapaPipeline[list[Experimento], list[Experimento]]):
    """Coordina el análisis de múltiples trayectorias y reúne sus indicadores."""

    def __init__(
        self,
        ventana_suavizado: float = 5.0,
        umbral_detencion: float = 0.2,
        duracion_minima_detencion: float = 0.5,
    ) -> None:
        """
        Args:
            ventana_suavizado: ancho total [s] de la ventana para la velocidad suavizada.
            umbral_detencion: velocidad [m/s] bajo la cual el peatón se considera detenido.
            duracion_minima_detencion: duración [s] mínima de una detención.
        """
        self._ventana = ventana_suavizado
        self._umbral = umbral_detencion
        self._duracion_minima = duracion_minima_detencion

    def ejecutar(
        self,
        experimentos: list[Experimento],
        contexto: ContextoPipeline,
    ) -> list[Experimento]:
        """Analiza las trayectorias de cada experimento."""
        analizados = [self._analizar(experimento) for experimento in experimentos]
        for experimento in analizados:
            resultados = list(experimento.resultados_individuales.values())
            v_media, eficiencia, detenido = (
                statistics.mean(r[clave] for r in resultados)
                for clave in ("velocidad_media", "eficiencia", "porcentaje_detenido")
            )
            print(
                f"  {experimento.nombre}: v media {v_media:.2f} m/s, "
                f"eficiencia {eficiencia:.2f}, detenido {detenido:.1f} % del tiempo"
            )
        return analizados

    def _analizar(self, experimento: Experimento) -> Experimento:
        """Retorna una copia del experimento con velocidades e indicadores calculados."""
        fps = experimento.fps
        trayectorias = [
            replace(t, velocidades=t.calcular_velocidades_suavizadas(fps, self._ventana))
            for t in experimento.trayectorias
        ]
        return replace(
            experimento,
            trayectorias=trayectorias,
            resultados_individuales={
                t.id_peaton: self._calcular_indicadores(t, fps) for t in trayectorias
            },
        )

    def _calcular_indicadores(
        self,
        trayectoria: Trayectoria,
        fps: float,
    ) -> dict[str, float]:
        """Calcula los indicadores individuales de una trayectoria."""
        x_inicial, y_inicial = trayectoria.posicion_inicial
        x_final, y_final = trayectoria.posicion_final
        tiempo_total = trayectoria.calcular_tiempo_total(fps)
        detenciones = self._detectar_detenciones(trayectoria, fps)
        tiempo_detenido = sum((fin - ini) / fps for ini, fin in detenciones)
        return {
            "x_inicial": x_inicial,
            "y_inicial": y_inicial,
            "x_final": x_final,
            "y_final": y_final,
            "tiempo_total": tiempo_total,
            "distancia_total": trayectoria.calcular_distancia_total(),
            "desplazamiento": trayectoria.calcular_desplazamiento(),
            "velocidad_media": trayectoria.calcular_velocidad_media(fps),
            "velocidad_maxima": max(trayectoria.velocidades),
            "eficiencia": trayectoria.calcular_eficiencia(),
            "detenciones": len(detenciones),
            "tiempo_detenido": tiempo_detenido,
            "porcentaje_detenido": 100 * tiempo_detenido / tiempo_total if tiempo_total else 0.0,
        }

    def _detectar_detenciones(
        self,
        trayectoria: Trayectoria,
        fps: float,
    ) -> list[tuple[int, int]]:
        """Identifica intervalos de detención de una trayectoria."""
        return detectar_detenciones(
            trayectoria.observaciones,
            trayectoria.velocidades,
            fps,
            self._umbral,
            self._duracion_minima,
        )
