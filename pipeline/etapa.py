"""Clase base para las etapas del pipeline."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from .contexto import ContextoPipeline

Entrada = TypeVar("Entrada")
Salida = TypeVar("Salida")
Elemento = TypeVar("Elemento")


class EtapaPipeline(ABC, Generic[Entrada, Salida]):
    """Interfaz genérica para etapas que transforman una entrada en una salida."""

    @abstractmethod
    def ejecutar(self, entrada: Entrada, contexto: ContextoPipeline) -> Salida:
        """Procesa una entrada de dominio usando la configuración de ejecución."""
        pass


class EtapaPorElemento(EtapaPipeline[list[Elemento], list[Elemento]]):
    """Etapa que procesa cada elemento de una lista de forma independiente.

    Como el resultado de un elemento no depende de los demás, varias de estas
    etapas pueden encadenarse y ejecutarse en paralelo con
    ``ProcesamientoParalelo``. ``procesar`` no debe imprimir: los mensajes se
    generan con ``describir`` en el proceso principal.
    """

    @abstractmethod
    def procesar(self, elemento: Elemento, contexto: ContextoPipeline) -> Elemento:
        """Retorna el elemento procesado."""
        pass

    def describir(self, elemento: Elemento) -> str:
        """Resumen de una línea del resultado de esta etapa para un elemento."""
        return ""

    def informar(self, elementos: list[Elemento], sangria: str = "  ") -> None:
        """Imprime la descripción de cada elemento procesado."""
        for elemento in elementos:
            if texto := self.describir(elemento):
                print(f"{sangria}{texto}")

    def ejecutar(self, entrada: list[Elemento], contexto: ContextoPipeline) -> list[Elemento]:
        """Procesa los elementos uno tras otro, en el proceso actual."""
        procesados = [self.procesar(elemento, contexto) for elemento in entrada]
        self.informar(procesados)
        return procesados
