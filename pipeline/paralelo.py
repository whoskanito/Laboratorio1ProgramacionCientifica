"""Ejecución en paralelo de etapas que procesan cada elemento por separado."""

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import reduce
from typing import Callable

from .contexto import ContextoPipeline
from .etapa import Elemento, EtapaPipeline, EtapaPorElemento


def aplicar_etapas(
    elemento: Elemento,
    etapas: list[EtapaPorElemento[Elemento]],
    contexto: ContextoPipeline,
) -> Elemento:
    """Aplica en orden cada etapa a un elemento; es lo que ejecuta cada proceso de trabajo."""
    return reduce(lambda actual, etapa: etapa.procesar(actual, contexto), etapas, elemento)


class ProcesamientoParalelo(EtapaPipeline[list[Elemento], list[Elemento]]):
    """Encadena etapas por elemento y reparte los elementos entre varios procesos.

    Se usan procesos y no hilos porque el trabajo es cálculo en Python puro:
    el GIL impide que dos hilos ejecuten código Python al mismo tiempo, en
    cambio cada proceso tiene su propio intérprete y usa su propio núcleo.
    Cada elemento recorre toda la cadena dentro de un mismo proceso, así los
    datos se transfieren entre procesos una sola vez.
    """

    def __init__(
        self,
        etapas: list[EtapaPorElemento[Elemento]],
        procesos: int | None = None,
        costo: Callable[[Elemento], float] | None = None,
    ) -> None:
        """
        Args:
            etapas: etapas que se aplican, en orden, a cada elemento.
            procesos: cantidad máxima de procesos (por defecto, uno por núcleo).
            costo: estimación del trabajo de cada elemento; los más costosos se
                envían primero para que el último en terminar no sea uno grande.
        """
        self._etapas = list(etapas)
        self._procesos = procesos or os.cpu_count() or 1
        self._costo = costo

    def ejecutar(self, entrada: list[Elemento], contexto: ContextoPipeline) -> list[Elemento]:
        """Procesa todos los elementos y luego informa lo hecho por cada etapa."""
        procesos = max(1, min(self._procesos, len(entrada)))
        inicio = time.perf_counter()
        if procesos == 1:
            resultados = [aplicar_etapas(elemento, self._etapas, contexto) for elemento in entrada]
        else:
            resultados = self._en_paralelo(entrada, contexto, procesos)
        nombres = " → ".join(type(etapa).__name__ for etapa in self._etapas)
        print(f"  {nombres}")
        print(f"  {len(entrada)} elementos en {procesos} proceso(s): {time.perf_counter() - inicio:.1f} s")
        for etapa in self._etapas:
            print(f"  {type(etapa).__name__}:")
            etapa.informar(resultados, sangria="    ")
        return resultados

    def _en_paralelo(
        self,
        elementos: list[Elemento],
        contexto: ContextoPipeline,
        procesos: int,
    ) -> list[Elemento]:
        """Reparte los elementos entre procesos y devuelve los resultados en el orden original."""
        orden = sorted(
            range(len(elementos)),
            key=lambda i: self._costo(elementos[i]) if self._costo else 0.0,
            reverse=True,
        )
        resultados: list[Elemento | None] = [None] * len(elementos)
        with ProcessPoolExecutor(max_workers=procesos) as ejecutor:
            futuros = {
                ejecutor.submit(aplicar_etapas, elementos[i], self._etapas, contexto): i
                for i in orden
            }
            # Se recibe cada resultado apenas termina, mientras los demás siguen calculando.
            for futuro in as_completed(futuros):
                resultados[futuros[futuro]] = futuro.result()
        return resultados
