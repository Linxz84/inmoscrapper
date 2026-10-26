"""Scraper de ZonaProp.

Usa exclusivamente los selectores especificados en el requerimiento.
La URL base y el patrón de construcción de URLs por barrio no están
especificados en el requerimiento: se declaran como SUPUESTO y pueden
ajustarse cuando se cuente con la URL real del portal.
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
_CARD_SELECTOR = ".postingCardLayout-module__posting-card-layout"
_URL_ATTR = "data-to-posting"
_PRECIO_SELECTOR = ".andes-money-amount__fraction"
_IMG_SELECTOR = "img"

# SUPUESTO: patrón de URL de ZonaProp (no especificado en el requerimiento).
URL_BASE = "https://www.zonaprop.com.ar"
URL_PATTERN = "{base}/{slug}-departamentos-venta.html"


class ZonaPropScraper(BaseScraper):
    """Scraper de ZonaProp usando los selectores del requerimiento."""

    def __init__(self, slugs: dict[str, str] | None = None):
        super().__init__("ZonaProp")
        self.slugs = slugs or {}

    def _url_para_barrio_pagina(self, barrio: str, pagina: int) -> str:
        slug = self.slugs.get(barrio, barrio.lower().replace(" ", "-"))
        if pagina > 1:
            return f"{URL_BASE}/{slug}-departamentos-venta-pagina-{pagina}.html"
        return URL_PATTERN.format(base=URL_BASE, slug=slug)

    def buscar(self, barrio: str, pagina: int) -> list[Propiedad]:
        url = self._url_para_barrio_pagina(barrio, pagina)
        html = self._obtener_html(url)
        if html is None:
            return []
        soup = self._soup(html)
        cards = soup.select(_CARD_SELECTOR)
        if not cards:
            logger.warning(
                "ZonaProp: no se encontraron cards con '%s' en %s",
                _CARD_SELECTOR,
                url,
            )
            return []
        propiedades: list[Propiedad] = []
        for card in cards:
            prop = self._extraer_propiedad(card, barrio)
            if prop is not None:
                propiedades.append(prop)
        return propiedades

    def _extraer_propiedad(self, card: Tag, barrio: str) -> Optional[Propiedad]:
        url_tag = card.find(attrs={_URL_ATTR: True})
        url = url_tag.get(_URL_ATTR) if url_tag else ""
        if url and url.startswith("/"):
            url = URL_BASE + url

        precio_tag = card.select_one(_PRECIO_SELECTOR)
        precio_texto = precio_tag.get_text(" ", strip=True) if precio_tag else None

        img_tag = card.select_one(_IMG_SELECTOR)
        imagen_url = ""
        if img_tag:
            imagen_url = img_tag.get("src") or img_tag.get("data-src") or ""

        texto_completo = card.get_text(" ", strip=True)

        senales = extraer_senales(texto_completo, precio_texto=precio_texto)

        direccion = ""
        # ZonaProp no especifica selector de dirección en el requerimiento.

        return Propiedad(
            portal="ZonaProp",
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
