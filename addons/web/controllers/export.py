"""Exportación de datos — adaptación de ``odoo19c: addons/web/controllers/export.py``.

``LGPL-3`` (``web/__manifest__.py``) — copia + adaptación con atribución.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===================================  ==========================================
Referencia                            Aquí
===================================  ==========================================
``Export.formats``                    ``formats()`` + vista ``web_export_formats``
``Export.get_fields``                 ``get_fields()`` + vista ``web_export_get_fields``
``Export.namelist``                   ``namelist()`` + vista ``web_export_namelist``
``Export.fields_info``                ``fields_info()`` (idéntico nombre)
``Export.graft_subfields``            ``graft_subfields()`` (idéntico nombre)
``Export._get_property_fields``       ``_get_property_fields()`` — devuelve
                                       ``{}`` siempre; ver "Lo que NO cubre".
``ExportFormat`` (+ ``http.Controller``) ``ExportFormat`` (clase base, sin
                                       ``http.Controller`` — la ruta la resuelve
                                       la subclase DRF)
``CSVExport``/``ExcelExport``         ``CSVExport``/``ExcelExport``
                                       (``ExportFormat`` + ``APIView``)
``CSVExport.web_export_csv``          ``CSVExport.get`` (dispatch DRF) vía
                                       ``_export_response``
``ExcelExport.web_export_xlsx``       ``ExcelExport.get`` (dispatch DRF) vía
                                       ``_export_response``
``GroupsTreeNode``                    ``GroupsTreeNode`` (idéntico nombre y
                                       métodos)
``ExportXlsxWriter``                  ``ExportXlsxWriter`` (idéntico nombre y
                                       métodos)
``GroupExportXlsxWriter``             ``GroupExportXlsxWriter`` (idéntico)
``Model.fields_get()``                ``_fields_get()`` — CONSTRUIDO (Rule 7):
                                       Django no expone un equivalente; se
                                       deriva de ``model._meta.get_fields()``
                                       reusando ``IrModelFields.ttype_for``
                                       (``addons.base.models.ir_model``).
``Model.export_data()``               ``_export_rows()``/``_object_export_lines()``
                                       — CONSTRUIDO, con una limitación
                                       declarada (ver abajo).
``Model.formatted_read_group()``      ``_build_groups_tree()`` — usa
                                       ``django.contrib.postgres.aggregates.ArrayAgg``
                                       (PostgreSQL nativo, Rule 7: cuando el
                                       stack SÍ lo trae, se usa en vez de
                                       fabricarlo).
``Model.browse()``/``Model.search()`` ``QuerySet.filter(pk__in=ids)`` /
                                       ``QuerySet.filter(osv.expression.to_q(domain))``
===================================  ==========================================

Rutas
=====

============================  =======  ============================================
Referencia                    Aquí (misma forma HTTP: jsonrpc→POST, http→GET)
============================  =======  ============================================
``/web/export/formats``       POST     ``/api/v2/web/export/formats/``
``/web/export/get_fields``    POST     ``/api/v2/web/export/get_fields/``
``/web/export/namelist``      POST     ``/api/v2/web/export/namelist/``
``/web/export/csv``           GET      ``/api/v2/web/export/csv/?data=<json>``
``/web/export/xlsx``          GET      ``/api/v2/web/export/xlsx/?data=<json>``
============================  =======  ============================================

El wiring de ``urls.py`` es de la fase de consolidación (no se toca aquí, ver
el prompt de esta pasada). La capacidad ``web.export`` (DEC-11, fail-closed)
tampoco está sembrada — sin esa fila, sólo el superadmin puede ejercer estas
vistas hasta que se dé de alta (dato, no migración; ver
``porte-completo-no-parcial.md``).

Divergencias declaradas
========================

1. **``model`` usa la convención del proyecto** — ``app_label.ModelName``
   (≙ ``ir.model.model``, ver ``addons.base.models.ir_model``), no el
   ``dominio.punto`` de Odoo (``'sale.order'``).
2. **``data`` sigue siendo JSON en un query param** en ``csv``/``xlsx`` (igual
   que la referencia, que es ``type='http'``): el body de una petición GET no
   es el canal RESTful habitual, pero es la forma exacta que la referencia ya
   usa para estas dos rutas — no se inventa un contrato nuevo.
3. **El contrato de ``fields`` en el payload de exportación** es
   ``[{'name': ..., 'label': ..., 'type': ...}]`` — igual que
   ``ExportXlsxWriter``/``base()`` de la referencia lo consumen directamente
   (el cliente JS de la referencia transforma el árbol de ``get_fields()``,
   con clave ``field_type``, a esta forma antes de enviarlo; esa
   transformación es plumbing de UI, fuera de este controlador).

Lo que esta adaptación NO cubre
================================

1. **``_get_property_fields`` no resuelve nada** — ``fields.Properties``/
   ``PropertiesDefinition`` (``orm/fields_properties.py``) son alias directos
   de ``JSONField``, sin la metadata ``definition_record``/
   ``definition_record_field`` que la referencia lee para expandir
   sub-campos por registro. Es divergencia de mecanismo, no ausencia de
   intento: no hay señal genérica de la que derivarlo. Devuelve ``{}``
   (cero propiedades dinámicas), que es el resultado correcto para este
   stack — no un stub que finja resultados.
2. **``_export_rows``/``_object_export_lines`` expanden UN solo nivel** de
   one2many/many2many a filas múltiples (p. ej. ``line_ids/product_id/name``
   funciona). La referencia soporta anidamiento arbitrario (un o2m dentro de
   otro o2m); si dos campos de la selección expanden por separado, sólo el
   primero gobierna el número de filas y el segundo se alinea por índice
   (recorta en vez de producir el producto cartesiano). Cubre el caso de uso
   dominante (una tabla de líneas); el caso de doble anidamiento no tiene
   consumidor conocido en este proyecto.
3. **``groupby`` no admite la sintaxis ``campo:granularity``** de fecha de la
   referencia (``date:month``, etc.) — se agrupa por el valor crudo del
   campo. Sin consumidor de reportes por fecha agrupada en este controlador
   todavía.
4. **Sin ``split_every``/``PREFETCH_MAX``** — la referencia trocea el
   recordset para no inflar su caché de ``browse()``. Django no cachea así:
   ``QuerySet.iterator()`` ya transmite fila a fila desde PostgreSQL, así que
   el problema que ese troceo resolvía no existe aquí en la misma forma.

Todo lo anterior es DESCONOCIDO/no-cubierto declarado — no divergencia
silenciosa (``porte-completo-no-parcial.md``).
"""
import csv
import datetime
import functools
import io
import itertools
import json
import logging
import re
from collections import OrderedDict, defaultdict
from decimal import Decimal
from urllib.parse import quote

