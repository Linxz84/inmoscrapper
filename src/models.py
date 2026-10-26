"""Modelos de datos del buscador de inmuebles y lista maestra de barrios.

Contiene:
- BARRIOS_VALIDOS: lista maestra hardcodeada de los 14 barrios objetivo de CABA.
- Propiedad: dataclass de una propiedad parseada de un aviso.
- Criterios: dataclass de filtros con metodo cumple(propiedad).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Lista maestra hardcodeada de los 14 barrios objetivo de CABA (barrios completos,
# sin divisiones en sub-zonas).
BARRIOS_VALIDOS: list[str] = [
    "Flores",
    "Floresta",
    "Villa del Parque",
    "Santa Rita",
    "Paternal",
    "Devoto",
    "Villa Pueyrredon",
    "Villa Urquiza",
    "Villa Crespo",
    "Almagro",
    "Parque Centenario",
    "Caballito",
    "Coghlan",
    "Monte Castro",
]

TipoPropiedad = Literal["casa", "PH", "departamento"]


@dataclass
class Propiedad:
    """Una propiedad inmobiliaria parseada a partir de un aviso de portal."""

    portal: str
    barrio: str
    tipo: TipoPropiedad = "departamento"
    ambientes: int = 0
    metros2: float = 0.0
    precio_usd: float | None = None
    moneda_original: str = "USD"
    precio_original: str | None = None
    direccion: str = ""
    tiene_balcon: bool = False
    tiene_patio: bool = False
    escalera_sin_ascensor: bool = False
    apto_credito: bool = False
    es_excepcion: bool = False
    imagen_url: str = ""
    url: str = ""
    fecha_publicacion: str = ""
    descripcion: str = ""

    def to_dict(self) -> dict:
        """Devuelve la propiedad como diccionario plano para exportación."""
        return {
            "portal": self.portal,
            "barrio": self.barrio,
            "tipo": self.tipo,
            "ambientes": self.ambientes,
            "metros2": self.metros2,
            "precio_usd": self.precio_usd,
            "moneda_original": self.moneda_original,
            "precio_original": self.precio_original,
            "direccion": self.direccion,
            "tiene_balcon": self.tiene_balcon,
            "tiene_patio": self.tiene_patio,
            "escalera_sin_ascensor": self.escalera_sin_ascensor,
            "apto_credito": self.apto_credito,
            "es_excepcion": self.es_excepcion,
            "imagen_url": self.imagen_url,
            "url": self.url,
            "fecha_publicacion": self.fecha_publicacion,
            "descripcion": self.descripcion,
        }

    def resumen(self) -> str:
        """Devuelve una linea resumen legible de la propiedad."""
        if self.precio_usd is None:
            precio = "sin precio"
        else:
            precio = f"USD {self.precio_usd:,.0f}"
        return (
            f"{self.tipo} | {self.barrio} | {self.ambientes} amb | "
            f"{self.metros2:g} m2 | {precio} | {self.portal} | {self.url}"
        )


@dataclass
class Criterios:
    """Criterios estrictos de filtrado de propiedades.

    Atributos con los valores por defecto del requerimiento.
    """

    tipos: list[str] | None = None
    ambientes_min: int = 3
    metros_min: float = 50.0
    precio_max_usd: float = 120_000.0
    requiere_balcon_o_patio: bool = True
    excluir_escalera: bool = True
    requiere_apto_credito: bool = False
    excluir_departamento_nuevo: bool = True
    excluir_departamento_pozo: bool = True
    moneda_objetivo: str = "USD"
    tipo_cambio_ars_usd: float = 1300.0

    def cumple(self, propiedad: Propiedad) -> tuple[bool, str]:
        """Evalua si la propiedad cumple TODOS los criterios.

        Devuelve (cumple, motivo). Cuando no cumple, motivo explica el rechazo.
        La escalera sin ascensor NO rechaza: se incluye con es_excepcion=True y
        se devuelve motivo indicando la excepcion (nunca se descarta silenciosamente).
        """
        if self.tipos is not None and propiedad.tipo not in self.tipos:
            return False, f"tipo '{propiedad.tipo}' no permitido"

        if propiedad.ambientes < self.ambientes_min:
            return False, (
                f"ambientes {propiedad.ambientes} < {self.ambientes_min}"
            )

        if propiedad.metros2 < self.metros_min:
            return False, (
                f"superficie {propiedad.metros2:g} m2 < {self.metros_min:g} m2"
            )

        if self.requiere_balcon_o_patio and not (
            propiedad.tiene_balcon or propiedad.tiene_patio
        ):
            return False, "sin balcon, terraza ni patio"

        if propiedad.precio_usd is None:
            return False, "precio no parseable"

        if propiedad.precio_usd > self.precio_max_usd:
            return False, (
                f"precio USD {propiedad.precio_usd:,.0f} > "
                f"{self.precio_max_usd:,.0f}"
            )

        if self.excluir_escalera and propiedad.escalera_sin_ascensor:
            propiedad.es_excepcion = True
            return True, "excepcion: acceso por escalera / sin ascensor"

        # Import diferido para evitar import circular con src.filters.
        from .filters import (
            detectar_departamento_nuevo,
            detectar_departamento_pozo,
        )

        if self.excluir_departamento_nuevo and detectar_departamento_nuevo(
            propiedad.descripcion
        ):
            return False, "departamento nuevo / a estrenar (excluido)"

        if self.excluir_departamento_pozo and detectar_departamento_pozo(
            propiedad.descripcion
        ):
            return False, "departamento de pozo / preventa (excluido)"

        if self.requiere_apto_credito and not propiedad.apto_credito:
            return False, "no apto credito (requerido)"

        return True, ""
