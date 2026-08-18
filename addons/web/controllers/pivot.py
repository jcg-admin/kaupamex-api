"""Exportación de tabla dinámica a XLSX — adaptación de ``odoo19c:
addons/web/controllers/pivot.py``, licencia LGPL-3 (``web/__manifest__.py``,
``odoo-tools@622ddc2a``) — copia + adaptación con atribución (DEC-KX-03).

Cierra la tarea **#397** (auditoría ``check_mirrored_roots.py``, hueco de
porte de ``controllers/pivot.py``, 13 archivos / 22 ``def`` del addon raíz
``web``).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``, sobre la clase única
``TableExporter``): **1** método (``export_xlsx``). **1 portado**, **0
ausentes**.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===================================  ========================================
Referencia                            Aquí
===================================  ========================================
``TableExporter.export_xlsx``         ``export_xlsx()`` — ``GET
(``:16``, ``http``, ``auth="user"``)  /api/v2/web/pivot/export_xlsx/?data=<json>``
===================================  ========================================

Sin dependencia de modelo — CONSTRUIDO sobre datos ya calculados
====================================================================

La referencia no consulta ningún modelo: recibe ``data`` (el JSON que la
tabla dinámica del cliente ya computó — cabeceras de columna, cabeceras de
medida, filas) y lo vuelca a una hoja de cálculo con ``xlsxwriter``. El
algoritmo de volcado (los cuatro pasos: cabeceras de columna, cabeceras de
medida, datos) se porta **verbatim**, celda por celda — no hay Odoo del que
divergir aquí, sólo formato de archivo.

Dos divergencias declaradas
=============================

1. **``osutil.clean_filename``** no existe en este árbol; se reusa
   ``export.py::_clean_filename`` (mismo contrato: caracteres prohibidos de
   nombre de archivo → ``_``), evitando duplicar el mismo recorte dos veces
   en el addon.
2. **``request.make_response``** (Werkzeug) → ``HttpResponse`` de Django +
   ``export.py::_content_disposition`` para la cabecera RFC 6266, mismo
   patrón que ``CSVExport``/``ExcelExport`` de ``export.py``.
"""
import io
import json
from collections import deque

import xlsxwriter
from django.http import HttpResponse
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.web.controllers.export import _clean_filename, _content_disposition

#: Deliberadamente amplia (cualquier usuario autenticado puede volcar los
#: datos que su propio cliente ya calculó) — mismo criterio que
#: ``web.export`` en este mismo addon.
_PIVOT_EXPORT_CAPABILITY = 'web.pivot.export'


@extend_schema(
    tags=['web'],
    summary='Exportar una tabla dinámica a XLSX',
    parameters=[
        OpenApiParameter(
            'data', str, required=True,
            description='JSON con {title, model, measure_count, '
                        'col_group_headers, measure_headers, rows}.'),
    ],
    responses={
        200: OpenApiResponse(description='application/vnd.openxmlformats-'
                                          'officedocument.spreadsheetml.sheet'),
        400: OpenApiResponse(description='sin datos que exportar'),
    },
)
@api_view(['GET'])
@require_capability(_PIVOT_EXPORT_CAPABILITY)
def export_xlsx(request):
    """≙ ``TableExporter.export_xlsx`` de la referencia — ``GET
    /api/v2/web/pivot/export_xlsx/?data=<json>``.
    """
    raw = request.query_params.get('data')
    if not raw:
        return Response(
            {'codigo_error': 'DATA_REQUIRED'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        jdata = json.loads(raw)
    except (TypeError, ValueError):
        return Response(
            {'codigo_error': 'INVALID_JSON'}, status=status.HTTP_400_BAD_REQUEST)
    if not jdata:
        return Response(
            {'codigo_error': 'DATA_REQUIRED', 'detail': 'No data to export.'},
            status=status.HTTP_400_BAD_REQUEST)

    xlsx_data = _pivot_to_xlsx(jdata)
    filename = _clean_filename(f"Pivot {jdata['title']} ({jdata['model']})") + '.xlsx'
    response = HttpResponse(
        xlsx_data,
        content_type='application/vnd.openxmlformats-officedocument'
                      '.spreadsheetml.sheet')
    response['Content-Disposition'] = _content_disposition(filename)
    return response


def _pivot_to_xlsx(jdata):
    """≙ el cuerpo de ``TableExporter.export_xlsx`` de la referencia —
    verbatim, celda por celda (ver "Sin dependencia de modelo" arriba)."""
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet(jdata['title'])

    header_bold = workbook.add_format({'bold': True, 'pattern': 1, 'bg_color': '#AAAAAA'})
    header_plain = workbook.add_format({'pattern': 1, 'bg_color': '#AAAAAA'})
    bold = workbook.add_format({'bold': True})

    measure_count = min(jdata['measure_count'], 100000)

    # Paso 1: cabeceras de grupo de columna.
    col_group_headers = jdata['col_group_headers']

    # x,y: coordenadas actuales. carry: cola con celdas de altura >= 2 que
    # necesitan celdas vacías debajo cuando el código de dibujo avanza.
    x, y, carry = 1, 0, deque()
    for i, header_row in enumerate(col_group_headers):
        worksheet.write(i, 0, '', header_plain)
        for header in header_row:
            while (carry and carry[0]['x'] == x):
                cell = carry.popleft()
                for j in range(measure_count):
                    worksheet.write(y, x + j, '', header_plain)
                if cell['height'] > 1:
                    carry.append({'x': x, 'height': cell['height'] - 1})
                x = x + measure_count
            width = min(header['width'], 100000)
            for j in range(width):
                worksheet.write(y, x + j, header['title'] if j == 0 else '', header_plain)
            if header['height'] > 1:
                carry.append({'x': x, 'height': header['height'] - 1})
            x = x + width
        while (carry and carry[0]['x'] == x):
            cell = carry.popleft()
            for j in range(measure_count):
                worksheet.write(y, x + j, '', header_plain)
            if cell['height'] > 1:
                carry.append({'x': x, 'height': cell['height'] - 1})
            x = x + measure_count
        x, y = 1, y + 1

    # Paso 2: cabeceras de medida.
    measure_headers = jdata['measure_headers']

    if measure_headers:
        worksheet.write(y, 0, '', header_plain)
        for measure in measure_headers:
            style = header_bold if measure['is_bold'] else header_plain
            worksheet.write(y, x, measure['title'], style)
            x = x + 1
        x, y = 1, y + 1
        # Ancho mínimo de columna 16 (~88px), igual que la referencia.
        worksheet.set_column(0, len(measure_headers), 16)

    # Paso 3: datos.
    x = 0
    for row in jdata['rows']:
        worksheet.write(y, x, f"{row['indent'] * '     '}{row['title']}", header_plain)
        for cell in row['values']:
            x = x + 1
            if cell.get('is_bold', False):
                worksheet.write(y, x, cell['value'], bold)
            else:
                worksheet.write(y, x, cell['value'])
        x, y = 0, y + 1

    workbook.close()
    return output.getvalue()