import xlsxwriter
from django.apps import apps
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count, Max
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from exceptions import UserError
from osv.expression import to_q

from addons.authz.permissions import HasCapability, RequireCapability
from addons.base.models import IrExports, IrModelFields, ResCurrency
from addons.web.controllers.serializers import (
    ExportFormatSerializer,
    ExportFieldTreeNodeSerializer,
    GetFieldsRequestSerializer,
    NamelistRequestSerializer,
)

_logger = logging.getLogger(__name__)

#: Capacidad DEC-11 que gobierna las cinco vistas de este módulo. Dato de
#: seeding pendiente (ver el docstring del módulo) — no requiere migración.
_EXPORT_CAPABILITY = 'web.export'


# === Utilidades genéricas (sin dependencia de Odoo, portadas verbatim) =====

def none_values_filtered(func):
    """≙ referencia — envuelve ``func`` descartando ``None`` del iterable."""
    @functools.wraps(func)
    def wrap(iterable):
        return func(v for v in iterable if v is not None)
    return wrap


def allow_empty_iterable(func):
    """≙ referencia.

    Algunas funciones (``max``/``min`` sin ``default``) no aceptan iterables
    vacíos. Devuelve una versión de ``func`` que responde ``None`` en ese
    caso, en vez de lanzar ``ValueError``.
    """
    @functools.wraps(func)
    def wrap(iterable):
        iterator = iter(iterable)
        try:
            value = next(iterator)
            return func(itertools.chain([value], iterator))
        except StopIteration:
            return None
    return wrap


OPERATOR_MAPPING = {
    'max': none_values_filtered(allow_empty_iterable(max)),
    'min': none_values_filtered(allow_empty_iterable(min)),
    'sum': sum,
    'bool_and': all,
    'bool_or': any,
}

#: ``ttype`` de Odoo cuyo agregador por defecto es ``'sum'`` cuando el campo
#: no declara otro explícitamente. Ver ``_aggregator_for``.
_NUMERIC_TTYPES = frozenset({'integer', 'float', 'monetary'})


def _aggregator_for(model, field_name):
    """Agregador de exportación — CONSTRUIDO (Rule 7).

    Odoo declara ``aggregator`` como atributo del propio campo
    (``fields.Integer(aggregator='sum')``…). Nuestros alias en
    ``orm/fields_numeric.py`` (``Integer = models.IntegerField`` …) son
    ``Field`` de Django puros, sin ese atributo — así que se deriva del
    ``ttype`` (vía ``IrModelFields.ttype_for``, ``addons.base.models.ir_model``):
    ``'sum'`` para los tres tipos numéricos, el mismo valor por defecto que
    usa la referencia para ellos salvo sobreescritura explícita.
    """
    try:
        field = model._meta.get_field(field_name)
        ttype = IrModelFields.ttype_for(field)
    except Exception:
        return None
    return 'sum' if ttype in _NUMERIC_TTYPES else None


