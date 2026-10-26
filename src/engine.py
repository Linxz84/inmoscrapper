"""Motor de búsqueda de propiedades.

Orquesta la consulta a los portales, la validación de barrios, la
deduplicación por URL y el filtrado de criterios. Incluye un modo demo
con datos sintéticos fijos que permite probar todo el pipeline sin internet.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import yaml

from src.models import BARRIOS_VALIDOS, Criterios, Propiedad

logger = logging.getLogger(__name__)


@dataclass
class ResultadoBusqueda:
    """Resultado de una corrida de búsqueda."""

    propiedades: list[Propiedad] = field(default_factory=list)
    aceptadas: list[Propiedad] = field(default_factory=list)
    rechazadas: list[tuple[Propiedad, str]] = field(default_factory=list)
    excepciones: list[Propiedad] = field(default_factory=list)
    portales_fallidos: list[str] = field(default_factory=list)
    total_revisadas: int = 0


class MotorBusqueda:
    """Motor de búsqueda de propiedades.

    Coordina scrapers por portal, valida barrios, deduplica por URL y
    aplica los criterios de filtrado. Soporta modo demo con datos fijos.
    """

    def __init__(self, scrapers: dict[str, object] | None = None):
        self.scrapers = scrapers or {}
        self.portales_fallidos: list[str] = []

    # ------------------------------------------------------------------
    # Validación y normalización de barrios
    # ------------------------------------------------------------------

    @staticmethod
    def validar_barrios(barrios: list[str]) -> list[str]:
        """Valida, normaliza y deduplica una lista de barrios.

        Rechaza nombres fuera de BARRIOS_VALIDOS, normaliza (strip y
        comparación exacta contra la lista maestra) y elimina duplicados
        ya normalizados, registrando en logs lo descartado.
        """
        validos: list[str] = []
        vistos: set[str] = set()
        for barrio in barrios:
            nombre = barrio.strip()
            if nombre not in BARRIOS_VALIDOS:
                logger.warning(
                    "Barrio '%s' no está en la lista maestra de barrios válidos: %s",
                    nombre,
                    BARRIOS_VALIDOS,
                )
                continue
            if nombre in vistos:
                logger.info("Barrio duplicado descartado: %s", nombre)
                continue
            vistos.add(nombre)
            validos.append(nombre)
        return validos

    # ------------------------------------------------------------------
    # Modo demo (dataset sintético fijo, sin random)
    # ------------------------------------------------------------------

    def _dataset_demo(self) -> list[Propiedad]:
        """Dataset sintético fijo de 7 propiedades.

        1. Válida con balcón             -> aceptada
        2. Válida con patio              -> aceptada
        3. Superficie < 50 m2            -> rechazada
        4. Precio > USD 120.000          -> rechazada
        5. Por escalera / sin ascensor   -> excepción (aceptada con es_excepcion)
        6. "a estrenar"                  -> rechazada (departamento nuevo)
        7. "de pozo" / entrega 2028      -> rechazada (departamento de pozo)
        """
        return [
            Propiedad(
                portal="demo",
                barrio="Caballito",
                tipo="departamento",
                ambientes=3,
                metros2=60.0,
                precio_usd=100000.0,
                moneda_original="USD",
                precio_original="100.000",
                direccion="Rivadavia 6000",
                tiene_balcon=True,
                tiene_patio=False,
                escalera_sin_ascensor=False,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/1",
                fecha_publicacion="2026-01-10",
                descripcion="Luminoso departamento con balcón al frente",
            ),
            Propiedad(
                portal="demo",
                barrio="Floresta",
                tipo="PH",
                ambientes=4,
                metros2=80.0,
                precio_usd=110000.0,
                moneda_original="USD",
                precio_original="110.000",
                direccion="Av. Ramón Falcón 3000",
                tiene_balcon=False,
                tiene_patio=True,
                escalera_sin_ascensor=False,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/2",
                fecha_publicacion="2026-01-11",
                descripcion="PH con patio propio y parrilla",
            ),
            Propiedad(
                portal="demo",
                barrio="Villa Crespo",
                tipo="departamento",
                ambientes=3,
                metros2=45.0,
                precio_usd=90000.0,
                moneda_original="USD",
                precio_original="90.000",
                direccion="Santa Fe 4500",
                tiene_balcon=True,
                tiene_patio=False,
                escalera_sin_ascensor=False,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/3",
                fecha_publicacion="2026-01-12",
                descripcion="Departamento 3 ambientes 45 m2",
            ),
            Propiedad(
                portal="demo",
                barrio="Almagro",
                tipo="departamento",
                ambientes=3,
                metros2=70.0,
                precio_usd=150000.0,
                moneda_original="USD",
                precio_original="150.000",
                direccion="Medrano 900",
                tiene_balcon=True,
                tiene_patio=False,
                escalera_sin_ascensor=False,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/4",
                fecha_publicacion="2026-01-13",
                descripcion="Departamento 3 ambientes, USD 150.000",
            ),
            Propiedad(
                portal="demo",
                barrio="Caballito",
                tipo="departamento",
                ambientes=3,
                metros2=60.0,
                precio_usd=100000.0,
                moneda_original="USD",
                precio_original="100.000",
                direccion="Rivadavia 6100",
                tiene_balcon=True,
                tiene_patio=False,
                escalera_sin_ascensor=True,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/5",
                fecha_publicacion="2026-01-14",
                descripcion="Departamento con balcón, acceso por escalera, sin ascensor",
            ),
            Propiedad(
                portal="demo",
                barrio="Devoto",
                tipo="departamento",
                ambientes=3,
                metros2=60.0,
                precio_usd=100000.0,
                moneda_original="USD",
                precio_original="100.000",
                direccion="Av. San Martín 4000",
                tiene_balcon=True,
                tiene_patio=False,
                escalera_sin_ascensor=False,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/6",
                fecha_publicacion="2026-01-15",
                descripcion="Departamento a estrenar, 3 ambientes, balcón",
            ),
            Propiedad(
                portal="demo",
                barrio="Villa Urquiza",
                tipo="departamento",
                ambientes=3,
                metros2=60.0,
                precio_usd=100000.0,
                moneda_original="USD",
                precio_original="100.000",
                direccion="Av. Triunvirato 5000",
                tiene_balcon=True,
                tiene_patio=False,
                escalera_sin_ascensor=False,
                apto_credito=False,
                es_excepcion=False,
                imagen_url="",
                url="https://demo.inmoscrapper.com/7",
                fecha_publicacion="2026-01-16",
                descripcion="Departamento de pozo, entrega 2028",
            ),
        ]

    def _filtrar(
        self, propiedades: list[Propiedad], criterios: Criterios
    ) -> ResultadoBusqueda:
        """Aplica criterios a una lista de propiedades y clasifica el resultado."""
        resultado = ResultadoBusqueda(propiedades=list(propiedades))
        resultado.total_revisadas = len(propiedades)
        urls_vistas: set[str] = set()
        for prop in propiedades:
            if prop.url and prop.url in urls_vistas:
                continue
            if prop.url:
                urls_vistas.add(prop.url)
            ok, motivo = criterios.cumple(prop)
            if ok:
                if prop.es_excepcion:
                    resultado.excepciones.append(prop)
                    logger.info(
                        "ACEPTADA (excepción): %s | motivo: %s",
                        prop.resumen(),
                        motivo,
                    )
                else:
                    resultado.aceptadas.append(prop)
                    logger.info("ACEPTADA: %s", prop.resumen())
            else:
                resultado.rechazadas.append((prop, motivo))
                logger.info(
                    "RECHAZADA: %s | motivo: %s",
                    prop.resumen(),
                    motivo,
                )
        return resultado

    def buscar_demo(self, criterios: Criterios) -> ResultadoBusqueda:
        """Ejecuta el modo demo con el dataset sintético fijo."""
        logger.info(
            "Modo demo activado: dataset sintético fijo de %d propiedades",
            len(self._dataset_demo()),
        )
        return self._filtrar(self._dataset_demo(), criterios)

    # ------------------------------------------------------------------
    # Búsqueda real (se conecta a scrapers; tolerante a fallos por portal)
    # ------------------------------------------------------------------

    def buscar(
        self,
        criterios: Criterios,
        portales: list[str],
        barrios: list[str],
        max_paginas: int = 2,
        modo_demo: bool = False,
    ) -> ResultadoBusqueda:
        """Busca propiedades aplicando filtros estrictos.

        Cuando ``modo_demo`` es True ignora portales/barrios y usa el
        dataset sintético fijo. De lo contrario itera sobre los portales
        habilitados, sus barrios y páginas, deduplica por URL y filtra.
        Un portal caído no tumba la búsqueda (se loguea y continúa).
        """
        if modo_demo:
            return self.buscar_demo(criterios)

        barrios_validos = self.validar_barrios(barrios)
        if not barrios_validos:
            logger.warning("No hay barrios válidos para buscar")
            return ResultadoBusqueda()

        todas: list[Propiedad] = []
        self.portales_fallidos = []
        for portal in portales:
            scraper = self.scrapers.get(portal)
            if scraper is None:
                logger.warning(
                    "Portal '%s' no tiene scraper registrado; se omite", portal
                )
                continue
            try:
                for barrio in barrios_validos:
                    for pagina in range(1, max_paginas + 1):
                        for prop in scraper.buscar(barrio, pagina):
                            todas.append(prop)
            except Exception as exc:  # tolerancia a fallos por portal
                logger.exception("Portal '%s' falló: %s", portal, exc)
                self.portales_fallidos.append(portal)
                continue

        return self._filtrar(todas, criterios)


def cargar_config(ruta: str = "config/config.yaml") -> dict:
    """Carga y valida config.yaml.

    Valida que cada barrio de la lista esté en BARRIOS_VALIDOS, sin
    duplicados, y que tenga slug no vacío para cada portal habilitado.
    Si un barrio tiene slug vacío o inválido para un portal habilitado:
    se loguea un warning y se saltea ese barrio para ese portal
    (no se tumba la carga completa).

    Retorna un diccionario con las secciones busqueda, barrios, portales,
    salida y barrios_validados.
    """
    with open(ruta, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    seccion_barrios = config.get("barrios", []) or []
    portales_cfg = config.get("portales", {}) or {}
    portales_habilitados = [
        p for p, c in portales_cfg.items() if c.get("habilitado", True)
    ]

    barrios_validados: list[str] = []
    vistos: set[str] = set()
    for entry in seccion_barrios:
        nombre = (entry.get("nombre") or "").strip()
        if nombre not in BARRIOS_VALIDOS:
            logger.warning("Barrio '%s' no está en la lista maestra: se omite", nombre)
            continue
        if nombre in vistos:
            logger.warning("Barrio duplicado '%s': se omite", nombre)
            continue
        slugs = entry.get("slugs") or {}
        slug_ok = True
        for portal in portales_habilitados:
            if not slugs.get(portal):
                logger.warning(
                    "Barrio '%s' sin slug para el portal '%s': se saltea para ese portal",
                    nombre,
                    portal,
                )
                slug_ok = False
        if slug_ok:
            vistos.add(nombre)
            barrios_validados.append(nombre)

    config["barrios_validados"] = barrios_validados
    return config
