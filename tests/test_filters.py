"""Pruebas de parsers, detectores y criterios (Fase 1).

Ejecutar con: pytest tests/ -v
"""

import pytest

from src.filters import (
    detectar_apto_credito,
    detectar_departamento_nuevo,
    detectar_departamento_pozo,
    detectar_escalera_sin_ascensor,
    detectar_tipo,
    extraer_senales,
    parse_ambientes,
    parse_metros,
    parse_numero,
    parse_precio_usd,
)
from src.models import BARRIOS_VALIDOS, Criterios, Propiedad


# ---------------------------------------------------------------------------
# parse_numero
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("120.000", 120000.0),
        ("50,5", 50.5),
        ("1.250.000", 1250000.0),
        ("1.250,50", 1250.5),
        ("100", 100.0),
        ("120.000,50", 120000.5),
        ("", None),
        ("sin numero", None),
        (None, None),
    ],
)
def test_parse_numero(texto, esperado):
    assert parse_numero(texto) == esperado


# ---------------------------------------------------------------------------
# parse_precio_usd
# ---------------------------------------------------------------------------

def test_parse_precio_usd_usd():
    assert parse_precio_usd("USD 120.000") == 120000.0


def test_parse_precio_usd_u_s():
    assert parse_precio_usd("U$S 100.000") == 100000.0


def test_parse_precio_usd_ars_conversion():
    assert parse_precio_usd("ARS 156.000.000", tipo_cambio_ars_usd=1300.0) == 120000.0


def test_parse_precio_usd_pesos_conversion():
    assert parse_precio_usd("156.000.000 pesos", tipo_cambio_ars_usd=1300.0) == 120000.0


def test_parse_precio_usd_solo_signo_peso_asume_usd(caplog):
    with caplog.at_level("WARNING"):
        assert parse_precio_usd("$ 100.000") == 100000.0
    assert any("asume USD" in record.getMessage() for record in caplog.records)


def test_parse_precio_usd_sin_precio_devuelve_none():
    assert parse_precio_usd("consultar precio") is None
    assert parse_precio_usd("") is None
    assert parse_precio_usd(None) is None


# ---------------------------------------------------------------------------
# parse_ambientes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("3 amb", 3),
        ("3 ambientes", 3),
        ("3 ambient", 3),
        ("Departamento de 3 ambientes", 3),
        ("PH 2 amb", 2),
    ],
)
def test_parse_ambientes(texto, esperado):
    assert parse_ambientes(texto) == esperado


def test_parse_ambientes_solo_dormitorio_no_cuenta():
    """2 dorm NO es lo mismo que 2 amb."""
    assert parse_ambientes("2 dorm") is None
    assert parse_ambientes("2 dormitorios") is None


def test_parse_ambientes_sin_ambientes_devuelve_none():
    assert parse_ambientes("expensas 15.000") is None


# ---------------------------------------------------------------------------
# parse_metros
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("50 m²", 50.0),
        ("50m2", 50.0),
        ("50 m", 50.0),
        ("Superficie: 120 m2 totales, 80 m2 cubierta", 120.0),
        ("50,5 m2", 50.5),
    ],
)
def test_parse_metros(texto, esperado):
    assert parse_metros(texto) == esperado


def test_parse_metros_sin_superficie_devuelve_none():
    assert parse_metros("expensas 5.000") is None


# ---------------------------------------------------------------------------
# Detectores con falsos positivos
# ---------------------------------------------------------------------------

def test_detector_escalera_positivo():
    assert detectar_escalera_sin_ascensor("por escalera")
    assert detectar_escalera_sin_ascensor("acceso por escalera")
    assert detectar_escalera_sin_ascensor("sin ascensor")
    assert detectar_escalera_sin_ascensor("x pisos por escalera")


def test_detector_escalera_falsos_positivos_no_marcan():
    assert not detectar_escalera_sin_ascensor("escalera de servicio")
    assert not detectar_escalera_sin_ascensor("escalera de incendio")
    assert not detectar_escalera_sin_ascensor("escalera decorativa")
    assert not detectar_escalera_sin_ascensor("escalera al patio")


def test_detector_apto_credito_negaciones_primero():
    assert not detectar_apto_credito("no apto credito")
    assert not detectar_apto_credito("sin credito")
    assert detectar_apto_credito("apto credito")
    assert detectar_apto_credito("credito hipotecario")
    assert detectar_apto_credito("credito bancario")
    assert detectar_apto_credito("financiacion")


def test_detector_balcon_o_patio():
    from src.filters import detectar_balcon_o_patio

    assert detectar_balcon_o_patio("con balcon")
    assert detectar_balcon_o_patio("terraza")
    assert detectar_balcon_o_patio("patio")
    assert detectar_balcon_o_patio("jardín propio")
    assert detectar_balcon_o_patio("jardin propio")
    assert not detectar_balcon_o_patio("PH céntrico 3 ambientes")


def test_detector_nuevo_reciclado_a_estrenar_no_es_nuevo():
    assert not detectar_departamento_nuevo("reciclado a estrenar")
    assert detectar_departamento_nuevo("a estrenar")
    assert detectar_departamento_nuevo("a estrenarse")
    assert detectar_departamento_nuevo("emprendimiento")
    assert detectar_departamento_nuevo("unidad nueva")
    assert detectar_departamento_nuevo("0 años de antigüedad")
    assert not detectar_departamento_nuevo("departamento reciclado")


