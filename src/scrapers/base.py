"""Clase base para scrapers de portales inmobiliarios.

Proporciona utilidades HTTP compartidas:
- requests con User-Agent de navegador común
- Pausas aleatorias de 1-2s entre requests
- 3 reintentos con backoff exponencial
- Timeout de 30s
- Tolerancia a fallos: devuelve None (no lanza) cuando un portal falla
"""

from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class BaseScraper:
    """Clase base con utilidades HTTP compartidas por todos los scrapers."""

    def __init__(self, nombre_portal: str):
        self.nombre_portal = nombre_portal
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _obtener_html(self, url: str) -> Optional[str]:
        """Realiza una petición GET con reintentos, backoff y pausa aleatoria.

        Devuelve el HTML como texto o ``None`` si falla tras 3 intentos.
        Nunca lanza: los errores se loguean y se devuelve ``None`` para que
        el motor de búsqueda continúe con los demás portales.
        """
        ultimo_error: Optional[Exception] = None
        for intento in range(1, 4):
            try:
                respuesta = self.session.get(url, timeout=30)
                if respuesta.status_code == 200:
                    # Pausa aleatoria 1-2s entre requests exitosos.
                    time.sleep(random.uniform(1, 2))
                    return respuesta.text
                logger.warning(
                    "%s: status %d en intento %d/3 para %s",
                    self.nombre_portal,
                    respuesta.status_code,
                    intento,
                    url,
                )
                ultimo_error = Exception(f"HTTP {respuesta.status_code}")
            except Exception as exc:
                logger.warning(
                    "%s: error en intento %d/3 para %s: %s",
                    self.nombre_portal,
                    intento,
                    url,
                    exc,
                )
                ultimo_error = exc
            if intento < 3:
                # Backoff exponencial: 2s, 4s.
                time.sleep(2 ** intento)
        logger.error(
            "%s: falló tras 3 intentos: %s", self.nombre_portal, ultimo_error
        )
        return None

    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    def buscar(self, barrio: str, pagina: int):  # noqa: D401
        """Devuelve una lista de :class:`src.models.Propiedad` para un barrio/página.

        Cada scraper concreto debe implementar este método usando los
        selectores especificados en el requerimiento. Si el HTML real del
        portal difiere de los selectores, debe loguear un error claro y
        devolver una lista vacía (no inventar otros selectores).
        """
        raise NotImplementedError