class GroupsTreeNode:
    """≙ referencia.

    Árbol ordenado de grupos construido desde el resultado de
    ``formatted_read_group`` (aquí, su equivalente construido:
    ``_build_groups_tree``). Cada leaf se inserta desde un dict con el
    conteo y las filas de datos del grupo; el árbol entero se arma
    insertando todas las leaves.
    """

    def __init__(self, model, fields, groupby, groupby_type):
        self._model = model
        self._export_field_names = fields  # ej. 'journal_id', 'account_id/name', ...
        self._groupby = groupby
        self._groupby_type = groupby_type

        self.count = 0  # Total de registros en el subárbol
        self.children = OrderedDict()
        self.data = []  # Sólo los nodos hoja tienen datos

    def _get_aggregate(self, field_name, data, aggregator):
        # Al exportar campos one2many puede haber varias líneas de datos por
        # registro; las celdas en blanco de líneas adicionales se rellenan
        # con '' — esto podría agregar '' junto a un entero o un float.
        data = (value for value in data if value != '')

        if aggregator == 'avg':
            return self._get_avg_aggregate(field_name, data)

        aggregate_func = OPERATOR_MAPPING.get(aggregator)
        if not aggregate_func:
            _logger.warning(
                "Agregador de exportación no soportado '%s' para el campo "
                '%s del modelo %s', aggregator, field_name, self._model._meta.label,
            )
            return None

        if self.data:
            return aggregate_func(data)
        return aggregate_func(
            child.aggregated_values.get(field_name) for child in self.children.values()
        )

    def _get_avg_aggregate(self, field_name, data):
        aggregate_func = OPERATOR_MAPPING.get('sum')
        if not self.count:
            return None
        if self.data:
            return aggregate_func(data) / self.count
        children_sums = (
            child.aggregated_values.get(field_name) * child.count
            for child in self.children.values()
        )
        return aggregate_func(children_sums) / self.count

    def _get_aggregated_field_names(self):
        """Nombres de campo exportados que tienen agregador."""
        aggregated_field_names = []
        for original_name in self._export_field_names:
            field_name = 'id' if original_name == '.id' else original_name
            if '/' in field_name:
                # Sin soporte de valor agregado para campos anidados,
                # p. ej. line_ids/analytic_line_ids/amount
                continue
            if _aggregator_for(self._model, field_name) is not None:
                aggregated_field_names.append(field_name)
        return aggregated_field_names

    # Propiedad perezosa que memoiza los valores agregados de los hijos para
    # evitar recómputos inútiles.
    @functools.cached_property
    def aggregated_values(self):
        aggregated_values = {}
        aggregated_field_names = self._get_aggregated_field_names()

        # Transpone la matriz de datos para agrupar los valores de cada
        # campo en un solo iterable.
        field_values = zip(*self.data)
        for field_name in self._export_field_names:
            field_data = self.data and next(field_values) or []

            if field_name in aggregated_field_names:
                name = 'id' if field_name == '.id' else field_name
                aggregator = _aggregator_for(self._model, name)
                aggregated_values[field_name] = self._get_aggregate(
                    field_name, field_data, aggregator)

        return aggregated_values

    def child(self, key):
        """Devuelve el hijo identificado por ``key``, insertando un nodo por
        defecto si aún no existe.
        """
        if key not in self.children:
            self.children[key] = GroupsTreeNode(
                self._model, self._export_field_names, self._groupby, self._groupby_type)
        return self.children[key]

    def insert_leaf(self, group, data):
        """Construye una hoja desde ``group`` y la inserta en el árbol."""
        leaf_path = [group.get(groupby_field) for groupby_field in self._groupby]
        count = group.pop('__count')

        # Recorre desde el grupo raíz hasta el grupo más profundo, el que
        # realmente contiene los datos de los registros.
        node = self  # raíz
        node.count += count
        for node_key in leaf_path:
            node = node.child(node_key)
            node.count += count

        node.data = data


class ExportXlsxWriter:
    """≙ referencia."""

    def __init__(self, fields, columns_headers, row_count):
        self.fields = fields
        self.columns_headers = columns_headers
        self.output = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.output, {'in_memory': True})
        self.header_style = self.workbook.add_format({'bold': True})
        self.date_style = self.workbook.add_format(
            {'text_wrap': True, 'num_format': 'yyyy-mm-dd'})
        self.datetime_style = self.workbook.add_format(
            {'text_wrap': True, 'num_format': 'yyyy-mm-dd hh:mm:ss'})
        self.base_style = self.workbook.add_format({'text_wrap': True})
        # FIXME: debería depender de los decimales del campo.
        self.float_style = self.workbook.add_format(
            {'text_wrap': True, 'num_format': '#,##0.00'})

        # FIXME: debería depender del campo de moneda de cada fila (y quizás
        # añadir el símbolo de moneda).
        decimal_places = ResCurrency.objects.aggregate(dp=Max('decimal_places'))['dp']
        self.monetary_style = self.workbook.add_format(
            {'text_wrap': True, 'num_format': f'#,##0.{(decimal_places or 2) * "0"}'})

        header_bold_props = {'text_wrap': True, 'bold': True, 'bg_color': '#e9ecef'}
        self.header_bold_style = self.workbook.add_format(header_bold_props)
        self.header_bold_style_float = self.workbook.add_format(
            dict(**header_bold_props, num_format='#,##0.00'))
        self.header_bold_style_monetary = self.workbook.add_format(
            dict(**header_bold_props, num_format=f'#,##0.{(decimal_places or 2) * "0"}'))

        self.worksheet = self.workbook.add_worksheet()
        self.value = False

        if row_count > self.worksheet.xls_rowmax:
            raise UserError(
                f'Hay demasiadas filas ({row_count} filas, límite: '
                f'{self.worksheet.xls_rowmax}) para exportar en formato Excel '
                '2007-2013 (.xlsx). Considera dividir la exportación.'
            )

    def __enter__(self):
        self.write_header()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()

    def write_header(self):
        # Escribe el encabezado principal
        for i, column_header in enumerate(self.columns_headers):
            self.write(0, i, column_header, self.header_style)
        self.worksheet.set_column(0, max(0, len(self.columns_headers) - 1), 30)  # ~220px

    def close(self):
        self.workbook.close()
        with self.output:
            self.value = self.output.getvalue()

    def write(self, row, column, cell_value, style=None):
        self.worksheet.write(row, column, cell_value, style)

    def write_cell(self, row, column, cell_value):
        cell_style = self.base_style

        if isinstance(cell_value, bytes):
            try:
                # como la exportación xlsx es "cruda", aquí puede llegar un
                # objeto bytes. xlsxwriter no soporta bytes en Python 3 →
                # se asume base64 y se decodifica a string; si falla, avisa
                # que no se puede exportar.
                cell_value = cell_value.decode()
            except UnicodeDecodeError:
                raise UserError(
                    'Los campos binarios no se pueden exportar a Excel salvo '
                    'que su contenido esté codificado en base64. No parece '
                    f'ser el caso de {self.columns_headers[column]}.'
                ) from None
        elif isinstance(cell_value, (list, tuple, dict)):
            cell_value = str(cell_value)

        if isinstance(cell_value, str):
            if len(cell_value) > self.worksheet.xls_strmax:
                cell_value = (
                    'El contenido de esta celda es demasiado largo para un '
                    f'archivo XLSX (más de {self.worksheet.xls_strmax} '
                    'caracteres). Usa el formato CSV para esta exportación.'
                )
            else:
                cell_value = cell_value.replace('\r', ' ')
        elif isinstance(cell_value, datetime.datetime):
            cell_style = self.datetime_style
        elif isinstance(cell_value, datetime.date):
            cell_style = self.date_style
        elif isinstance(cell_value, (float, Decimal)):
            field = self.fields[column]
            cell_style = (
                self.monetary_style if field.get('type') == 'monetary' else self.float_style
            )
            cell_value = float(cell_value)
        self.write(row, column, cell_value, cell_style)


