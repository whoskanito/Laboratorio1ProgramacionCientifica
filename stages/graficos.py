"""Etapa de generación de figuras para el informe."""

import math
from pathlib import Path

from models.experimento import Experimento
from models.region import Region
from models.resultado_analisis import ResultadoAnalisis
from pipeline.contexto import ContextoPipeline
from pipeline.etapa import EtapaPipeline
from stages.colectivo import segundos_validos, velocidad_weidmann
from stages.espacial import AREA_MEDICION, REGION_ANALISIS

try:
    import matplotlib

    matplotlib.use("Agg")  # sin ventana: permite generar figuras en un servidor sin pantalla
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch, Rectangle
except ImportError:  # el resto del pipeline funciona sin gráficos
    plt = None

# Paleta: un color para los datos, otro para el modelo de referencia y grises para el contexto.
SUPERFICIE = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_TENUE = "#898781"
GRILLA = "#e1e0d9"
EJE = "#c3c2b7"
AZUL = "#2a78d6"
AZUL_CLARO = "#cde2fb"
NARANJO = "#eb6834"
RAMPA_AZUL = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

ESTILO = {
    "figure.facecolor": SUPERFICIE,
    "axes.facecolor": SUPERFICIE,
    "savefig.facecolor": SUPERFICIE,
    "savefig.dpi": 200,
    "font.size": 9,
    "axes.edgecolor": EJE,
    "axes.linewidth": 0.8,
    "axes.labelcolor": TINTA_SECUNDARIA,
    "axes.titlecolor": TINTA,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRILLA,
    "grid.linewidth": 0.6,
    "xtick.color": EJE,
    "ytick.color": EJE,
    "xtick.labelcolor": TINTA_SECUNDARIA,
    "ytick.labelcolor": TINTA_SECUNDARIA,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.frameon": False,
    "legend.fontsize": 8,
    "figure.titlesize": 12,
}


def numero_corrida(nombre: str) -> str:
    """'uni_corr_500_05' → '05'."""
    return nombre.rsplit("_", 1)[-1]


def guardar(figura, ruta: Path) -> None:
    """Guarda la figura recortando márgenes y libera su memoria."""
    figura.savefig(ruta, bbox_inches="tight")
    plt.close(figura)


def cuadricula(cantidad: int, **opciones):
    """Crea una grilla de 3 columnas con un panel por experimento (small multiples)."""
    filas = math.ceil(cantidad / 3)
    figura, ejes = plt.subplots(filas, 3, squeeze=False, **opciones)
    ejes = ejes.ravel()
    for eje in ejes[cantidad:]:
        eje.set_visible(False)
    return figura, ejes[:cantidad]


def rotular_bordes(ejes, etiqueta_x: str, etiqueta_y: str) -> None:
    """Rotula solo los ejes exteriores de una grilla de 3 columnas."""
    for eje in ejes[-3:]:
        eje.set_xlabel(etiqueta_x)
    for eje in ejes[::3]:
        eje.set_ylabel(etiqueta_y)


def rectangulo(region: Region, **opciones) -> "Rectangle":
    """Parche de matplotlib que dibuja una región."""
    return Rectangle(
        (region.x_min, region.y_min),
        region.x_max - region.x_min,
        region.y_max - region.y_min,
        **opciones,
    )


