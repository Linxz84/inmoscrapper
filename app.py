"""Interfaz web (Streamlit) del buscador de inmuebles de CABA.

Es la vía principal de uso. Se ejecuta con: streamlit run app.py

No escribe archivos en disco: la exportación se genera en memoria con
io.BytesIO/StringIO y se ofrece mediante st.download_button.
"""

from __future__ import annotations

import logging

import streamlit as st

from src.cli import PORTALES_DISPONIBLES, SCRAPERS_POR_PORTAL
from src.engine import MotorBusqueda, cargar_config
from src.exporters import exportar_en_memoria
from src.models import BARRIOS_VALIDOS, Criterios

logger = logging.getLogger(__name__)

FORMATOS_DISPONIBLES = ["CSV", "JSON", "Excel"]
PAGINA_TAMANIO = 20

# Estado de conectividad de los portales (se detecta al intentar buscar).
# Por defecto se asume desconocido hasta que el usuario haga una búsqueda real.
if "portal_estado" not in st.session_state:
    st.session_state["portal_estado"] = {p: "desconocido" for p in PORTALES_DISPONIBLES}

st.set_page_config(
    page_title="Buscador de Inmuebles CABA",
    page_icon="🏠",
    layout="wide",
)

st.title("🏠 Buscador de Inmuebles — CABA")
st.caption(
    "Barrios objetivo: Flores, Floresta, Villa del Parque, Santa Rita, Paternal, "
    "Devoto, Villa Pueyrredon, Villa Urquiza, Villa Crespo, Almagro, "
    "Parque Centenario, Caballito, Coghlan, Monte Castro."
)

# ---------------------------------------------------------------------------
# Carga de configuración
# ---------------------------------------------------------------------------

try:
    config = cargar_config()
except FileNotFoundError:
    st.error("No se encontró config/config.yaml. Usando valores por defecto.")
    config = {"barrios_validados": BARRIOS_VALIDOS.copy()}

barrios_config = config.get("barrios_validados", BARRIOS_VALIDOS.copy())
portales_cfg = config.get("portales", {}) or {}
busqueda_cfg = config.get("busqueda", {}) or {}

# ---------------------------------------------------------------------------
# Banner informativo sobre los portales reales (bloqueo externo)
# ---------------------------------------------------------------------------