class GroupExportXlsxWriter(ExportXlsxWriter):
    """≙ referencia."""

    def write_group(self, row, column, group_name, group, group_depth=0):
        group_name = (
            group_name[1] if isinstance(group_name, tuple) and len(group_name) > 1
            else group_name
        )
        if group._groupby_type[group_depth] != 'boolean':
            group_name = group_name if group_name not in (None, False) else 'Sin definir'
        row, column = self._write_group_header(row, column, group_name, group, group_depth)

        # Escribe recursivamente los subgrupos
        for child_group_name, child_group in group.children.items():
            row, column = self.write_group(row, column, child_group_name, child_group, group_depth + 1)

        for record in group.data:
            row, column = self._write_row(row, column, record)
        return row, column

    def _write_row(self, row, column, data):
        for value in data:
            self.write_cell(row, column, value)
            column += 1
        return row + 1, 0

    def _write_group_header(self, row, column, label, group, group_depth=0):
        aggregates = group.aggregated_values

        label = '%s%s (%s)' % ('    ' * group_depth, label, group.count)
        self.write(row, column, label, self.header_bold_style)
        for field in self.fields[1:]:  # Sin agregados en la primera columna (título del grupo)
            column += 1
            aggregated_value = aggregates.get(field['name'])
            header_style = self.header_bold_style
            if field.get('type') == 'monetary':
                header_style = self.header_bold_style_monetary
            elif field.get('type') == 'float':
                header_style = self.header_bold_style_float
            else:
                aggregated_value = str(aggregated_value if aggregated_value is not None else '')
            self.write(row, column, aggregated_value, header_style)
        return row + 1, 0


# === Introspección de modelo — CONSTRUIDO, Rule 7 =========================
#
# Django no expone un equivalente genérico a ``Model.fields_get()``. Se
# construye a partir de ``model._meta.get_fields()``, reusando
# ``IrModelFields.ttype_for`` (``addons.base.models.ir_model``) para el
# mapeo tipo-Django → ttype-Odoo, que YA existe en el proyecto para la
# reflexión de ``ir.model.fields`` — no se duplica el mapa.

def _get_model(model_label):
    """``'app_label.ModelName'`` → clase de modelo (≙ ``request.env[model]``)."""
    app_label, model_name = model_label.split('.', 1)
    return apps.get_model(app_label, model_name)


def _field_meta(field):
    """Metadata de un campo Django, concreto o reverso — lo que
    ``Model.fields_get()`` (ausente en Django) necesita por campo."""
    if getattr(field, 'one_to_many', False) and not getattr(field, 'concrete', True):
        remote = field.related_model
        return {
            'type': 'one2many',
            'relation': f'{remote._meta.app_label}.{remote._meta.object_name}',
            'relation_field': field.field.name,
            'string': str(field.field.verbose_name) or field.get_accessor_name(),
            'required': False,
            'readonly': True,  # un reverso o2m no se escribe desde este lado
        }
    if getattr(field, 'many_to_many', False) and not getattr(field, 'concrete', True):
        remote = field.related_model
        return {
            'type': 'many2many',
            'relation': f'{remote._meta.app_label}.{remote._meta.object_name}',
            'relation_field': '',
            'string': field.get_accessor_name(),
            'required': False,
            'readonly': True,
        }
    remote = getattr(field, 'related_model', None)
    return {
        'type': IrModelFields.ttype_for(field),
        'relation': f'{remote._meta.app_label}.{remote._meta.object_name}' if remote else '',
        'relation_field': '',
        'string': str(getattr(field, 'verbose_name', '') or field.name),
        'required': not getattr(field, 'null', True) and not getattr(field, 'blank', True),
        'readonly': not getattr(field, 'editable', True),
    }


