"""Etapa de comparación de experimentos."""

import math
import statistics
from collections import defaultdict

from models.experimento import Experimento
from models.resultado_analisis import ResultadoAnalisis
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline
from stages.espacial import correlacion, promedio

# Niveles de servicio de Fruin (1971) para pasillos: densidad máxima [1/m²] de cada nivel.
NIVELES_SERVICIO = (("A", 0.31), ("B", 0.43), ("C", 0.72), ("D", 1.08), ("E", 2.17), ("F", math.inf))
# Parámetros del diagrama fundamental de Weidmann (1993).
VELOCIDAD_LIBRE = 1.34  # m/s
GAMMA_WEIDMANN = 1.913  # 1/m²
DENSIDAD_MAXIMA = 5.4  # 1/m²


def nivel_servicio(densidad: float) -> str:
    """Nivel de servicio (A = flujo libre, F = congestión) según la densidad."""
    return next(nivel for nivel, limite in NIVELES_SERVICIO if densidad <= limite)


def velocidad_weidmann(densidad: float) -> float:
    """Velocidad esperada [m/s] para una densidad según el modelo de Weidmann (1993)."""
    if densidad <= 0:
        return VELOCIDAD_LIBRE
    exponente = -GAMMA_WEIDMANN * (1 / densidad - 1 / DENSIDAD_MAXIMA)
    return max(0.0, VELOCIDAD_LIBRE * (1 - math.exp(exponente)))


def segundos_validos(experimento: Experimento) -> list[dict[str, float]]:
    """Segundos de la serie de densidad con peatones en el área y velocidad definida."""
    return [
        fila for fila in experimento.serie_densidad
        if fila["peatones"] > 0 and not math.isnan(fila["velocidad_media"])
    ]