class GeneracionGraficos(EtapaPipeline[ResultadoAnalisis, None]):
    """Genera las figuras del informe a partir de los resultados calculados."""

    def ejecutar(
        self,
        resultados: ResultadoAnalisis,
        contexto: ContextoPipeline,
    ) -> None:
        """Guarda las figuras en la subcarpeta ``figuras`` del directorio de salida."""
        if plt is None:
            print("  Aviso: matplotlib no está instalado; se omiten las figuras (pip install -r requirements.txt).")
            return None

        carpeta = contexto.ruta_salida / "figuras"
        carpeta.mkdir(parents=True, exist_ok=True)
        resumen = {fila["experimento"]: fila for fila in resultados.resumen}
        self._titulos = {
            nombre: f"{numero_corrida(nombre)} · entrada {fila['ancho_entrada']:g} m / salida {fila['ancho_salida']:g} m"
            for nombre, fila in resumen.items()
        }
        self._etiquetas = [
            f"{numero_corrida(nombre)}\n{fila['ancho_entrada']:g}/{fila['ancho_salida']:g}"
            for nombre, fila in resumen.items()
        ]
        linea_flujo = contexto.parametros.get("linea_flujo", 0.0)

        figuras = {
            "trayectorias.png": lambda: self._trayectorias(resultados.experimentos, linea_flujo),
            "densidad_tiempo.png": lambda: self._densidad_tiempo(resultados.experimentos),
            "flujo_tiempo.png": lambda: self._flujo_tiempo(resultados.experimentos),
            "diagrama_fundamental.png": lambda: self._diagrama_fundamental(resultados),
            "zonas.png": lambda: self._zonas(resultados.experimentos),
            "comparacion_experimentos.png": lambda: self._comparacion(resultados.resumen),
            "distribuciones_individuales.png": lambda: self._distribuciones(resultados.experimentos),
        }
        with plt.rc_context(ESTILO):
            for nombre, crear in figuras.items():
                guardar(crear(), carpeta / nombre)
        print(f"  {len(figuras)} figuras en {carpeta}: {', '.join(figuras)}")
        return None

    def _trayectorias(self, experimentos: list[Experimento], linea_flujo: float):
        """Una muestra de trayectorias por corrida, con la región, el área y la línea de flujo."""
        figura, ejes = cuadricula(len(experimentos), figsize=(13, 6.4), sharex=True, sharey=True)
        for eje, experimento in zip(ejes, experimentos):
            paso = max(1, len(experimento.trayectorias) // 80)
            for trayectoria in experimento.trayectorias[::paso]:
                eje.plot(
                    [o.x for o in trayectoria.observaciones],
                    [o.y for o in trayectoria.observaciones],
                    color=AZUL, linewidth=0.5, alpha=0.45,
                )
            eje.add_patch(rectangulo(AREA_MEDICION, facecolor=TINTA_TENUE, alpha=0.15, edgecolor="none"))
            eje.add_patch(rectangulo(REGION_ANALISIS, fill=False, edgecolor=TINTA_SECUNDARIA, linewidth=1))
            eje.axvline(linea_flujo, color=NARANJO, linewidth=1.2)
            eje.set_title(self._titulos[experimento.nombre])
            eje.set_xlim(-10, 10)
            eje.set_ylim(-1, 6)
            eje.set_aspect("equal")
        rotular_bordes(ejes, "x [m]", "y [m]")
        figura.legend(
            handles=[
                Line2D([], [], color=AZUL, linewidth=1, label="trayectoria (muestra de ~80 por corrida)"),
                Patch(fill=False, edgecolor=TINTA_SECUNDARIA, label="región analizada (zonas)"),
                Patch(facecolor=TINTA_TENUE, alpha=0.3, label=f"área de medición ({AREA_MEDICION.area:g} m²)"),
                Line2D([], [], color=NARANJO, linewidth=1.2, label="línea de flujo"),
            ],
            loc="lower center", ncol=4, bbox_to_anchor=(0.5, -0.04),
        )
        figura.suptitle("Trayectorias observadas en cada corrida")
        return figura

    def _densidad_tiempo(self, experimentos: list[Experimento]):
        """Serie de densidad ρ(t) de cada corrida, con su media."""
        figura, ejes = cuadricula(len(experimentos), figsize=(13, 7.5), sharex=True, sharey=True)
        for eje, experimento in zip(ejes, experimentos):
            serie = experimento.serie_densidad
            eje.plot([f["tiempo"] for f in serie], [f["densidad"] for f in serie], color=AZUL, linewidth=1.4)
            media = experimento.resultados_colectivos["densidad_media"]
            eje.axhline(media, color=TINTA_TENUE, linewidth=1)
            eje.annotate(
                f"media {media:.2f}", xy=(1, media), xycoords=("axes fraction", "data"),
                xytext=(0, 3), textcoords="offset points", ha="right", va="bottom",
                fontsize=8, color=TINTA_SECUNDARIA,
            )
            eje.set_title(self._titulos[experimento.nombre])
        rotular_bordes(ejes, "Tiempo [s]", r"Densidad $\rho$ [1/m²]")
        figura.suptitle(f"Densidad en el área de medición ({AREA_MEDICION.area:g} m²) durante cada corrida")
        figura.tight_layout()
        return figura

    def _flujo_tiempo(self, experimentos: list[Experimento]):
        """Serie de flujo J por intervalo en la línea transversal, con el flujo global."""
        figura, ejes = cuadricula(len(experimentos), figsize=(13, 7.5), sharex=True, sharey=True)
        for eje, experimento in zip(ejes, experimentos):
            serie = experimento.serie_flujo
            if serie:
                ventana = serie[0]["tiempo_fin"] - serie[0]["tiempo_inicio"]
                eje.bar(
                    [f["tiempo_inicio"] for f in serie], [f["flujo"] for f in serie],
                    width=0.85 * ventana, align="edge", color=AZUL,
                )
            flujo = experimento.resultados_colectivos["flujo"]
            eje.axhline(flujo, color=TINTA_TENUE, linewidth=1)
            eje.annotate(
                f"J global {flujo:.2f}", xy=(1, flujo), xycoords=("axes fraction", "data"),
                xytext=(0, 3), textcoords="offset points", ha="right", va="bottom",
                fontsize=8, color=TINTA_SECUNDARIA,
                bbox={"facecolor": SUPERFICIE, "edgecolor": "none", "pad": 1},
            )
            eje.set_title(self._titulos[experimento.nombre])
            eje.grid(axis="x", visible=False)
        rotular_bordes(ejes, "Tiempo [s]", "Flujo J [1/s]")
        figura.suptitle("Flujo a través de la línea transversal, por intervalos de tiempo")
        figura.tight_layout()
        return figura

    def _diagrama_fundamental(self, resultados: ResultadoAnalisis):
        """Velocidad–densidad y flujo–densidad: datos, promedio por rango y modelo de Weidmann."""
        segundos = [f for e in resultados.experimentos for f in segundos_validos(e)]
        densidades = [f["densidad"] for f in segundos]
        velocidades = [f["velocidad_media"] for f in segundos]
        diagrama = resultados.diagrama_fundamental
        rangos = [f["densidad_media"] for f in diagrama]
        curva = [i * 0.05 for i in range(2, 91)]

        figura, (eje_v, eje_j) = plt.subplots(1, 2, figsize=(12.5, 4.8))

        eje_v.scatter(densidades, velocidades, s=5, color=EJE, alpha=0.6, linewidths=0,
                      label="un segundo de una corrida")
        eje_v.fill_between(
            rangos,
            [f["velocidad_media"] - f["velocidad_desviacion"] for f in diagrama],
            [f["velocidad_media"] + f["velocidad_desviacion"] for f in diagrama],
            color=AZUL, alpha=0.15, linewidth=0, label="± 1 desviación estándar",
        )
        eje_v.plot(rangos, [f["velocidad_media"] for f in diagrama], color=AZUL, marker="o",
                   markersize=4, label="promedio por rango de densidad")
        eje_v.plot(curva, [velocidad_weidmann(r) for r in curva], color=NARANJO, linewidth=1.5,
                   linestyle="--", label="modelo de Weidmann (1993)")
        puntos_v = [(f["densidad_media"], f["velocidad_media_area"], f["experimento"]) for f in resultados.resumen]
        self._marcar_corridas(eje_v, puntos_v, "media de cada corrida")
        eje_v.set_xlabel(r"Densidad $\rho$ [1/m²]")
        eje_v.set_ylabel("Velocidad v [m/s]")
        eje_v.set_title("Velocidad en función de la densidad")
        eje_v.set_ylim(bottom=0)
        eje_v.legend(loc="upper right")

        eje_j.scatter(densidades, [r * v for r, v in zip(densidades, velocidades)], s=5, color=EJE,
                      alpha=0.6, linewidths=0, label=r"$\rho \cdot v$ de un segundo")
        eje_j.plot(rangos, [f["flujo_especifico"] for f in diagrama], color=AZUL, marker="o",
                   markersize=4, label=r"$\rho \cdot v$ promedio por rango")
        eje_j.plot(curva, [r * velocidad_weidmann(r) for r in curva], color=NARANJO, linewidth=1.5,
                   linestyle="--", label="modelo de Weidmann (1993)")
        puntos_j = [(f["densidad_media"], f["flujo_especifico"], f["experimento"]) for f in resultados.resumen]
        self._marcar_corridas(eje_j, puntos_j, "J/b medido en la línea, por corrida")
        eje_j.set_xlabel(r"Densidad $\rho$ [1/m²]")
        eje_j.set_ylabel(r"Flujo específico $J_s$ [1/(m·s)]")
        eje_j.set_title("Flujo específico en función de la densidad")
        eje_j.set_ylim(bottom=0)
        eje_j.legend(loc="upper left")

        figura.suptitle("Diagrama fundamental del corredor (todas las corridas)")
        figura.tight_layout()
        return figura

    @staticmethod
    def _marcar_corridas(eje, puntos: list[tuple[float, float, str]], etiqueta: str) -> None:
        """Dibuja un marcador por corrida con su número como etiqueta directa."""
        eje.scatter([p[0] for p in puntos], [p[1] for p in puntos], s=40, facecolor=SUPERFICIE,
                    edgecolor=TINTA, linewidth=1.2, zorder=5, label=etiqueta)
        # Alterna la etiqueta arriba y abajo para que corridas vecinas no se tapen.
        for indice, (x, y, nombre) in enumerate(puntos):
            desplazamiento = (5, 4) if indice % 2 == 0 else (-14, -12)
            eje.annotate(numero_corrida(nombre), (x, y), xytext=desplazamiento, textcoords="offset points",
                         fontsize=8, color=TINTA, zorder=6)

    def _zonas(self, experimentos: list[Experimento]):
        """Mapas de calor de velocidad y densidad por zona (filas: corridas; columnas: zonas)."""
        rampa = LinearSegmentedColormap.from_list("azul", RAMPA_AZUL)
        figura, ejes = plt.subplots(1, 2, figsize=(13, 5))
        filas = [f"{numero_corrida(e.nombre)}" for e in experimentos]
        for eje, clave, titulo, unidad in (
            (ejes[0], "velocidad_media", "Velocidad media por zona", "m/s"),
            (ejes[1], "densidad_media", "Densidad media por zona", "1/m²"),
        ):
            matriz = [[zona[clave] for zona in e.resultados_zonas] for e in experimentos]
            malla = eje.pcolormesh(matriz, cmap=rampa, edgecolors=SUPERFICIE, linewidth=1.5)
            minimo, maximo = malla.get_clim()
            for i, fila in enumerate(matriz):
                for j, valor in enumerate(fila):
                    if math.isnan(valor):
                        continue
                    oscuro = (valor - minimo) / (maximo - minimo) > 0.55 if maximo > minimo else False
                    eje.text(j + 0.5, i + 0.5, f"{valor:.2f}", ha="center", va="center", fontsize=7,
                             color="white" if oscuro else TINTA)
            columnas = len(matriz[0]) if matriz else 0
            eje.set_xticks([j + 0.5 for j in range(columnas)], [str(j + 1) for j in range(columnas)])
            eje.set_yticks([i + 0.5 for i in range(len(filas))], self._etiquetas_filas(experimentos))
            eje.invert_yaxis()
            eje.grid(False)
            eje.tick_params(length=0)
            eje.set_xlabel("Zona (1 = más cercana a la entrada; franjas de 1 m)")
            eje.set_ylabel("Corrida (entrada/salida en m)")
            eje.set_title(titulo)
            figura.colorbar(malla, ax=eje, label=f"{titulo.split(' por')[0]} [{unidad}]", shrink=0.85)
        figura.suptitle("Análisis por zonas del tramo observado (x de -5 a 4 m)")
        figura.tight_layout()
        return figura

    def _etiquetas_filas(self, experimentos: list[Experimento]) -> list[str]:
        """Etiquetas de una línea con número de corrida y anchos: '05 (5/5)'."""
        return [etiqueta.replace("\n", " (") + ")" for etiqueta in self._etiquetas[: len(experimentos)]]

    def _comparacion(self, resumen: list[dict[str, float | str]]):
        """Barras por corrida de los indicadores agregados que pide la comparación."""
        metricas = (
            ("velocidad_media", "Velocidad media [m/s]"),
            ("densidad_media", "Densidad media [1/m²]"),
            ("flujo", "Flujo J [1/s]"),
            ("distancia_media", "Distancia media recorrida [m]"),
            ("tiempo_cruce_region", "Tiempo medio en cruzar el tramo de 9 m [s]"),
            ("porcentaje_detenido_medio", "Tiempo detenido promedio [%]"),
        )
        figura, ejes = plt.subplots(2, 3, figsize=(13, 6.5), sharex=True)
        posiciones = range(len(resumen))
        for eje, (clave, titulo) in zip(ejes.ravel(), metricas):
            eje.bar(posiciones, [fila[clave] for fila in resumen], color=AZUL, width=0.7)
            eje.set_title(titulo)
            eje.grid(axis="x", visible=False)
            eje.set_xticks(list(posiciones), self._etiquetas)
        for eje in ejes[-1]:
            eje.set_xlabel("Corrida (ancho de entrada/salida en m)")
        figura.suptitle("Comparación de las condiciones experimentales")
        figura.tight_layout()
        return figura

    def _distribuciones(self, experimentos: list[Experimento]):
        """Diagramas de caja de los indicadores individuales en cada corrida."""
        metricas = (
            ("velocidad_media", "Velocidad media [m/s]"),
            ("eficiencia", "Eficiencia E = D / Dr"),
            ("porcentaje_detenido", "Tiempo detenido [%]"),
        )
        figura, ejes = plt.subplots(1, 3, figsize=(13, 4.4))
        for eje, (clave, titulo) in zip(ejes, metricas):
            datos = [[r[clave] for r in e.resultados_individuales.values()] for e in experimentos]
            eje.boxplot(
                datos, patch_artist=True, widths=0.6,
                boxprops={"facecolor": AZUL_CLARO, "edgecolor": AZUL},
                medianprops={"color": TINTA, "linewidth": 1.5},
                whiskerprops={"color": AZUL},
                capprops={"color": AZUL},
                flierprops={"marker": "o", "markersize": 2, "markerfacecolor": TINTA_TENUE,
                            "markeredgecolor": "none", "alpha": 0.5},
            )
            eje.set_xticks(range(1, len(datos) + 1), self._etiquetas[: len(datos)])
            eje.set_title(titulo)
            eje.set_xlabel("Corrida (entrada/salida en m)")
            eje.grid(axis="x", visible=False)
        figura.suptitle("Diferencias entre peatones: distribución de los indicadores individuales")
        figura.tight_layout()
        return figura
