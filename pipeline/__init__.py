"""Infraestructura para coordinar etapas de procesamiento."""

from .contexto import ContextoPipeline
from .etapa import EtapaPipeline, EtapaPorElemento
from .paralelo import ProcesamientoParalelo
from .pipeline import Pipeline

__all__ = [
    "ContextoPipeline",
    "EtapaPipeline",
    "EtapaPorElemento",
    "Pipeline",
    "ProcesamientoParalelo",
]
