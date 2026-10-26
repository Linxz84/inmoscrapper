"""Paquete de scrapers de portales inmobiliarios."""

from .argenprop import ArgenpropScraper
from .base import BaseScraper
from .mercadolibre import MercadoLibreScraper
from .zonaprop import ZonaPropScraper

__all__ = ["BaseScraper", "ZonaPropScraper", "MercadoLibreScraper", "ArgenpropScraper"]