st.markdown(
    '<div style="background-color:#c0392b;color:#ffffff;padding:14px;border-radius:8px;margin-bottom:16px;">'
    '<strong>⚠️ PORTAL INMOBILIARIOS BLOQUEADOS EXTERNAMENTE</strong><br>'
    'ZonaProp devuelve <code>403</code> (Cloudflare), Argenprop devuelve '
    '<code>405</code> y MercadoLibre no expone los selectores especificados. '
    'Esto es un bloqueo de los portales, no un error de la aplicación. '
    'Usá el <strong>modo demo</strong> para probar el pipeline completo con datos '
    'sintéticos fijos.</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Modo demo (vía principal recomendada)
# ---------------------------------------------------------------------------

st.subheader("Modo de operación")

col_demo, col_real = st.columns(2)

with col_demo:
    st.info(
        "🧪 **Modo demo** — Datos sintéticos fijos, sin internet. "
        "Prueba todo el pipeline: 7 propiedades (2 válidas, 1 excepción por escalera, "
        "1 <50 m², 1 >USD 120.000, 1 a estrenar, 1 de pozo)."
    )
    modo_demo = st.checkbox("Activar modo demo", value=True, key="modo_demo_check")

with col_real:
    st.warning(
        "🌐 **Modo real** — Se conecta a ZonaProp, MercadoLibre y Argenprop. "
        "Es probable que falle por bloqueos externos (403/405)."
    )

# ---------------------------------------------------------------------------
# Estado de los portales (se actualiza al buscar en modo real)
# ---------------------------------------------------------------------------

st.markdown("#### Estado de los portales")

cols_estado = st.columns(len(PORTALES_DISPONIBLES))
estado_actual = st.session_state.get("portal_estado", {})
for i, portal in enumerate(PORTALES_DISPONIBLES):
    estado = estado_actual.get(portal, "desconocido")
    if estado == "ok":
        color = "#27ae60"
        texto = "Conectado"
    elif estado == "fallo":
        color = "#c0392b"
        texto = "Bloqueado"
    else:
        color = "#bdc3c7"
        texto = "Sin probar"
    with cols_estado[i]:
        st.markdown(
            f"<div style='text-align:center;padding:10px;border-radius:6px;"
            f"background:{color};color:#fff;font-weight:600;font-size:13px;'>"
            f"{portal}<br>{texto}</div>",
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Configuración en el cuerpo principal (sin sidebar)
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Configuración de búsqueda")

col_portales, col_barrios, col_paginas = st.columns([0.34, 0.36, 0.30])

with col_portales:
    portales_por_defecto = [
        p for p in PORTALES_DISPONIBLES if portales_cfg.get(p, {}).get("habilitado", True)
    ] or PORTALES_DISPONIBLES
    portales_sel = st.multiselect(
        "Portales",
        options=PORTALES_DISPONIBLES,
        default=[] if modo_demo else portales_por_defecto,
        disabled=modo_demo,
        help="En modo demo no se usan portales reales.",
    )

with col_barrios:
    barrios_sel = st.multiselect(
        "Barrios",
        options=barrios_config,
        default=barrios_config[:6],
    )

with col_paginas:
    max_paginas = st.number_input(
        "Máx. páginas por portal",
        min_value=1,
        max_value=20,
        value=int(portales_cfg.get("zonaprop", {}).get("max_paginas", 2)),
        disabled=modo_demo,
    )

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
with col1:
    ambientes_min = st.number_input("Ambientes mínimos", min_value=1, value=3, step=1)
    metros_min = st.number_input("Superficie mínima (m²)", min_value=10, value=50, step=5)
    precio_max_usd = st.number_input(
        "Precio máximo (USD)", min_value=1000, value=120000, step=5000
    )
    requiere_balcon = st.checkbox("Requiere balcón/terraza/patio", value=True)
    excluir_escalera = st.checkbox("Excluir sin ascensor (por escalera)", value=True)

with col2:
    requiere_apto_credito = st.checkbox("Requiere apto crédito", value=False)
    excluir_nuevo = st.checkbox("Excluir departamento nuevo (a estrenar)", value=True)
    excluir_pozo = st.checkbox("Excluir departamento de pozo", value=True)
    tipo_cambio = st.number_input(
        "Tipo de cambio ARS→USD", min_value=100, value=1300, step=50
    )

with col3:
    st.write("")  # espaciado
    st.write("")
    buscar = st.button("🔍 Buscar", type="primary", use_container_width=True)

with col4:
    st.write("")
    st.write("")
    limpiar = st.button("🗑️ Limpiar resultados", use_container_width=True)

if limpiar:
    for clave in ("resultado", "pagina_actual", "portal_estado"):
        st.session_state.pop(clave, None)
    st.session_state["portal_estado"] = {p: "desconocido" for p in PORTALES_DISPONIBLES}
    st.rerun()

# ---------------------------------------------------------------------------
# Ejecución de búsqueda
# ---------------------------------------------------------------------------

if buscar:
    if modo_demo:
        criterios = Criterios(
            tipos=["casa", "PH", "departamento"],
            ambientes_min=int(ambientes_min),
            metros_min=float(metros_min),
            precio_max_usd=float(precio_max_usd),
            requiere_balcon_o_patio=requiere_balcon,
            excluir_escalera=excluir_escalera,
            requiere_apto_credito=requiere_apto_credito,
            excluir_departamento_nuevo=excluir_nuevo,
            excluir_departamento_pozo=excluir_pozo,
            moneda_objetivo="USD",
            tipo_cambio_ars_usd=float(tipo_cambio),
        )
        motor = MotorBusqueda()
        try:
            resultado = motor.buscar(
                criterios=criterios,
                portales=[],
                barrios=[],
                max_paginas=1,
                modo_demo=True,
            )
        except Exception as exc:
            logger.exception("Error en búsqueda demo: %s", exc)
            st.error(f"Error durante la búsqueda: {exc}")
            resultado = None
        # En demo no hay portales fallados
        st.session_state["portal_estado"] = {p: "no_usado" for p in PORTALES_DISPONIBLES}
    else:
        if not portales_sel:
            st.error("Seleccioná al menos un portal.")
            st.stop()
        if not barrios_sel:
            st.error("Seleccioná al menos un barrio.")
            st.stop()

        criterios = Criterios(
            tipos=["casa", "PH", "departamento"],
            ambientes_min=int(ambientes_min),
            metros_min=float(metros_min),
            precio_max_usd=float(precio_max_usd),
            requiere_balcon_o_patio=requiere_balcon,
            excluir_escalera=excluir_escalera,
            requiere_apto_credito=requiere_apto_credito,
            excluir_departamento_nuevo=excluir_nuevo,
            excluir_departamento_pozo=excluir_pozo,
            moneda_objetivo="USD",
            tipo_cambio_ars_usd=float(tipo_cambio),
        )
        motor = MotorBusqueda()
        for portal in portales_sel:
            motor.scrapers[portal] = SCRAPERS_POR_PORTAL[portal]()
        try:
            resultado = motor.buscar(
                criterios=criterios,
                portales=portales_sel,
                barrios=barrios_sel,
                max_paginas=int(max_paginas),
                modo_demo=False,
            )
        except Exception as exc:
            logger.exception("Error en búsqueda real: %s", exc)
            st.error(f"Error durante la búsqueda: {exc}")
            resultado = None
        # Actualizar estado de portales según fallos detectados
        fallados = motor.portales_fallidos
        for p in PORTALES_DISPONIBLES:
            if p in fallados:
                st.session_state["portal_estado"][p] = "fallo"
            elif p in portales_sel:
                st.session_state["portal_estado"][p] = "ok"
            else:
                st.session_state["portal_estado"][p] = "no_usado"

    if resultado is not None:
        st.session_state["resultado"] = resultado
        st.session_state["pagina_actual"] = 1

# ---------------------------------------------------------------------------
# Visualización de resultados
# ---------------------------------------------------------------------------

resultado = st.session_state.get("resultado")
if resultado is None:
    st.info("Configurá los criterios y presioná **Buscar** para ver los resultados.")
    st.stop()

aceptadas = resultado.aceptadas
excepciones = resultado.excepciones
todas_validas = aceptadas + excepciones

# Aviso de portales fallados (solo modo real)
portales_fallidos = st.session_state.get("portal_estado", {})
fallados_lista = [p for p, e in portales_fallidos.items() if e == "fallo"]
if not modo_demo and fallados_lista:
    st.markdown(
        '<div style="background-color:#c0392b;color:#ffffff;padding:12px;border-radius:6px;margin-bottom:16px;">'
        '<strong>⚠️ Algunos portales fallaron (bloqueo externo):</strong><br>'
        + ", ".join(fallados_lista)
        + '. Están bloqueando peticiones automáticas (403/405/CAPTCHA). '
        'No es un error de la aplicación: el motor continuó con los portales disponibles.'
        '</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")
st.subheader("Resultados")

# Métricas
precios = [p.precio_usd for p in todas_validas if p.precio_usd is not None]
metros = [p.metros2 for p in todas_validas if p.metros2 > 0]

col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
with col_m1:
    st.metric("Total válidas", len(todas_validas))
with col_m2:
    if precios:
        st.metric("Precio promedio (USD)", f"{sum(precios)/len(precios):,.0f}")
    else:
        st.metric("Precio promedio (USD)", "—")
with col_m3:
    if precios:
        st.metric("Precio mínimo (USD)", f"{min(precios):,.0f}")
    else:
        st.metric("Precio mínimo (USD)", "—")
with col_m4:
    if precios:
        st.metric("Precio máximo (USD)", f"{max(precios):,.0f}")
    else:
        st.metric("Precio máximo (USD)", "—")
with col_m5:
    if metros:
        st.metric("Superficie promedio (m²)", f"{sum(metros)/len(metros):,.1f}")
    else:
        st.metric("Superficie promedio (m²)", "—")

st.caption(
    f"Revisadas: {resultado.total_revisadas} | "
    f"Aceptadas: {len(aceptadas)} | "
    f"Excepciones (escalera/sin ascensor): {len(excepciones)} | "
    f"Rechazadas: {len(resultado.rechazadas)}"
)

# ---------------------------------------------------------------------------
# Filtros rápidos post-búsqueda
# ---------------------------------------------------------------------------

st.markdown("#### Filtros rápidos")
col_f1, col_f2, col_f3 = st.columns([0.25, 0.25, 0.50])
with col_f1:
    barrios_disponibles = sorted({p.barrio for p in todas_validas})
    filtro_barrio = st.multiselect("Barrio", options=barrios_disponibles, default=[])
with col_f2:
    tipos_disponibles = sorted({p.tipo for p in todas_validas})
    filtro_tipo = st.multiselect("Tipo", options=tipos_disponibles, default=[])
with col_f3:
    filtro_texto = st.text_input("Texto libre (descripción / dirección / URL)")

filtradas = todas_validas
if filtro_barrio:
    filtradas = [p for p in filtradas if p.barrio in filtro_barrio]
if filtro_tipo:
    filtradas = [p for p in filtradas if p.tipo in filtro_tipo]
if filtro_texto:
    texto = filtro_texto.lower()
    filtradas = [
        p for p in filtradas
        if texto in (p.descripcion or "").lower()
        or texto in (p.direccion or "").lower()
        or texto in (p.url or "").lower()
    ]

# ---------------------------------------------------------------------------
# Paginación (20 por página)
# ---------------------------------------------------------------------------

total = len(filtradas)
total_paginas = max(1, (total + PAGINA_TAMANIO - 1) // PAGINA_TAMANIO)
pagina_actual = st.session_state.get("pagina_actual", 1)
if pagina_actual < 1:
    pagina_actual = 1
if pagina_actual > total_paginas:
    pagina_actual = total_paginas
st.session_state["pagina_actual"] = pagina_actual

inicio = (pagina_actual - 1) * PAGINA_TAMANIO
fin = inicio + PAGINA_TAMANIO
pagina_items = filtradas[inicio:fin]

col_p1, col_p2, col_p3 = st.columns([0.2, 0.6, 0.2])
with col_p1:
    if st.button("⬅️ Anterior", disabled=(pagina_actual == 1), use_container_width=True):
        st.session_state["pagina_actual"] = pagina_actual - 1
        st.rerun()
with col_p2:
    st.markdown(
        f"<div style='text-align:center'>Página {pagina_actual} de {total_paginas} "
        f"({total} propiedad{'es' if total != 1 else ''})</div>",
        unsafe_allow_html=True,
    )
with col_p3:
    if st.button("Siguiente ➡️", disabled=(pagina_actual == total_paginas), use_container_width=True):
        st.session_state["pagina_actual"] = pagina_actual + 1
        st.rerun()

# ---------------------------------------------------------------------------
# Tarjetas horizontales por propiedad
# ---------------------------------------------------------------------------

st.markdown("#### Listado")

for p in pagina_items:
    with st.container():
        col_img, col_info, col_accion = st.columns([0.17, 0.63, 0.20])

        with col_img:
            if p.imagen_url:
                st.image(p.imagen_url, width=150)
            else:
                st.markdown(
                    '<div style="width:150px;height:100px;background:#eee;'
                    'border-radius:4px;display:flex;align-items:center;justify-content:center;'
                    'color:#999;font-size:12px;">Sin imagen</div>',
                    unsafe_allow_html=True,
                )

        with col_info:
            precio_txt = (
                f"**USD {p.precio_usd:,.0f}**"
                if p.precio_usd is not None
                else "Sin precio"
            )
            st.markdown(precio_txt)
            st.caption(
                f"{p.tipo} · {p.barrio} · {p.ambientes} amb · {p.metros2:g} m²"
            )
            if p.direccion:
                st.caption(f"📍 {p.direccion}")

            # Tags de colores
            tags = []
            if p.tiene_balcon:
                tags.append('<span style="background:#27ae60;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Balcón</span>')
            if p.tiene_patio:
                tags.append('<span style="background:#16a085;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Patio</span>')
            if p.escalera_sin_ascensor:
                tags.append('<span style="background:#c0392b;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Escalera</span>')
            if p.apto_credito:
                tags.append('<span style="background:#8e44ad;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;">Apto crédito</span>')
            if p.es_excepcion:
                tags.append('<span style="background:#e74c3c;color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:bold;">Excepción</span>')
            if tags:
                st.markdown(" ".join(tags), unsafe_allow_html=True)

        with col_accion:
            if p.url:
                st.link_button("Ver aviso", p.url, use_container_width=True)
            else:
                st.button("Sin URL", disabled=True, use_container_width=True)

        st.divider()

# ---------------------------------------------------------------------------
# Exportación en memoria (3 st.download_button, sin escribir en disco)
# ---------------------------------------------------------------------------

if todas_validas:
    st.markdown("#### Exportar resultados")
    col_e1, col_e2, col_e3 = st.columns(3)
    exportables = todas_validas
    with col_e1:
        nombre_csv, bytes_csv = exportar_en_memoria(exportables, "csv")
        st.download_button(
            "⬇️ CSV",
            data=bytes_csv,
            file_name=nombre_csv,
            mime="text/csv",
            use_container_width=True,
        )
    with col_e2:
        nombre_json, bytes_json = exportar_en_memoria(exportables, "json")
        st.download_button(
            "⬇️ JSON",
            data=bytes_json,
            file_name=nombre_json,
            mime="application/json",
            use_container_width=True,
        )
    with col_e3:
        nombre_xlsx, bytes_xlsx = exportar_en_memoria(exportables, "excel")
        st.download_button(
            "⬇️ Excel",
            data=bytes_xlsx,
            file_name=nombre_xlsx,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
