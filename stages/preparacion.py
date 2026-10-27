"""Etapa de preparación de observaciones y trayectorias."""

import math
from dataclasses import replace
from functools import reduce
from itertools import groupby
from operator import attrgetter

from models.experimento import Experimento
from models.observacion import Observacion
from models.trayectoria import Trayectoria
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline


def es_registro_valido(observacion: Observacion) -> bool:
    """Un registro es válido si sus coordenadas son finitas y su frame no es negativo."""
    coordenadas = (observacion.x, observacion.y, observacion.z)
    return observacion.frame >= 0 and all(map(math.isfinite, coordenadas))


def eliminar_duplicados(observaciones: list[Observacion]) -> list[Observacion]:
    """Conserva un único registro por par (peatón, frame); prevalece el último leído."""
    return list({(obs.id_peaton, obs.frame): obs for obs in observaciones}.values())


def filtrar_saltos(
    observaciones: list[Observacion],
    fps: float,
    velocidad_maxima: float,
) -> list[Observacion]:
    """Descarta posiciones que implicarían una velocidad físicamente imposible.

    Cada observación se compara con la última aceptada: si para alcanzarla se
    requiere una velocidad mayor a ``velocidad_maxima`` se considera un error
    de tracking. Como el intervalo crece con cada descarte, un salto aislado se
    elimina sin perder el resto de la trayectoria.
    """

    def acumular(aceptadas: list[Observacion], actual: Observacion) -> list[Observacion]:
        previa = aceptadas[-1]
        intervalo = (actual.frame - previa.frame) / fps
        if math.dist(previa.posicion, actual.posicion) / intervalo <= velocidad_maxima:
            aceptadas.append(actual)
        return aceptadas

    if not observaciones:
        return []
    return reduce(acumular, observaciones[1:], [observaciones[0]])


class PreparacionTrayectorias(EtapaPipeline[list[Experimento], list[Experimento]]):
    """Agrupa validación, organización y reconstrucción de trayectorias."""

    def __init__(self, velocidad_maxima: float = 4.0, duracion_minima: float = 1.0) -> None:
        """
        Args:
            velocidad_maxima: velocidad [m/s] sobre la cual un desplazamiento
                entre frames se considera error de tracking.
            duracion_minima: duración [s] mínima para conservar una trayectoria.
        """
        self._velocidad_maxima = velocidad_maxima
        self._duracion_minima = duracion_minima

    def ejecutar(
        self,
        experimentos: list[Experimento],
        contexto: ContextoPipeline,
    ) -> list[Experimento]:
        """Prepara las observaciones y trayectorias de cada experimento."""
        preparados = [self._preparar(experimento) for experimento in experimentos]
        for experimento in preparados:
            reporte = ", ".join(f"{k}={v}" for k, v in experimento.reporte_validacion.items())
            print(f"  {experimento.nombre}: {len(experimento.trayectorias)} trayectorias ({reporte})")
        return preparados

    def _preparar(self, experimento: Experimento) -> Experimento:
        """Retorna una copia del experimento con observaciones validadas y trayectorias."""
        validas, reporte = self._validar_observaciones(experimento.observaciones)
        organizadas = self._organizar_observaciones(validas)

        sin_saltos = {
            id_peaton: filtrar_saltos(obs, experimento.fps, self._velocidad_maxima)
            for id_peaton, obs in organizadas.items()
        }
        reporte["saltos_eliminados"] = len(validas) - sum(map(len, sin_saltos.values()))

        trayectorias = self._reconstruir_trayectorias(sin_saltos)
        conservadas = [
            t for t in trayectorias
            if t.calcular_tiempo_total(experimento.fps) >= self._duracion_minima
        ]
        reporte["trayectorias_cortas"] = len(trayectorias) - len(conservadas)

        return replace(
            experimento,
            observaciones=[obs for t in conservadas for obs in t.observaciones],
            trayectorias=conservadas,
            reporte_validacion={**experimento.reporte_validacion, **reporte},
        )

    def _validar_observaciones(
        self,
        observaciones: list[Observacion],
    ) -> tuple[list[Observacion], dict[str, int]]:
        """Valida las observaciones y retorna las válidas junto a un conteo de descartes."""
        correctas = list(filter(es_registro_valido, observaciones))
        unicas = eliminar_duplicados(correctas)
        reporte = {
            "registros_invalidos": len(observaciones) - len(correctas),
            "duplicados": len(correctas) - len(unicas),
        }
        return unicas, reporte

    def _organizar_observaciones(
        self,
        observaciones: list[Observacion],
    ) -> dict[int, list[Observacion]]:
        """Organiza las observaciones por identificador de peatón, en orden temporal."""
        ordenadas = sorted(observaciones, key=attrgetter("id_peaton", "frame"))
        return {
            id_peaton: list(grupo)
            for id_peaton, grupo in groupby(ordenadas, key=attrgetter("id_peaton"))
        }

    def _reconstruir_trayectorias(
        self,
        observaciones_organizadas: dict[int, list[Observacion]],
    ) -> list[Trayectoria]:
        """Construye trayectorias desde las observaciones organizadas."""
        return [
            Trayectoria(id_peaton=id_peaton, observaciones=observaciones)
            for id_peaton, observaciones in observaciones_organizadas.items()
        ]