def _fields_get(model):
    """≙ ``Model.fields_get()`` de la referencia — CONSTRUIDO vía
    introspección de ``model._meta.get_fields()``."""
    result = {
        'id': {
            'type': 'integer', 'string': 'ID', 'required': False,
            'relation': '', 'relation_field': '', 'readonly': True,
            'default_export_compatible': True,
        },
    }
    for field in model._meta.get_fields():
        if field.name == 'id':
            continue
        meta = _field_meta(field)
        meta['default_export_compatible'] = True
        result[field.name] = meta
    return result


def _rec_name_fallback(model):
    """≙ ``Model._rec_name_fallback()`` — ``name`` si existe; si no, el
    primer ``CharField`` propio; si no, ``id``."""
    concrete_names = {f.name for f in model._meta.get_fields() if getattr(f, 'concrete', False)}
    if 'name' in concrete_names:
        return 'name'
    for f in model._meta.get_fields():
        if getattr(f, 'concrete', False) and f.get_internal_type() == 'CharField':
            return f.name
    return 'id'


def _get_property_fields(fields_map, model, domain=()):
    """≙ ``Export._get_property_fields`` — NO PORTADO (divergencia de
    mecanismo declarada en el docstring del módulo). Devuelve ``{}`` siempre:
    es el resultado correcto (cero propiedades dinámicas resueltas) para un
    stack donde ``fields.Properties``/``PropertiesDefinition`` son alias
    directos de ``JSONField``, sin la metadata que la referencia necesita
    para expandir sub-campos por registro.
    """
    return {}


def formats():
    """≙ ``Export.formats`` — formatos de exportación válidos.

    ``xlsxwriter`` es dependencia obligatoria del proyecto
    (``pyproject.toml``), así que — a diferencia de la referencia, que
    detecta su ausencia opcional — aquí ``xlsx`` nunca reporta error.
    """
    return [
        {'tag': 'xlsx', 'label': 'XLSX', 'error': None},
        {'tag': 'csv', 'label': 'CSV'},
    ]


def get_fields(model, domain, prefix='', parent_name='', import_compat=True,
                parent_field_type=None, parent_field=None, exclude=None):
    """≙ ``Export.get_fields`` — árbol de campos exportables/importables de
    ``model``, recorrido un nivel por llamada (igual que la referencia: el
    cliente expande una relación pidiendo el siguiente nivel con
    ``prefix``/``parent_field``).
    """
    fields_map = _fields_get(model)

    if import_compat:
        if parent_field_type in ('many2one', 'many2many'):
            rec_name = _rec_name_fallback(model)
            fields_map = {'id': fields_map['id'], rec_name: fields_map[rec_name]}
    else:
        fields_map = dict(fields_map)
        fields_map['.id'] = dict(fields_map['id'])

    fields_map['id'] = dict(fields_map['id'])
    fields_map['id']['string'] = 'ID externo'

    if not model._meta.managed:
        fields_map.pop('id', None)
    elif parent_field:
        parent_field = dict(parent_field)
        parent_field['string'] = 'ID externo'
        fields_map['id'] = parent_field
        fields_map['id']['type'] = parent_field.get('field_type', parent_field.get('type'))

    exportable_fields = {}
    for field_name, field in fields_map.items():
        if import_compat and field_name != 'id':
            if exclude and field_name in exclude:
                continue
            if field.get('readonly'):
                continue
        exportable_fields[field_name] = field

    exportable_fields.update(_get_property_fields(fields_map, model, domain=domain))

    fields_sequence = sorted(
        exportable_fields.items(), key=lambda field: field[1]['string'].lower())

    result = []
    for field_name, field in fields_sequence:
        ident = f'{prefix}/{field_name}' if prefix else field_name
        val = ident
        if field_name == 'name' and import_compat and parent_field_type in ('many2one', 'many2many'):
            # Añade el campo 'name' al expandir campos m2o/m2m en modo
            # compatible con importación
            val = prefix
        name = f'{parent_name}/{field["string"]}' if parent_name else field['string']
        field_dict = {
            'id': ident,
            'string': name,
            'value': val,
            'children': False,
            'field_type': field.get('type'),
            'required': field.get('required'),
            'relation_field': field.get('relation_field'),
            'default_export': import_compat and field.get('default_export_compatible'),
        }
        if len(ident.split('/')) < 3 and field.get('relation'):
            field_dict['value'] += '/id'
            field_dict['params'] = {
                'model': field['relation'],
                'prefix': ident,
                'name': name,
                'parent_field': field,
            }
            field_dict['children'] = True

        result.append(field_dict)

    return result


