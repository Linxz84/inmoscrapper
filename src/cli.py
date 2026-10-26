"""Interfaz de línea de comandos del buscador de inmuebles."""

from __future__ import annotations

import argparse
import logging
import sys

from src.engine import MotorBusqueda
from src.exporters import exportar_propiedades
from src.models import BARRIOS_VALIDOS, Criterios
from src.scrapers import ArgenpropScraper, MercadoLibreScraper, ZonaPropScraper

logger = logging.getLogger(__name__)

SCRAPERS_POR_PORTAL = {
    "zonaprop": ZonaPropScraper,
    "mercadolibre": MercadoLibreScraper,
    "argenprop": ArgenpropScraper,
}

PORTALES_DISPONIBLES = list(SCRAPERS_POR_PORTAL.keys())
FORMATOS_DISPONIBLES = ["csv", "json", "excel"]


def _configurar_logging(verbose: bool) -> None:
    nivel = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=nivel,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _validar_barrios(barrios: list[str] | None) -> list[str]:
    if not barrios:
        return []
    invalidos = [b for b in barrios if b not in BARRIOS_VALIDOS]
    if invalidos:
        logger.error(
            "Barrios inválidos: %s. Barrios válidos: %s", invalidos, BARRIOS_VALIDOS
        )
        sys.exit(1)
    return barrios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Buscador de inmuebles (CABA)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="modo demo con datos sintéticos fijos (sin internet)",
    )
    parser.add_argument(
        "--portales",
        nargs="+",
        choices=PORTALES_DISPONIBLES,
        default=PORTALES_DISPONIBLES,
        help="portales a consultar",
    )
    parser.add_argument(
        "--max-paginas",
        type=int,
        default=2,
        help="máximo de páginas por portal y barrio",
    )
    parser.add_argument(
        "--formatos",
        nargs="+",
        choices=FORMATOS_DISPONIBLES,
        default=FORMATOS_DISPONIBLES,
        help="formatos de exportación",
    )
    parser.add_argument(
        "--salida",
        default="data",
        help="carpeta de salida para archivos generados (sólo CLI)",
    )
    parser.add_argument(
        "--nombre",
        default=None,
        help="nombre base de los archivos de salida",
    )
    parser.add_argument(
        "--barrios",
        nargs="+",
        default=None,
        help="barrios a buscar (deben estar en la lista válida)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="logs detallados (-v)",
    )
    args = parser.parse_args(argv)

    _configurar_logging(args.verbose)

    barrios = _validar_barrios(args.barrios)

    criterios = Criterios()
    motor = MotorBusqueda()
    for portal in args.portales:
        cls = SCRAPERS_POR_PORTAL[portal]
        motor.scrapers[portal] = cls()

    resultado = motor.buscar(
        criterios=criterios,
        portales=args.portales,
        barrios=barrios,
        max_paginas=args.max_paginas,
        modo_demo=args.demo,
    )

    rutas = exportar_propiedades(
        resultado.aceptadas + resultado.excepciones,
        args.formatos,
        args.salida,
        args.nombre,
    )
    for fmt, ruta in rutas.items():
        logger.info("Exportado %s: %s", fmt.upper(), ruta)

    logger.info(
        "Resumen: %d aceptadas, %d excepciones, %d rechazadas, %d revisadas",
        len(resultado.aceptadas),
        len(resultado.excepciones),
        len(resultado.rechazadas),
        resultado.total_revisadas,
    )
    if motor.portales_fallidos:
        logger.warning("Portales fallidos: %s", motor.portales_fallidos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
