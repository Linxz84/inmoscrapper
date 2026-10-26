"""Filtros, parsers y detectores de texto para avisos inmobiliarios.

Implementa exactamente las reglas de parseo y detectores del requerimiento:
numeros argentinos, deteccion de ambientes vs dormitorios, superficie,
moneda, balcon/terraza/patio, escalera sin ascensor (con falsos positivos),
apto credito, departamento nuevo y departamento de pozo.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from .models import Propiedad, TipoPropiedad

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

_RE_NUMERO = re.compile(r"\d[\d\.\s,]*")


def parse_numero(texto: str) -> float | None:
    """Parsea un numero con formato argentino.

    Punto = separador de miles, coma = decimal.
    "120.000" -> 120000; "50,5" -> 50.5; "1.250.000" -> 1250000.
    Devuelve None si no hay numero parseable.
    """
    if texto is None:
        return None
    limpio = texto.strip()
    if not limpio:
        return None
    match = _RE_NUMERO.search(limpio)
    if not match:
        return None
    grupo = match.group(0)
    # Quitar puntos (miles) y convertir coma decimal en punto.
    entero = grupo.replace(".", "").replace(",", ".")
    try:
        return float(entero)
    except ValueError:
        return None


_RE_MONEDA_USD = re.compile(r"\b(USD|U\$S|dólares|dolares|usd)\b", re.IGNORECASE)
_RE_MONEDA_ARS = re.compile(r"\b(ARS|pesos)\b", re.IGNORECASE)


def parse_precio_usd(
    texto: str, tipo_cambio_ars_usd: float = 1300.0
) -> float | None:
    """Extrae el precio en USD de un aviso.

    Si el aviso trae moneda ARS, convierte con el tipo de cambio.
    Si solo hay "$" se asume USD (practica estandar de los portales) y se
    registra una advertencia. Devuelve None si no hay precio parseable.
    """
    if texto is None:
        return None
    numero = parse_numero(texto)
    if numero is None:
        return None
    if _RE_MONEDA_ARS.search(texto):
        usd = numero / tipo_cambio_ars_usd
        logger.debug(
            "Precio ARS %s convertido a USD %.2f", numero, usd
        )
        return usd
    if _RE_MONEDA_USD.search(texto):
        return numero
    # Solo "$" sin moneda explicita: se asume USD con advertencia.
    if "$" in texto:
        logger.warning(
            "Precio solo con '$': se asume USD (verificar en el aviso)"
        )
        return numero
    return numero


_RE_AMBIENTES = re.compile(r"(\d+)\s*amb(?:ientes|ient)?\b", re.IGNORECASE)


def parse_ambientes(texto: str) -> int | None:
    """Detecta la cantidad de ambientes.

    Patrones: "3 amb", "3 ambientes", "3 ambient". "2 dorm" NO es lo mismo
    que "2 amb": los dormitorios por si solos no se cuentan como ambientes.
    Se prioriza la senal de "amb" sobre "dormitorio".
    """
    if texto is None:
        return None
    match = _RE_AMBIENTES.search(texto)
    if match:
        return int(match.group(1))
    return None


_RE_METROS = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*m\s*(?:2|²|m2|m²)?\b", re.IGNORECASE
)


def parse_metros(texto: str) -> float | None:
    """Detecta la superficie en m2.

    "50 m2", "50m2", "50 m". Si hay varias superficies (cubierta/total),
    se usa la MAYOR.
    """
    if texto is None:
        return None
    valores: list[float] = []
    for match in _RE_METROS.finditer(texto):
        numero = parse_numero(match.group(1))
        if numero is not None:
            valores.append(numero)
    if not valores:
        return None
    return max(valores)


# ---------------------------------------------------------------------------
# Detectores de texto
# ---------------------------------------------------------------------------

_RE_BALCON = re.compile(
    r"\b(balcón|balcon|terraza)\b", re.IGNORECASE
)
_RE_PATIO = re.compile(
    r"\b(patio|jard[ií]n propio)\b", re.IGNORECASE
)


def detectar_balcon_o_patio(texto: str) -> bool:
    """True si el aviso menciona balcon, terraza o patio (detector combinado)."""
    if not texto:
        return False
    return bool(_RE_BALCON.search(texto) or _RE_PATIO.search(texto))


def detectar_balcon(texto: str) -> bool:
    """True si el aviso menciona balcon o terraza."""
    if not texto:
        return False
    return bool(_RE_BALCON.search(texto))


def detectar_patio(texto: str) -> bool:
    """True si el aviso menciona patio o jardín propio."""
    if not texto:
        return False
    return bool(_RE_PATIO.search(texto))


_RE_ESCALERA_POSITIVO = re.compile(
    r"\b(por escalera|acceso por escalera|sin ascensor|x pisos por escalera)\b",
    re.IGNORECASE,
)
_RE_ESCALERA_FALSO_POSITIVO = re.compile(
    r"\b(escalera de servicio|escalera de incendio|escalera decorativa|escalera al patio)\b",
    re.IGNORECASE,
)


def detectar_escalera_sin_ascensor(texto: str) -> bool:
    """True solo si se indica acceso por escalera o sin ascensor.

    No se marca si la escalera es de servicio, de incendio, decorativa o al
    patio (falsos positivos).
    """
    if not texto:
        return False
    if _RE_ESCALERA_FALSO_POSITIVO.search(texto):
        return False
    return bool(_RE_ESCALERA_POSITIVO.search(texto))


_RE_APTO_CREDITO_POSITIVO = re.compile(
    r"\b(apto cr[eé]dito|cr[eé]dito hipotecario|cr[eé]dito bancario|financiaci[eo]n)\b",
    re.IGNORECASE,
)
_RE_APTO_CREDITO_NEGACION = re.compile(
    r"\b(no\s+apto\s+cr[eé]dito|sin\s+cr[eé]dito)\b", re.IGNORECASE
)


def detectar_apto_credito(texto: str) -> bool:
    """True si el aviso es apto credito.

    Las negaciones ("no apto credito", "sin credito") se evalúan primero.
    """
    if not texto:
        return False
    if _RE_APTO_CREDITO_NEGACION.search(texto):
        return False
    return bool(_RE_APTO_CREDITO_POSITIVO.search(texto))


_RE_NUEVO_POSITIVO = re.compile(
    r"\b(a estrenar|a estrenarse|emprendimiento|unidad nueva|0 años de antigüedad)\b",
    re.IGNORECASE,
)


def detectar_departamento_nuevo(texto: str) -> bool:
    """True si el aviso indica departamento nuevo.

    "reciclado a estrenar" en edificio con antigüedad NO cuenta como nuevo.
    """
    if not texto:
        return False
    if re.search(r"\breciclado\b", texto, re.IGNORECASE) and re.search(
        r"\ba estrenar\b", texto, re.IGNORECASE
    ):
        return False
    return bool(_RE_NUEVO_POSITIVO.search(texto))


_RE_POZO_POSITIVO = re.compile(
    r"\b(de pozo|en pozo|preventa|lanzamiento|construcci[oó]n en curso)\b",
    re.IGNORECASE,
)
_RE_ENTREGA_AÑO = re.compile(r"entrega\s*20\d{2}", re.IGNORECASE)


def detectar_departamento_pozo(texto: str) -> bool:
    """True si el aviso indica departamento de pozo / preventa / futuro."""
    if not texto:
        return False
    if _RE_POZO_POSITIVO.search(texto):
        return True
    match = _RE_ENTREGA_AÑO.search(texto)
    if match:
        año = int(match.group(0)[-4:])
        if año > datetime.now().year:
            return True
    return False


_RE_TIPO_PH = re.compile(r"\bPH\b", re.IGNORECASE)
_RE_TIPO_CASA = re.compile(r"\bcasa\b", re.IGNORECASE)


def detectar_tipo(texto: str) -> TipoPropiedad:
    """Detecta el tipo de propiedad con prioridad PH > Casa > Departamento.

    Si no se detecta, asume "departamento" y registra advertencia.
    """
    if not texto:
        logger.warning(
            "No se detecto tipo de propiedad: se asume departamento"
        )
        return "departamento"
    if _RE_TIPO_PH.search(texto):
        return "PH"
    if _RE_TIPO_CASA.search(texto):
        return "casa"
    logger.warning(
        "No se detecto tipo de propiedad: se asume departamento"
    )
    return "departamento"


# ---------------------------------------------------------------------------
# Ensamblado de senales desde el texto de un aviso
# ---------------------------------------------------------------------------

def extraer_senales(
    texto: str,
    precio_texto: str | None = None,
    tipo_cambio_ars_usd: float = 1300.0,
) -> dict:
    """Extrae todas las senales detectables de un aviso.

    ``precio_texto`` es el texto del elemento de precio del portal (se pasa
    por separado porque el resto del aviso suele contener otros numeros,
    como ambientes o expensas). Devuelve None de precio cuando no se provee.
    Devuelve un diccionario listo para mapear a los campos de Propiedad.
    """
    return {
        "tipo": detectar_tipo(texto),
        "ambientes": parse_ambientes(texto),
        "metros2": parse_metros(texto) or 0.0,
        "precio_usd": (
            parse_precio_usd(precio_texto, tipo_cambio_ars_usd)
            if precio_texto
            else None
        ),
        "tiene_balcon": detectar_balcon(texto),
        "tiene_patio": detectar_patio(texto),
        "escalera_sin_ascensor": detectar_escalera_sin_ascensor(texto),
        "apto_credito": detectar_apto_credito(texto),
    }