def fields_info(model, export_fields):
    """≙ ``Export.fields_info``."""
    field_info = []
    fields_map = _fields_get(model)
    fields_map.update(_get_property_fields(fields_map, model))
    if '.id' in export_fields:
        fields_map['.id'] = fields_map.get('id', {'string': 'ID'})

    for (base, length), subfields in itertools.groupby(
            sorted(export_fields),
            lambda field: (field.split('/', 1)[0], len(field.split('/', 1)))):
        subfields = list(subfields)
        if length == 2:
            # subfields es una secuencia de $base/*resto, aún sin cargar
            base_field = fields_map.get(base)
            if base_field is None or not base_field.get('relation'):
                continue
            field_info.extend(
                graft_subfields(
                    base_field['relation'], base, base_field['string'], subfields,
                ),
            )
        elif base in fields_map:
            field_dict = fields_map[base]
            field_info.append({
                'id': base,
                'string': field_dict['string'],
                'field_type': field_dict['type'],
            })

    indexes_dict = {fname: i for i, fname in enumerate(export_fields)}
    return sorted(field_info, key=lambda field_dict: indexes_dict[field_dict['id']])


def graft_subfields(model_label, prefix, prefix_string, fields):
    """≙ ``Export.graft_subfields``."""
    model = _get_model(model_label)
    export_fields = [field.split('/', 1)[1] for field in fields]
    return [
        dict(
            field_info,
            id=f"{prefix}/{field_info['id']}",
            string=f"{prefix_string}/{field_info['string']}",
        )
        for field_info in fields_info(model, export_fields)
    ]


def namelist(model, export_id):
    """≙ ``Export.namelist``."""
    export = IrExports.objects.filter(pk=export_id).first()
    if export is None:
        return []
    field_names = list(export.export_fields.order_by('id').values_list('name', flat=True))
    return fields_info(model, field_names)


# === Lectura de datos por registro — CONSTRUIDO, Rule 7 ====================
#
# Django no expone un equivalente a ``Model.export_data()``. Ver la
# limitación #2 declarada en el docstring del módulo: un solo nivel de
# expansión one2many/many2many.

def _resolve_scalar_path(obj, path):
    """Sigue ``a/b/c`` vía atributos many2one — sin expandir o2m/m2m (ese
    caso ya se resolvió en ``_resolve_field_path`` antes de llamar aquí)."""
    value = obj
    for segment in path.split('/'):
        if value is None:
            return ''
        if segment in ('.id', 'id'):
            value = getattr(value, 'pk', value)
            continue
        value = getattr(value, segment, '')
    if value is None or value is False:
        return ''
    return value


def _resolve_field_path(obj, path):
    """Valores (≥1) de ``path`` sobre ``obj``. Longitud > 1 sólo si el
    PRIMER segmento de ``path`` es un one2many o many2many del modelo de
    ``obj`` — un nivel de expansión (ver la limitación #2 del docstring del
    módulo).
    """
    head, _, rest = path.partition('/')
    if head in ('.id', 'id'):
        return [obj.pk]

    try:
        field = obj._meta.get_field(head)
    except Exception:
        return ['']

    if getattr(field, 'one_to_many', False) or getattr(field, 'many_to_many', False):
        accessor = field.name if getattr(field, 'concrete', True) else field.get_accessor_name()
        related = list(getattr(obj, accessor).all())
        if not related:
            return ['']
        return [
            _resolve_scalar_path(sub, rest) if rest else str(sub)
            for sub in related
        ]

    return [_resolve_scalar_path(obj, path)]


def _object_export_lines(obj, field_names):
    """Filas (≥1) de ``obj`` para ``field_names`` — ≙ lo que
    ``export_data()`` (ausente en Django) hace por registro."""
    lines = [[]]
    for field_name in field_names:
        values = _resolve_field_path(obj, field_name)
        if len(values) > len(lines):
            base_line = lines[0]
            lines = [list(base_line) for _ in values]
        for i, line in enumerate(lines):
            line.append(values[i] if i < len(values) else '')
    return lines


def _export_rows(objects, field_names):
    """≙ ``records.export_data(field_names).get('datas', [])`` de la
    referencia."""
    rows = []
    for obj in objects:
        rows.extend(_object_export_lines(obj, field_names))
    return rows


def _groupby_types(model, groupby):
    """≙ el ``groupby_type`` que ``ExportFormat.base`` calcula con
    ``Model._fields[x].type`` — aquí vía ``IrModelFields.ttype_for``."""
    types = []
    for g in groupby:
        base = g.split(':', 1)[0].split('.', 1)[0]
        try:
            field = model._meta.get_field(base)
            types.append(IrModelFields.ttype_for(field))
        except Exception:
            types.append('char')
    return types


