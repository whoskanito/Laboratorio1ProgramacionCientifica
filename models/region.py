"""Región rectangular del espacio de análisis."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """Rectángulo alineado con los ejes, usado como zona o área de medición."""

    nombre: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    @property
    def area(self) -> float:
        """Área de la región en m²."""
        return (self.x_max - self.x_min) * (self.y_max - self.y_min)

    def contiene(self, x: float, y: float) -> bool:
        """Indica si el punto (x, y) está dentro de la región (borde superior abierto)."""
        return self.x_min <= x < self.x_max and self.y_min <= y < self.y_max

    def dividir_en_x(self, ancho: float) -> list["Region"]:
        """Divide la región en franjas transversales de ``ancho`` metros a lo largo de x."""
        cantidad = round((self.x_max - self.x_min) / ancho)
        return [
            Region(
                nombre=f"{self.nombre}_{i + 1}",
                x_min=self.x_min + i * ancho,
                x_max=self.x_min + (i + 1) * ancho,
                y_min=self.y_min,
                y_max=self.y_max,
            )
            for i in range(cantidad)
        ]
