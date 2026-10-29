"""Etapa de análisis espacial, densidad y flujo."""

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import replace
from itertools import pairwise

from models.experimento import Experimento
from models.region import Region
from models.trayectoria import Trayectoria
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPorElemento

# Tramo del corredor cubierto por las cámaras en las nueve corridas.
REGION_ANALISIS = Region("corredor", x_min=-5.0, x_max=4.0, y_min=0.0, y_max=5.0)
# Área central para densidad y velocidad, lejos de la entrada y la salida.
AREA_MEDICION = Region("medicion", x_min=-2.0, x_max=2.0, y_min=0.0, y_max=5.0)
UMBRAL_ZONA_LENTA = 0.8  # fracción de la velocidad media de la región


def promedio(valores: list[float]) -> float:
    """Media aritmética, o NaN si no hay valores."""
    return statistics.fmean(valores) if valores else math.nan


def correlacion(x: list[float], y: list[float]) -> float:
    """Coeficiente de Pearson, o NaN si hay menos de dos datos o alguna serie es constante."""
    try:
        return statistics.correlation(x, y)
    except statistics.StatisticsError:
        return math.nan


def sentido_movimiento(trayectorias: list[Trayectoria]) -> int:
    """Retorna +1 si los peatones avanzan hacia x creciente y -1 en caso contrario."""
    avance = sum(t.posicion_final[0] - t.posicion_inicial[0] for t in trayectorias)
    return 1 if avance >= 0 else -1


def instante_cruce(
    trayectoria: Trayectoria,
    x_linea: float,
    sentido: int,
    fps: float,
) -> float | None:
    """Instante [s] del primer cruce de la línea x = ``x_linea`` en el sentido del flujo.

    El instante se interpola linealmente entre las dos observaciones que
    quedan a cada lado de la línea, lo que da una resolución menor a un frame.
    """
    return next(
        (
            (a.frame + (x_linea - a.x) / (b.x - a.x) * (b.frame - a.frame)) / fps
            for a, b in pairwise(trayectoria.observaciones)
            if (a.x - x_linea) * sentido < 0 <= (b.x - x_linea) * sentido
        ),
        None,
    )