def _build_groups_tree(model, base_queryset, field_names, groupby, ids, domain):
    """≙ el tramo de ``ExportFormat.base`` que arma el ``GroupsTreeNode``
    desde ``formatted_read_group`` — aquí, agregación nativa de PostgreSQL
    (``ArrayAgg``/``Count``, ``django.contrib.postgres``). El ORM SÍ trae
    este mecanismo (Rule 7: se usa, no se fabrica).
    """
    groupby_type = _groupby_types(model, groupby)
    tree = GroupsTreeNode(model, field_names, groupby, groupby_type)

    group_source = model.objects.filter(pk__in=ids) if ids else model.objects.filter(to_q(domain))
    groups_data = list(
        group_source.values(*groupby)
                    .annotate(agg_count=Count('pk'), agg_ids=ArrayAgg('pk'))
                    .order_by()
    )

    # Preserva el orden natural del modelo: se basa en base_queryset, que es
    # el resultado de Model.objects.filter(...) (mismo criterio que la
    # referencia con export_data() a partir de Model.search()).
    record_lines = {obj.pk: _object_export_lines(obj, field_names) for obj in base_queryset}

    record_to_groups = defaultdict(list)
    for group_index, group in enumerate(groups_data):
        for pk in group['agg_ids']:
            record_to_groups[pk].append(group_index)

    grouped_rows = [[] for _ in groups_data]
    for pk, lines in record_lines.items():
        for group_index in record_to_groups.get(pk, ()):
            grouped_rows[group_index].extend(lines)

    for group, rows in zip(groups_data, grouped_rows):
        leaf = {field: group[field] for field in groupby}
        leaf['__count'] = group['agg_count']
        tree.insert_leaf(leaf, rows)

    return tree


# === Filename / Content-Disposition — CONSTRUIDO ===========================

_UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n]+')


def _clean_filename(name):
    """≙ ``odoo.tools.osutil.clean_filename`` recortado — sustituye
    caracteres prohibidos en un nombre de archivo Windows/POSIX por ``_``."""
    cleaned = _UNSAFE_FILENAME_CHARS.sub('_', name).strip()
    return cleaned or 'export'


def _content_disposition(filename):
    """≙ ``odoo.http.content_disposition`` — adjunto con nombre UTF-8
    (RFC 6266 ``filename*``) y un fallback ASCII para clientes viejos."""
    ascii_name = filename.encode('ascii', 'replace').decode('ascii')
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(filename)}"
    )


# === Vistas DRF =============================================================

@extend_schema(
    tags=['web'],
    summary='Formatos de exportación disponibles',
    request=None,
    responses={200: ExportFormatSerializer(many=True)},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RequireCapability(_EXPORT_CAPABILITY)])
def web_export_formats(request):
    """≙ ``GET /web/export/formats`` de la referencia (aquí POST, sin body —
    consistente con el resto de rutas ``jsonrpc`` de este módulo)."""
    return Response(formats())


