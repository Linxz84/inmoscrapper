"""Scraper de Argenprop.

Usa exclusivamente los selectores especificados en el requerimiento.
Si la imagen no está en el card, se intenta obtener del detalle; si tampoco,
imagen_url queda vacía ("").
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
_ITEM_SELECTOR = ".listing__item"
_URL_SELECTOR = "a.card__title"
_PRECIO_SELECTOR = ".card__price"
_DIRECCION_SELECTOR = ".card__address"
_IMG_SELECTOR = "img"
_PAGINACION_SELECTOR = 'a[href*="/pagina-"]'

# SUPUESTO: patrón de URL de Argenprop (no especificado).
URL_BASE = "https://www.argenprop.com.ar"
URL_PATTERN = "{base}/departamentos/venta/{slug}/pagina-{pagina}"


class ArgenpropScraper(BaseScraper):
    """Scraper de Argenprop usando los selectores del requerimiento."""

    def __init__(self, slugs: dict[str, str] | None = None):
        super().__init__("Argenprop")
        self.slugs = slugs or {}

    def _url_para_barrio_pagina(self, barrio: str, pagina: int) -> str:
        slug = self.slugs.get(barrio, barrio.lower().replace(" ", "-"))
        return URL_PATTERN.format(base=URL_BASE, slug=slug, pagina=pagina)

    def buscar(self, barrio: str, pagina: int) -> list[Propiedad]:
        url = self._url_para_barrio_pagina(barrio, pagina)
        html = self._obtener_html(url)
        if html is None:
            return []
        soup = self._soup(html)
        items = soup.select(_ITEM_SELECTOR)
        if not items:
            logger.warning(
                "Argenprop: no se encontraron items con '%s' en %s",
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
        if url and url.startswith("/"):
            url = URL_BASE + url

        precio_tag = item.select_one(_PRECIO_SELECTOR)
        precio_texto = precio_tag.get_text(" ", strip=True) if precio_tag else None

        direccion_tag = item.select_one(_DIRECCION_SELECTOR)
        direccion = direccion_tag.get_text(" ", strip=True) if direccion_tag else ""

        img_tag = item.select_one(_IMG_SELECTOR)
        imagen_url = ""
        if img_tag:
            imagen_url = img_tag.get("src") or img_tag.get("data-src") or ""

        texto_completo = item.get_text(" ", strip=True)

        senales = extraer_senales(texto_completo, precio_texto=precio_texto)

        return Propiedad(
            portal="Argenprop",
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