class AnalisisEspacial(EtapaPorElemento[Experimento]):
    """Agrupa el análisis por zonas y los cálculos de densidad y flujo."""

    def __init__(
        self,
        ancho_zona: float = 1.0,
        linea_flujo: float = 0.0,
        ventana_flujo: float = 10.0,
        region: Region = REGION_ANALISIS,
        area_medicion: Region = AREA_MEDICION,
    ) -> None:
        """
        Args:
            ancho_zona: largo [m] de cada zona a lo largo del corredor.
            linea_flujo: coordenada x [m] de la línea transversal para el flujo.
            ventana_flujo: duración [s] de los intervalos de la serie de flujo.
            region: tramo del corredor que se divide en zonas.
            area_medicion: área donde se mide la densidad.
        """
        self._ancho_zona = ancho_zona
        self._linea_flujo = linea_flujo
        self._ventana_flujo = ventana_flujo
        self._region = region
        self._area_medicion = area_medicion

    def describir(self, experimento: Experimento) -> str:
        """Densidad media, flujo y zonas lentas del experimento."""
        r = experimento.resultados_colectivos
        lentas = [f["zona"] for f in experimento.resultados_zonas if f["zona_lenta"]]
        return (
            f"{experimento.nombre}: densidad media {r['densidad_media']:.2f} 1/m², "
            f"flujo {r['flujo']:.2f} 1/s, zonas lentas {lentas or 'ninguna'}"
        )

    def procesar(self, experimento: Experimento, contexto: ContextoPipeline) -> Experimento:
        """Retorna una copia del experimento con los resultados espaciales."""
        sentido = sentido_movimiento(experimento.trayectorias)
        zonas = self._analizar_zonas(experimento, sentido)
        densidad = self._calcular_densidad(experimento)
        flujo, cruces = self._calcular_flujo(experimento, sentido)
        return replace(
            experimento,
            resultados_zonas=zonas,
            serie_densidad=densidad,
            serie_flujo=flujo,
            resultados_colectivos=self._resumir(experimento, densidad, cruces),
        )

    def _analizar_zonas(
        self,
        experimento: Experimento,
        sentido: int,
    ) -> list[dict[str, float]]:
        """Calcula peatones, velocidad, densidad y tiempo de cruce de cada zona.

        Las zonas se numeran desde la entrada del corredor (1) hacia la salida,
        para que sean comparables entre corridas con sentidos opuestos.
        """
        fps = experimento.fps
        zonas = self._region.dividir_en_x(self._ancho_zona)
        velocidades: defaultdict[int, list[float]] = defaultdict(list)
        frames_en_zona: defaultdict[int, Counter[int]] = defaultdict(Counter)
        frames_ocupados: set[int] = set()

        for trayectoria in experimento.trayectorias:
            for obs, velocidad in zip(trayectoria.observaciones, trayectoria.velocidades):
                if self._region.contiene(obs.x, obs.y):
                    indice = int((obs.x - self._region.x_min) // self._ancho_zona)
                    velocidades[indice].append(velocidad)
                    frames_en_zona[indice][trayectoria.id_peaton] += 1
                    frames_ocupados.add(obs.frame)

        rangos_x = {
            t.id_peaton: (min(o.x for o in t.observaciones), max(o.x for o in t.observaciones))
            for t in experimento.trayectorias
        }
        velocidad_region = promedio([v for lista in velocidades.values() for v in lista])

        def resumir_zona(indice: int, zona: Region) -> dict[str, float]:
            # Solo quienes recorren la zona completa aportan al tiempo de cruce.
            tiempos_cruce = [
                frames / fps
                for id_peaton, frames in frames_en_zona[indice].items()
                if rangos_x[id_peaton][0] < zona.x_min and rangos_x[id_peaton][1] >= zona.x_max
            ]
            velocidad = promedio(velocidades[indice])
            return {
                "zona": indice + 1 if sentido > 0 else len(zonas) - indice,
                "x_min": zona.x_min,
                "x_max": zona.x_max,
                "peatones": len(frames_en_zona[indice]),
                "velocidad_media": velocidad,
                "tiempo_medio": promedio(tiempos_cruce),
                "densidad_media": len(velocidades[indice]) / (len(frames_ocupados) * zona.area)
                if frames_ocupados else 0.0,
                "velocidad_relativa": velocidad / velocidad_region,
                "zona_lenta": int(velocidad < UMBRAL_ZONA_LENTA * velocidad_region),
            }

        filas = [resumir_zona(indice, zona) for indice, zona in enumerate(zonas)]
        return sorted(filas, key=lambda fila: fila["zona"])

    def _calcular_densidad(self, experimento: Experimento) -> list[dict[str, float]]:
        """Serie temporal, por segundo, de densidad ρ = N / A y velocidad en el área de medición."""
        fps = experimento.fps
        area = self._area_medicion
        por_frame: defaultdict[int, list[float]] = defaultdict(list)
        for trayectoria in experimento.trayectorias:
            for obs, velocidad in zip(trayectoria.observaciones, trayectoria.velocidades):
                if area.contiene(obs.x, obs.y):
                    por_frame[obs.frame].append(velocidad)
        if not por_frame:
            return []

        primero, ultimo = min(por_frame), max(por_frame)
        paso = round(fps)  # cantidad de frames en un segundo

        def resumir_segundo(inicio: int) -> dict[str, float]:
            frames = range(inicio, min(inicio + paso, ultimo + 1))
            conteos = [len(por_frame.get(frame, [])) for frame in frames]
            velocidades = [v for frame in frames for v in por_frame.get(frame, [])]
            return {
                "tiempo": inicio / fps,
                "peatones": statistics.fmean(conteos),
                "densidad": statistics.fmean(conteos) / area.area,
                "velocidad_media": promedio(velocidades),
            }

        return list(map(resumir_segundo, range(primero, ultimo + 1, paso)))

    def _calcular_flujo(
        self,
        experimento: Experimento,
        sentido: int,
    ) -> tuple[list[dict[str, float]], list[float]]:
        """Serie de flujo J = N / Δt en la línea transversal; retorna también los instantes de cruce."""
        cruces = sorted(
            instante
            for trayectoria in experimento.trayectorias
            if (instante := instante_cruce(trayectoria, self._linea_flujo, sentido, experimento.fps))
            is not None
        )
        if not cruces:
            return [], []

        ancho = float(experimento.parametros.get("corridor width [m]", self._region.y_max - self._region.y_min))
        inicio = math.floor(cruces[0])
        por_intervalo = Counter(int((c - inicio) // self._ventana_flujo) for c in cruces)
        filas = [
            {
                "tiempo_inicio": inicio + i * self._ventana_flujo,
                "tiempo_fin": inicio + (i + 1) * self._ventana_flujo,
                "cruces": por_intervalo[i],
                "flujo": por_intervalo[i] / self._ventana_flujo,
                "flujo_especifico": por_intervalo[i] / self._ventana_flujo / ancho,
            }
            for i in range(max(por_intervalo) + 1)
        ]
        return filas, cruces

    def _tiempo_cruce_region(self, experimento: Experimento) -> float:
        """Tiempo medio [s] dentro de la región de análisis de quienes la recorren completa.

        A diferencia del tiempo total observado, no depende de cuánto del
        corredor cubre la cámara en cada corrida, por lo que es comparable.
        """
        region = self._region
        tiempos = [
            sum(region.contiene(o.x, o.y) for o in t.observaciones) / experimento.fps
            for t in experimento.trayectorias
            if min(o.x for o in t.observaciones) < region.x_min
            and max(o.x for o in t.observaciones) >= region.x_max
        ]
        return promedio(tiempos)

    def _resumir(
        self,
        experimento: Experimento,
        serie_densidad: list[dict[str, float]],
        cruces: list[float],
    ) -> dict[str, float]:
        """Indicadores colectivos del experimento a partir de las series calculadas."""
        ocupados = [fila for fila in serie_densidad if fila["peatones"] > 0]
        con_velocidad = [fila for fila in ocupados if not math.isnan(fila["velocidad_media"])]
        densidades = [fila["densidad"] for fila in con_velocidad]
        velocidades = [fila["velocidad_media"] for fila in con_velocidad]

        duracion_cruces = cruces[-1] - cruces[0] if len(cruces) > 1 else 0.0
        flujo = (len(cruces) - 1) / duracion_cruces if duracion_cruces > 0 else 0.0
        ancho = float(experimento.parametros.get("corridor width [m]", self._region.y_max - self._region.y_min))
        return {
            "peatones": len(experimento.trayectorias),
            "tiempo_cruce_region": self._tiempo_cruce_region(experimento),
            "densidad_media": promedio([fila["densidad"] for fila in ocupados]),
            "densidad_maxima": max((fila["densidad"] for fila in ocupados), default=0.0),
            "velocidad_media_area": promedio(velocidades),
            "correlacion_densidad_velocidad": correlacion(densidades, velocidades),
            "cruces_linea": len(cruces),
            "flujo": flujo,
            "flujo_especifico": flujo / ancho,
        }