@extend_schema(
    tags=['web'],
    summary='Árbol de campos exportables de un modelo (un nivel)',
    request=GetFieldsRequestSerializer,
    responses={
        200: ExportFieldTreeNodeSerializer(many=True),
        400: OpenApiResponse(description='INVALID_PAYLOAD'),
        404: OpenApiResponse(description='MODEL_NOT_FOUND'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RequireCapability(_EXPORT_CAPABILITY)])
def web_export_get_fields(request):
    """≙ ``/web/export/get_fields`` de la referencia."""
    serializer = GetFieldsRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'codigo_error': 'INVALID_PAYLOAD', 'detail': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST)
    data = serializer.validated_data
    try:
        model = _get_model(data['model'])
    except (LookupError, ValueError):
        return Response({'codigo_error': 'MODEL_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

    result = get_fields(
        model, data.get('domain') or [],
        prefix=data.get('prefix', ''),
        parent_name=data.get('parent_name', ''),
        import_compat=data.get('import_compat', True),
        parent_field_type=data.get('parent_field_type'),
        exclude=data.get('exclude'),
    )
    return Response(result)


@extend_schema(
    tags=['web'],
    summary='Nombres de campo de una exportación guardada (ir.exports)',
    request=NamelistRequestSerializer,
    responses={
        200: ExportFieldTreeNodeSerializer(many=True),
        400: OpenApiResponse(description='INVALID_PAYLOAD'),
        404: OpenApiResponse(description='MODEL_NOT_FOUND'),
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated, RequireCapability(_EXPORT_CAPABILITY)])
def web_export_namelist(request):
    """≙ ``/web/export/namelist`` de la referencia."""
    serializer = NamelistRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {'codigo_error': 'INVALID_PAYLOAD', 'detail': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST)
    try:
        model = _get_model(serializer.validated_data['model'])
    except (LookupError, ValueError):
        return Response({'codigo_error': 'MODEL_NOT_FOUND'}, status=status.HTTP_404_NOT_FOUND)

    result = namelist(model, serializer.validated_data['export_id'])
    return Response(result)


class ExportFormat:
    """≙ referencia ``ExportFormat`` — sin ``http.Controller``: la ruta HTTP
    la resuelve la subclase DRF (``CSVExport``/``ExcelExport``)."""

    #: Content-Type de la respuesta. Las subclases lo fijan.
    content_type = None
    #: Extensión del archivo, con el punto (p. ej. ``'.csv'``).
    extension = None

    def filename(self, model_label):
        """Nombre de archivo (sin extensión) para ``model_label``."""
        try:
            model = _get_model(model_label)
        except (LookupError, ValueError):
            return model_label
        return f'{model._meta.verbose_name} ({model_label})'

    def from_data(self, fields, columns_headers, rows):
        """Convierte los datos exportados de Odoo a lo que produce esta
        clase de exportación.

        :params list fields: campos a exportar
        :params list rows: registros a exportar
        :rtype: bytes
        """
        raise NotImplementedError()

    def from_group_data(self, fields, columns_headers, groups):
        raise NotImplementedError()

    def base(self, payload):
        """≙ ``ExportFormat.base`` — arma la respuesta HTTP del archivo."""
        model_label = payload['model']
        field_defs = payload['fields']
        ids = payload.get('ids')
        domain = payload.get('domain') or []
        import_compat = bool(payload.get('import_compat'))

        model = _get_model(model_label)
        if not model._meta.managed:
            field_defs = [f for f in field_defs if f['name'] != 'id']

        field_names = [f['name'] for f in field_defs]
        if import_compat:
            columns_headers = field_names
        else:
            columns_headers = [f['label'].strip() for f in field_defs]

        base_qs = model.objects.filter(pk__in=ids) if ids else model.objects.filter(to_q(domain))

        groupby = payload.get('groupby')
        if not import_compat and groupby:
            tree = _build_groups_tree(model, base_qs, field_names, groupby, ids, domain)
            response_data = self.from_group_data(field_defs, columns_headers, tree)
        else:
            rows = _export_rows(base_qs.iterator(), field_names)
            response_data = self.from_data(field_defs, columns_headers, rows)

        _logger.info(
            'Usuario %s exportó %s registros de %r. Campos: %s. %s: %s',
            getattr(base_qs.model, '_meta', None) and payload.get('model'),
            len(ids) if ids else base_qs.count(), model_label,
            ','.join(field_names), 'muestra de IDs' if ids else 'Dominio',
            ids[:10] if ids else domain,
        )

        filename = _clean_filename(self.filename(model_label) + self.extension)
        response = HttpResponse(response_data, content_type=self.content_type)
        response['Content-Disposition'] = _content_disposition(filename)
        return response


def _export_response(exporter, request):
    """Envoltura DRF común de ``CSVExport.get``/``ExcelExport.get`` — ≙
    ``web_export_csv``/``web_export_xlsx`` de la referencia (parseo del
    ``data`` JSON + manejo de errores)."""
    raw = request.query_params.get('data')
    if not raw:
        return Response({'codigo_error': 'DATA_REQUIRED'}, status=status.HTTP_400_BAD_REQUEST)
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return Response({'codigo_error': 'INVALID_JSON'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        return exporter.base(payload)
    except UserError as exc:
        return Response(
            {'codigo_error': 'EXPORT_ERROR', 'detail': str(exc)},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except (KeyError, LookupError, ValueError) as exc:
        _logger.exception('Payload de exportación inválido.')
        return Response(
            {'codigo_error': 'INVALID_PAYLOAD', 'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST)


class CSVExport(ExportFormat, APIView):
    """≙ ``CSVExport`` — ``GET /api/v2/web/export/csv/?data=<json>``."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = _EXPORT_CAPABILITY
    content_type = 'text/csv;charset=utf8'
    extension = '.csv'

    def from_group_data(self, fields, columns_headers, groups):
        raise UserError('La exportación agrupada a CSV no está soportada.')

    def from_data(self, fields, columns_headers, rows):
        fp = io.StringIO()
        writer = csv.writer(fp, quoting=csv.QUOTE_ALL)

        writer.writerow(columns_headers)

        for data in rows:
            row = []
            for d in data:
                if d is None or d is False:
                    d = ''
                elif isinstance(d, bytes):
                    d = d.decode()
                # Las hojas de cálculo suelen detectar fórmulas por un = , + o
                # - al inicio de la celda.
                if isinstance(d, str) and d.startswith(('=', '-', '+')):
                    d = "'" + d

                row.append(d)
            writer.writerow(row)

        return fp.getvalue()

    @extend_schema(
        tags=['web'],
        summary='Exportar registros a CSV',
        parameters=[
            OpenApiParameter(
                'data', OpenApiTypes.STR, required=True,
                description="JSON con {model, fields, ids, domain, "
                            "import_compat, groupby, context}."),
        ],
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request):
        """≙ ``CSVExport.web_export_csv`` de la referencia."""
        return _export_response(self, request)


class ExcelExport(ExportFormat, APIView):
    """≙ ``ExcelExport`` — ``GET /api/v2/web/export/xlsx/?data=<json>``."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = _EXPORT_CAPABILITY
    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    extension = '.xlsx'

    def from_group_data(self, fields, columns_headers, groups):
        with GroupExportXlsxWriter(fields, columns_headers, groups.count) as xlsx_writer:
            x, y = 1, 0
            for group_name, group in groups.children.items():
                x, y = xlsx_writer.write_group(x, y, group_name, group)

        return xlsx_writer.value

    def from_data(self, fields, columns_headers, rows):
        with ExportXlsxWriter(fields, columns_headers, len(rows)) as xlsx_writer:
            for row_index, row in enumerate(rows):
                for cell_index, cell_value in enumerate(row):
                    xlsx_writer.write_cell(row_index + 1, cell_index, cell_value)

        return xlsx_writer.value

    @extend_schema(
        tags=['web'],
        summary='Exportar registros a XLSX',
        parameters=[
            OpenApiParameter(
                'data', OpenApiTypes.STR, required=True,
                description="JSON con {model, fields, ids, domain, "
                            "import_compat, groupby, context}."),
        ],
        responses={200: OpenApiTypes.BINARY},
    )
    def get(self, request):
        """≙ ``ExcelExport.web_export_xlsx`` de la referencia."""
        return _export_response(self, request)