class ComparacionExperimentos(
    EtapaPipeline[list[Experimento], ResultadoAnalisis]
):
    """Compara resultados de varios experimentos."""

    def __init__(self, ancho_densidad: float = 0.25, muestras_minimas: int = 5) -> None:
        """
        Args:
            ancho_densidad: ancho [1/m²] de los rangos de densidad del diagrama fundamental.
            muestras_minimas: segundos mínimos para incluir un rango en el diagrama.
        """
        self._ancho_densidad = ancho_densidad
        self._muestras_minimas = muestras_minimas

    def ejecutar(
        self,
        experimentos: list[Experimento],
        contexto: ContextoPipeline,
    ) -> ResultadoAnalisis:
        """Retorna los experimentos junto con sus resultados comparativos."""
        resumen = [self._resumir(experimento) for experimento in experimentos]
        diagrama = self._diagrama_fundamental(experimentos)
        resultado = ResultadoAnalisis(
            experimentos=experimentos,
            resumen=resumen,
            diagrama_fundamental=diagrama,
            comparacion=self._comparar(experimentos, resumen, diagrama),
        )
        print("  exp  entrada/salida  peatones  v[m/s]  ρ[1/m²]  nivel  J[1/s]  detenido[%]")
        for fila in resumen:
            print(
                f"  {fila['experimento'][-2:]}   {fila['ancho_entrada']:g} m / {fila['ancho_salida']:g} m"
                f"      {fila['peatones']:>4}    {fila['velocidad_media']:.2f}    "
                f"{fila['densidad_media']:.2f}     {fila['nivel_servicio']}     "
                f"{fila['flujo']:.2f}   {fila['porcentaje_detenido_medio']:5.1f}"
            )
        return resultado

    def _resumir(self, experimento: Experimento) -> dict[str, float | str]:
        """Fila de resumen de un experimento: indicadores individuales promediados y colectivos."""
        individuales = list(experimento.resultados_individuales.values())

        def media(clave: str) -> float:
            return statistics.fmean(r[clave] for r in individuales)

        colectivos = experimento.resultados_colectivos
        parametros = experimento.parametros
        segundos = segundos_validos(experimento)
        return {
            "experimento": experimento.nombre,
            "ancho_entrada": float(parametros.get("entrance width [m]", math.nan)),
            "ancho_salida": float(parametros.get("exit width [m]", math.nan)),
            "sentido": parametros.get("movement_direction", ""),
            "fps": experimento.fps,
            "peatones": colectivos["peatones"],
            "velocidad_media": media("velocidad_media"),
            "velocidad_maxima_media": media("velocidad_maxima"),
            "distancia_media": media("distancia_total"),
            "desplazamiento_medio": media("desplazamiento"),
            "tiempo_medio": media("tiempo_total"),
            "tiempo_cruce_region": colectivos["tiempo_cruce_region"],
            "eficiencia_media": media("eficiencia"),
            "detenciones_media": media("detenciones"),
            "porcentaje_detenido_medio": media("porcentaje_detenido"),
            "densidad_media": colectivos["densidad_media"],
            "densidad_maxima": colectivos["densidad_maxima"],
            "nivel_servicio": nivel_servicio(colectivos["densidad_media"]),
            "velocidad_media_area": colectivos["velocidad_media_area"],
            "correlacion_densidad_velocidad": colectivos["correlacion_densidad_velocidad"],
            "flujo": colectivos["flujo"],
            "flujo_especifico": colectivos["flujo_especifico"],
            # Relación hidrodinámica Js = ρ·v, para contrastar con el flujo medido en la línea.
            "flujo_especifico_rho_v": promedio([f["densidad"] * f["velocidad_media"] for f in segundos]),
        }

    def _diagrama_fundamental(self, experimentos: list[Experimento]) -> list[dict[str, float]]:
        """Velocidad media y flujo específico por rango de densidad, con todas las corridas juntas."""
        por_rango: defaultdict[int, list[tuple[float, float]]] = defaultdict(list)
        for experimento in experimentos:
            for fila in segundos_validos(experimento):
                rango = int(fila["densidad"] // self._ancho_densidad)
                por_rango[rango].append((fila["densidad"], fila["velocidad_media"]))

        def resumir_rango(rango: int) -> dict[str, float]:
            densidades, velocidades = zip(*por_rango[rango])
            densidad = statistics.fmean(densidades)
            velocidad = statistics.fmean(velocidades)
            return {
                "densidad_min": rango * self._ancho_densidad,
                "densidad_max": (rango + 1) * self._ancho_densidad,
                "densidad_media": densidad,
                "segundos": len(velocidades),
                "velocidad_media": velocidad,
                "velocidad_desviacion": statistics.stdev(velocidades) if len(velocidades) > 1 else 0.0,
                "flujo_especifico": densidad * velocidad,
                "velocidad_weidmann": velocidad_weidmann(densidad),
            }

        rangos = sorted(r for r, muestras in por_rango.items() if len(muestras) >= self._muestras_minimas)
        return list(map(resumir_rango, rangos))

    def _comparar(
        self,
        experimentos: list[Experimento],
        resumen: list[dict[str, float | str]],
        diagrama: list[dict[str, float]],
    ) -> dict[str, float | str]:
        """Indicadores globales que relacionan las condiciones experimentales."""
        segundos = [fila for experimento in experimentos for fila in segundos_validos(experimento)]
        mayor_flujo = max(resumen, key=lambda fila: fila["flujo"])
        mas_congestionado = max(resumen, key=lambda fila: fila["densidad_media"])
        errores = [(f["velocidad_media"] - f["velocidad_weidmann"]) ** 2 for f in diagrama]
        return {
            "correlacion_densidad_velocidad_segundos": correlacion(
                [f["densidad"] for f in segundos], [f["velocidad_media"] for f in segundos]
            ),
            "correlacion_densidad_velocidad_experimentos": correlacion(
                [f["densidad_media"] for f in resumen], [f["velocidad_media"] for f in resumen]
            ),
            "experimento_mayor_flujo": mayor_flujo["experimento"],
            "flujo_maximo": mayor_flujo["flujo"],
            "flujo_especifico_maximo": mayor_flujo["flujo_especifico"],
            "densidad_en_flujo_maximo": mayor_flujo["densidad_media"],
            "experimento_mas_congestionado": mas_congestionado["experimento"],
            "densidad_media_maxima": mas_congestionado["densidad_media"],
            "rmse_weidmann": math.sqrt(promedio(errores)),
        }