def test_detector_pozo():
    assert detectar_departamento_pozo("de pozo")
    assert detectar_departamento_pozo("en pozo")
    assert detectar_departamento_pozo("preventa")
    assert detectar_departamento_pozo("lanzamiento")
    assert detectar_departamento_pozo("construccion en curso")
    assert detectar_departamento_pozo("construcción en curso")
    assert detectar_departamento_pozo("entrega 2030")
    # Año pasado no es pozo por entrega futura.
    assert not detectar_departamento_pozo("entrega 2020")
    assert not detectar_departamento_pozo("departamento reciclado")


# ---------------------------------------------------------------------------
# detectar_tipo
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("PH en venta", "PH"),
        ("PH 3 ambientes", "PH"),
        ("Casa quinta", "casa"),
        ("Casa en Caballito", "casa"),
        ("Departamento 3 amb", "departamento"),
        ("", "departamento"),
    ],
)
def test_detectar_tipo(texto, esperado):
    assert detectar_tipo(texto) == esperado


# ---------------------------------------------------------------------------
# Criterios.cumple() sobre el dataset demo
# ---------------------------------------------------------------------------

def _propiedad_demo(**sobreescritura):
    datos = dict(
        portal="demo",
        barrio="Caballito",
        tipo="departamento",
        ambientes=3,
        metros2=60.0,
        precio_usd=100000.0,
        moneda_original="USD",
        precio_original="100.000",
        direccion="Falsa 123",
        tiene_balcon=True,
        tiene_patio=False,
        escalera_sin_ascensor=False,
        apto_credito=False,
        es_excepcion=False,
        imagen_url="",
        url="https://ejemplo.com/1",
        fecha_publicacion="2026-01-01",
        descripcion="",
    )
    datos.update(sobreescritura)
    return Propiedad(**datos)


def test_cumple_propiedad_valida():
    p = _propiedad_demo()
    ok, motivo = Criterios().cumple(p)
    assert ok is True
    assert motivo == ""


def test_cumple_rechaza_menos_de_tres_ambientes():
    p = _propiedad_demo(ambientes=2)
    ok, motivo = Criterios().cumple(p)
    assert ok is False
    assert "ambientes" in motivo


def test_cumple_rechaza_superficie_menor_a_50():
    p = _propiedad_demo(metros2=45.0)
    ok, motivo = Criterios().cumple(p)
    assert ok is False
    assert "superficie" in motivo


def test_cumple_rechaza_sin_balcon_ni_patio():
    p = _propiedad_demo(tiene_balcon=False, tiene_patio=False)
    ok, motivo = Criterios().cumple(p)
    assert ok is False
    assert "balcon" in motivo.lower()


def test_cumple_rechaza_precio_mayor_a_120000():
    p = _propiedad_demo(precio_usd=150000.0)
    ok, motivo = Criterios().cumple(p)
    assert ok is False
    assert "120,000" in motivo


def test_cumple_escalera_es_excepcion_no_rechaza():
    p = _propiedad_demo(escalera_sin_ascensor=True)
    ok, motivo = Criterios().cumple(p)
    assert ok is True
    assert p.es_excepcion is True
    assert "excepcion" in motivo.lower()


def test_cumple_rechaza_departamento_nuevo_por_defecto():
    p = _propiedad_demo(descripcion="a estrenar")
    ok, motivo = Criterios().cumple(p)
    assert ok is False
    assert "nuevo" in motivo.lower()


def test_cumple_apto_credito_requerido_y_no_tiene():
    p = _propiedad_demo(apto_credito=False)
    ok, _ = Criterios(requiere_apto_credito=True).cumple(p)
    assert ok is False


def test_cumple_apto_credito_no_requerido_pasa_sin_ello():
    p = _propiedad_demo(apto_credito=False)
    ok, _ = Criterios().cumple(p)
    assert ok is True


# ---------------------------------------------------------------------------
# Validacion de barrios (lista maestra)
# ---------------------------------------------------------------------------

def test_barrios_validos_lista_maestra():
    assert len(BARRIOS_VALIDOS) == 14
    assert "Caballito" in BARRIOS_VALIDOS
    assert "Flores" in BARRIOS_VALIDOS
    assert "Monte Castro" in BARRIOS_VALIDOS
    assert len(set(BARRIOS_VALIDOS)) == len(BARRIOS_VALIDOS), "no debe haber duplicados"


def test_barrio_invalido_no_esta_en_lista_maestra():
    assert "Barrio Inexistente" not in BARRIOS_VALIDOS
    assert "Palermo" not in BARRIOS_VALIDOS
    assert "Recoleta" not in BARRIOS_VALIDOS


# ---------------------------------------------------------------------------
# extraer_senales
# ---------------------------------------------------------------------------

def test_extraer_senales_demostracion():
    senales = extraer_senales(
        "PH con balcón, 3 ambientes, 60 m2, apto credito",
        precio_texto="USD 100.000",
    )
    assert senales["tipo"] == "PH"
    assert senales["ambientes"] == 3
    assert senales["metros2"] == 60.0
    assert senales["precio_usd"] == 100000.0
    assert senales["tiene_balcon"] is True
    assert senales["apto_credito"] is True


def test_extraer_senales_sin_precio_texto_devuelve_none():
    senales = extraer_senales("Departamento 2 ambientes, 50 m2")
    assert senales["precio_usd"] is None
