"""Exportadores de resultados a CSV, JSON y Excel.

Escribe los archivos en disco (carpeta data/) únicamente. Para la interfaz
web (Streamlit) los archivos se generan en memoria con io.BytesIO/StringIO
y se ofrecen mediante st.download_button, sin escribir en disco.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from io import BytesIO, StringIO
from typing import Iterable

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from src.models import Propiedad

# Orden fijo de columnas para exportación.
CAMPOS_EXPORT = [
    "portal",
    "barrio",
    "tipo",
    "ambientes",
    "metros2",
    "precio_usd",
    "moneda_original",
    "precio_original",
    "direccion",
    "tiene_balcon",
    "tiene_patio",
    "escalera_sin_ascensor",
    "apto_credito",
    "es_excepcion",
    "imagen_url",
    "url",
    "fecha_publicacion",
    "descripcion",
]


def _nombre_archivo(nombre: str | None, extension: str) -> str:
    if nombre:
        base = nombre
    else:
        base = datetime.now().strftime("inmuebles_%Y%m%d_%H%M%S")
    return f"{base}.{extension}" if not nombre else f"{nombre}.{extension}"


def _asegurar_carpeta(carpeta: str) -> None:
    os.makedirs(carpeta, exist_ok=True)


def _datos(propiedades: Iterable[Propiedad]) -> list[dict]:
    return [p.to_dict() for p in propiedades]


def exportar_csv(
    propiedades: Iterable[Propiedad], carpeta: str, nombre: str | None = None
) -> str:
    _asegurar_carpeta(carpeta)
    ruta = os.path.join(carpeta, _nombre_archivo(nombre, "csv"))
    datos = _datos(propiedades)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CAMPOS_EXPORT, extrasaction="ignore")
        writer.writeheader()
        for fila in datos:
            writer.writerow({k: fila.get(k, "") for k in CAMPOS_EXPORT})
    return ruta


def exportar_json(
    propiedades: Iterable[Propiedad], carpeta: str, nombre: str | None = None
) -> str:
    _asegurar_carpeta(carpeta)
    ruta = os.path.join(carpeta, _nombre_archivo(nombre, "json"))
    datos = _datos(propiedades)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    return ruta


def exportar_excel(
    propiedades: Iterable[Propiedad], carpeta: str, nombre: str | None = None
) -> str:
    _asegurar_carpeta(carpeta)
    ruta = os.path.join(carpeta, _nombre_archivo(nombre, "xlsx"))
    datos = _datos(propiedades)
    wb = Workbook()
    ws = wb.active
    ws.title = "Propiedades"
    # Encabezados
    for col_idx, campo in enumerate(CAMPOS_EXPORT, start=1):
        celda = ws.cell(row=1, column=col_idx, value=campo)
        celda.font = None  # negrita simple opcional; se deja estilo por defecto
    # Filas
    for fila_idx, fila in enumerate(datos, start=2):
        for col_idx, campo in enumerate(CAMPOS_EXPORT, start=1):
            ws.cell(row=fila_idx, column=col_idx, value=fila.get(campo, ""))
    # Ajuste básico de ancho de columnas
    for col_idx in range(1, len(CAMPOS_EXPORT) + 1):
        letra = get_column_letter(col_idx)
        ws.column_dimensions[letra].width = 18
    wb.save(ruta)
    return ruta


def exportar_en_memoria(
    propiedades: Iterable[Propiedad], formato: str
) -> tuple[str, bytes]:
    """Genera un archivo en memoria para descarga web.

    Devuelve (nombre_archivo, bytes). No escribe en disco.
    """
    datos = _datos(propiedades)
    nombre_base = datetime.now().strftime("inmuebles_%Y%m%d_%H%M%S")
    if formato == "csv":
        buffer = StringIO()
        writer = csv.DictWriter(buffer, fieldnames=CAMPOS_EXPORT, extrasaction="ignore")
        writer.writeheader()
        for fila in datos:
            writer.writerow({k: fila.get(k, "") for k in CAMPOS_EXPORT})
        nombre = f"{nombre_base}.csv"
        return nombre, buffer.getvalue().encode("utf-8")
    if formato == "json":
        nombre = f"{nombre_base}.json"
        return nombre, json.dumps(datos, ensure_ascii=False, indent=2).encode("utf-8")
    if formato == "excel":
        nombre = f"{nombre_base}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Propiedades"
        for col_idx, campo in enumerate(CAMPOS_EXPORT, start=1):
            ws.cell(row=1, column=col_idx, value=campo)
        for fila_idx, fila in enumerate(datos, start=2):
            for col_idx, campo in enumerate(CAMPOS_EXPORT, start=1):
                ws.cell(row=fila_idx, column=col_idx, value=fila.get(campo, ""))
        buffer = BytesIO()
        wb.save(buffer)
        return nombre, buffer.getvalue()
    raise ValueError(f"Formato no soportado: {formato}")


def exportar_propiedades(
    propiedades: Iterable[Propiedad],
    formatos: Iterable[str],
    carpeta: str = "data",
    nombre: str | None = None,
) -> dict[str, str]:
    """Exporta a los formatos solicitados en la carpeta indicada.

    Devuelve un diccionario {formato: ruta_archivo}.
    """
    rutas: dict[str, str] = {}
    lista = list(propiedades)
    for fmt in formatos:
        if fmt == "csv":
            rutas["csv"] = exportar_csv(lista, carpeta, nombre)
        elif fmt == "json":
            rutas["json"] = exportar_json(lista, carpeta, nombre)
        elif fmt == "excel":
            rutas["excel"] = exportar_excel(lista, carpeta, nombre)
        else:
            logging.getLogger(__name__).warning("Formato desconocido ignorado: %s", fmt)
    return rutas
