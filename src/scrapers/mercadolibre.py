"""Scraper de MercadoLibre Inmuebles.

Usa exclusivamente los selectores especificados en el requerimiento.
La URL base y el patrón de construcción de URLs por barrio no están
especificados en el requerimiento: se declaran como SUPUESTO.
"""

from __future__ import annotations

import logging
from typing import Optional

from bs4 import Tag

from src.filters import extraer_senales
from src.models import Propiedad

from .base import BaseScraper

logger = logging.getLogger(__name__)

# Selectores verificados según el requerimiento.
_ITEM_SELECTOR = "li.ui-search-layout__item"
_URL_SELECTOR = "a.poly-component__title"
_PRECIO_FRACTION_SELECTOR = ".andes-money-amount__fraction"
_PRECIO_SYMBOL_SELECTOR = ".andes-money-amount__currency-symbol"
_IMG_SELECTOR = "img"

# SUPUESTO: patrón de URL de MercadoLibre Inmuebles (no especificado).
URL_BASE = "https://inmuebles.mercadolibre.com.ar"
URL_PATTERN = "{base}/departamentos/{slug}/venta"


class MercadoLibreScraper(BaseScraper):
    """Scraper de MercadoLibre usando los selectores del requerimiento."""

    def __init__(self, slugs: dict[str, str] | None = None):
        super().__init__("MercadoLibre")
        self.slugs = slugs or {}

    def _url_para_barrio_pagina(self, barrio: str, pagina: int) -> str:
        slug = self.slugs.get(barrio, barrio.lower().replace(" ", "-"))
        offset = (pagina - 1) * 48 + 1
        return f"{URL_BASE}/departamentos/{slug}/venta/_Desde_{offset}"

    def buscar(self, barrio: str, pagina: int) -> list[Propiedad]:
        url = self._url_para_barrio_pagina(barrio, pagina)
        html = self._obtener_html(url)
        if html is None:
            return []
        soup = self._soup(html)
        items = soup.select(_ITEM_SELECTOR)
        if not items:
            logger.warning(
                "MercadoLibre: no se encontraron items con '%s' en %s",
                _ITEM_SELECTOR,
                url,
            )
            return []
        propiedades: list[Propiedad] = []
        for item in items:
            prop = self._extraer_propiedad(item, barrio)
            if prop is not None:
                propiedades.append(prop)
        return propiedades

    def _extraer_propiedad(self, item: Tag, barrio: str) -> Optional[Propiedad]:
        url_tag = item.select_one(_URL_SELECTOR)
        url = url_tag.get("href") if url_tag else ""

        precio_fraction = item.select_one(_PRECIO_FRACTION_SELECTOR)
        precio_symbol = item.select_one(_PRECIO_SYMBOL_SELECTOR)
        partes_precio = []
        if precio_fraction:
            partes_precio.append(precio_fraction.get_text(" ", strip=True))
        if precio_symbol:
            partes_precio.append(precio_symbol.get_text(" ", strip=True))
        precio_texto = " ".join(partes_precio) if partes_precio else None

        img_tag = item.select_one(_IMG_SELECTOR)
        imagen_url = img_tag.get("src") or img_tag.get("data-src") or "" if img_tag else ""

        texto_completo = item.get_text(" ", strip=True)

        senales = extraer_senales(texto_completo, precio_texto=precio_texto)

        direccion = ""
        # MercadoLibre no especifica selector de dirección en el requerimiento.

        return Propiedad(
            portal="MercadoLibre",
            barrio=barrio,
            tipo=senales["tipo"],
            ambientes=senales["ambientes"] or 0,
            metros2=senales["metros2"] or 0.0,
            precio_usd=senales["precio_usd"],
            moneda_original="USD",
            precio_original=precio_texto,
            direccion=direccion,
            tiene_balcon=senales["tiene_balcon"],
            tiene_patio=senales["tiene_patio"],
            escalera_sin_ascensor=senales["escalera_sin_ascensor"],
            apto_credito=senales["apto_credito"],
            imagen_url=imagen_url,
            url=url,
            descripcion=texto_completo,
        )
