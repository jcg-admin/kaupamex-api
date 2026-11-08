"""Campos numéricos — fiel a ``odoo/orm/fields_numeric.py`` (Odoo 19).

``Integer``, ``Float``, ``Monetary`` (Odoo Monetary = importe con moneda; alias
de ``DecimalField`` que en el proyecto sale como string por
``COERCE_DECIMAL_TO_STRING``).

``Monetary`` no es un alias pelado sino un **despachador** de ``store=``, igual
que ``Char`` (ver ``fields_textual.py``): recibe el vocabulario de la fuente,
lo deriva y lo anota sobre el campo. Lo que **ya no hace** es elegir clase —
``store`` es un atributo, no un tipo (``odoo19c: odoo/orm/fields.py:455``), y
la forma sin columna la resuelve la costura al contribuir a la clase
(TASK-API-0417). Precedente de ``Monetary`` sin columna:
``account/models/account_analytic_distribution_model.py`` (campo
``prefix_placeholder``) y ``account/models/digest.py`` (los KPI
``kpi_account_*_value``, que en la fuente son ``compute`` no almacenados).
``Integer`` y ``Float`` reciben el mismo trato por el molde de
:func:`~orm.fields_company_dependent.make_dispatcher`. Primer consumidor de
``Integer(store=False)``: ``hr_recruitment/models/digest.py`` (tarea #159),
cuyo KPI la fuente declara ``fields.Integer(compute=…)``, sin columna.

``company_dependent`` — ``Integer`` y ``Float`` sí lo llevan (tarea #129)
=========================================================================

Los dos están en ``COMPANY_DEPENDENT_FIELDS``, y los dos tienen consumidor en
la referencia: ``purchase/models/res_partner.py:43``
(``reminder_date_before_receipt``, ``Integer``) y
``product/models/product_product.py:62`` (``standard_price``, ``Float``). Por
eso dejan de ser alias pelados y pasan a ser despachadores fabricados con
:func:`~orm.fields_company_dependent.make_dispatcher`.

``Monetary`` **no** lo lleva, y no por olvido: ``monetary`` no está en la lista
cerrada de tipos que la fuente admite
(``odoo19c: odoo/orm/fields.py:42-44``). El ``standard_price`` que aquí es
``Monetary`` y allá es ``Float`` company_dependent es una decisión propia —
tarea **#135**.
"""

import decimal
from xmlrpc.client import MAXINT

from django.db import models

from orm.fields_company_dependent import current_env, make_dispatcher
from tools.float_utils import float_repr, float_round
from orm.fields_nonstored import (
    _UNSET,
    annotate_related,
    apply_source_defaults,
)

__all__ = ['Integer', 'Float', 'Monetary']

Integer = make_dispatcher('Integer', 'integer', models.IntegerField)


class NumericFloat(models.FloatField):
    """Un ``Float`` con ``digits``: columna ``numeric``, valor ``float``.

    ≙ ``Float._column_type`` (``odoo19c: odoo/orm/fields_numeric.py:125-133``),
    verbatim en su decisión: con ``digits`` declarados la columna es
    ``('numeric', 'numeric')`` —sin precisión: el redondeo lo hace
    ``convert_to_column``— y sin ellos ``float8``. El valor de Python sigue
    siendo ``float`` (``convert_to_cache``, ``:141-150``), así que la lectura
    convierte el ``Decimal`` que ``psycopg`` entrega por una columna
    ``numeric``.

    Antes el ``FloatField`` guardaba ``digits`` como atributo y creaba
    ``float8``: :ref:`h-api-1131`.
    """

    column_type = ('numeric', 'numeric')

    def db_type(self, connection):
        return 'numeric'

    def from_db_value(self, value, expression, connection):
        return None if value is None else float(value)


_float_plain = make_dispatcher('Float', 'float', models.FloatField)
_float_numeric = make_dispatcher('Float', 'float', NumericFloat)


def Float(*args, digits=None, min_display_digits=None, **kwargs):
    """``fields.Float`` — el despachador de ``company_dependent`` de
    siempre, que con ``digits`` construye un :class:`NumericFloat`.

    ≙ ``Float.__init__`` (``odoo19c: odoo/orm/fields_numeric.py:113-121``):
    ``min_display_digits`` sin ``digits`` declara ``digits=False``, una
    columna ``numeric`` sin escala fija. ``digits`` es una tupla o el nombre
    de un registro de ``decimal.precision``; los dos se guardan en
    ``_digits`` y se resuelven con :func:`_float_get_digits`.
    """
    if digits is None and min_display_digits is not None:
        digits = False
    if digits is None:
        field = _float_plain(*args, **kwargs)
    else:
        field = _float_numeric(*args, **kwargs)
        field.digits = digits
        field._digits = digits
    if min_display_digits is not None:
        field._min_display_digits = min_display_digits
    return field


Float.company_dependent_base_type = _float_plain.company_dependent_base_type
Float.plain_field_class = _float_plain.plain_field_class


def Monetary(*args, store=_UNSET, help=None, related=None,
             currency_field=None, **kwargs):
    """``fields.Monetary`` — ≙ el de la referencia, con y sin columna.

    ``help=`` es el alias de firma de la fuente para ``help_text=`` (misma
    tabla de alias que ``Char``). ``currency_field`` nombra el campo de la
    moneda (``odoo19c: odoo/orm/fields_numeric.py:202-203``); sin él,
    :func:`_monetary_get_currency_field` busca ``currency_id``.
    """
    if help is not None:
        kwargs.setdefault('help_text', help)
    #: ``:452-458`` — el centinela, por el mismo motivo que en ``Char``: el
    #: defecto de ``store`` depende de si hay ``related``.
    if store is not _UNSET:
        kwargs['store'] = store
    related_attrs = apply_source_defaults(related, kwargs)
    #: El ``DecimalField`` se construye con columna y sin ella: ``store`` es
    #: atributo, no tipo (``odoo19c: odoo/orm/fields.py:455``).
    field = models.DecimalField(*args, **kwargs)
    field.currency_field = currency_field
    return annotate_related(field, related, related_attrs)


def _integer_convert_to_column(
    self, value, record, values=None, validate=True
):
    """
    ``Integer.convert_to_column`` — ≙ ``odoo19c:
    odoo/orm/fields_numeric.py:32-33``.

    ``int(value or 0)``: el vocabulario de ausencia de un entero es el cero, no
    el ``NULL``. Es la sobrecarga que impide que la base lleve ``False`` a
    ``NULL`` sobre una columna que la fuente declara siempre poblada.

    **El cuerpo es verbatim y NO consulta ``null``.** Una primera versión
    añadió una rama ``if self.null: return None``, razonando que la fuente
    declara su ``Integer`` NOT NULL. Medido, eso es falso:
    ``odoo19c: odoo/orm/fields.py:298`` declara ``required: bool = False`` —
    «whether the field is required (NOT NULL in database)»—, así que la columna
    de un ``Integer`` admite ``NULL`` como cualquier otra. Lo que la fuente
    declara es ``falsy_value = 0`` (``fields_numeric.py:21``) y **tres**
    conversores que colapsan la ausencia al cero —éste, ``convert_to_cache`` y
    ``convert_to_record``—: el ORM nunca escribe ``NULL`` ni devuelve ``None``,
    y un ``NULL`` heredado en la columna se lee como ``0``.

    Cuando una restricción de tabla necesita el ``NULL``, la fuente lo resuelve
    **en el modelo**, no aquí: ``ir_filters`` declara su ``CHECK`` y borra la
    clave cuando vale cero antes de escribir
    (``odoo19c: odoo/addons/base/models/ir_filters.py:33-34`` y ``:54-57``).
    """
    return int(value or 0)


models.IntegerField.convert_to_column = _integer_convert_to_column


def _float_convert_to_column(self, value, record, values=None, validate=True):
    """``Float.convert_to_column`` — ≙ ``:155-163``.

    Redondea al número de decimales declarado antes de escribir, que es el
    punto entero del cuerpo de la fuente: sin ese paso el valor de la columna y
    el de la caché divergen en el último dígito y las comparaciones dejan de
    coincidir.

    La precisión sale de ``self.get_digits(env)``, verbatim: la tupla
    declarada o el registro de ``decimal.precision``. Sin registro —la
    escritura de Django llama con ``record=None``— el entorno es el del
    alcance (:func:`orm.environments.env`). Como allá, el valor redondeado
    viaja como su representación textual, salvo en ``company_dependent``.
    """
    value_float = value = float(value or 0.0)
    environment = record.env if record is not None else current_env()
    if digits := self.get_digits(environment):
        _precision, scale = digits
        value_float = float_round(value, precision_digits=scale)
        value = float_repr(value_float, precision_digits=scale)
    if self.company_dependent:
        return value_float
    return value


models.FloatField.convert_to_column = _float_convert_to_column


def _decimal_convert_to_column(
    self, value, record, values=None, validate=True
):
    """``Monetary.convert_to_column`` — ≙ el mismo reparto que ``Float``.

    ``DecimalField`` es el tipo con que este árbol declara el dinero, y su
    valor **no** pasa por ``float``: cuantizarlo en ``Decimal`` es lo que
    conserva la representación exacta que la columna guarda. Un ``0`` o un
    ``False`` entran como cero, no como ``NULL`` — mismo criterio que el
    entero.
    """
    if value is None or value is False or value == '':
        return decimal.Decimal(0)
    if not isinstance(value, decimal.Decimal):
        value = decimal.Decimal(str(value))
    scale = getattr(self, 'decimal_places', None)
    if scale is None:
        return value
    return value.quantize(
        decimal.Decimal(1).scaleb(-scale), rounding=decimal.ROUND_HALF_UP
    )


models.DecimalField.convert_to_column = _decimal_convert_to_column


def _integer_convert_to_cache(self, value, record, validate=True):
    """``Integer.convert_to_cache`` — ≙ ``odoo19c:
    odoo/orm/fields_numeric.py:35-39``.

    ``int(value or 0)``, salvo el dict que llega cuando un entero hace de
    inverso de un ``One2many``, del que se toma ``id``. Un valor que no es
    entero levanta ``ValueError`` o ``TypeError``, como allá: es lo que
    ``_search_display_name`` usa para descartar un valor que no convierte.

    **Las claves primarias se excluyen.** ``AutoField`` deriva de
    ``IntegerField`` en Django, y la referencia modela el id con otra clase
    (``Id``): pasarle este conversor convertiría el ``pk`` ausente de una fila
    sin guardar en ``0``. Siguen con el conversor genérico.
    """
    if isinstance(self, models.AutoField):
        return models.Field.convert_to_cache(self, value, record, validate)
    if isinstance(value, dict):
        return value.get('id', None)
    return int(value or 0)


def _integer_convert_to_record(self, value, record):
    """``Integer.convert_to_record`` — ≙ ``:41-42``: la ausencia se lee como
    ``0``. Las claves primarias siguen con el conversor genérico."""
    if isinstance(self, models.AutoField):
        return models.Field.convert_to_record(self, value, record)
    return value or 0


models.IntegerField.convert_to_cache = _integer_convert_to_cache
models.IntegerField.convert_to_record = _integer_convert_to_record


def _integer_convert_to_read(self, value, record, use_display_name=True):
    """``Integer.convert_to_read`` — ≙ ``:44-49``. Por encima de ``MAXINT``
    (``2**31 - 1``, el de ``xmlrpc.client`` como allá) el valor viaja como
    ``float``: XML-RPC puro no admite enteros mayores. Las claves primarias
    siguen con el conversor genérico."""
    if isinstance(self, models.AutoField):
        return models.Field.convert_to_read(self, value, record,
                                            use_display_name)
    if value and value > MAXINT:
        return float(value)
    return value


def _integer_convert_to_export(self, value, record):
    """``Integer.convert_to_export`` — ≙ ``:54-57``: el ``0`` se exporta como
    ``0`` y sólo la ausencia como texto vacío."""
    if isinstance(self, models.AutoField):
        return models.Field.convert_to_export(self, value, record)
    if value or value == 0:
        return value
    return ''


models.IntegerField.convert_to_read = _integer_convert_to_read
models.IntegerField.convert_to_export = _integer_convert_to_export


def _float_get_digits(self, env):
    """≙ ``Float.get_digits``.

    Fuente: ``odoo19c: odoo/orm/fields_numeric.py:135-140``.

    Un nombre de ``decimal.precision`` da ``(16, precisión)``; una tupla, o
    su ausencia, se devuelve tal cual.
    """
    if isinstance(self._digits, str):
        precision = env['decimal.precision'].precision_get(self._digits)
        return 16, precision
    return self._digits


def _float_get_min_display_digits(self, env):
    """≙ ``Float.get_min_display_digits`` (``:142-145``)."""
    if isinstance(self._min_display_digits, str):
        return env['decimal.precision'].precision_get(
            self._min_display_digits)
    return self._min_display_digits


def _float_description_digits(self, env):
    """≙ ``Float._description_digits`` (``:149-150``)."""
    return self.get_digits(env)


def _float_description_min_display_digits(self, env):
    """≙ ``Float._description_min_display_digits`` (``:152-153``)."""
    return self.get_min_display_digits(env)


#: ≙ los atributos de clase ``_digits`` y ``_min_display_digits``
#: (``:109-110``): sin declaración, ``None``.
models.FloatField._digits = None
models.FloatField._min_display_digits = None
models.FloatField.get_digits = _float_get_digits
models.FloatField.get_min_display_digits = _float_get_min_display_digits
models.FloatField._description_digits = _float_description_digits
models.FloatField._description_min_display_digits = (
    _float_description_min_display_digits)


def _monetary_get_currency_field(self, model):
    """≙ ``Monetary.get_currency_field`` (``:222-228``) — «Return the name
    of the currency field.»"""
    return self.currency_field or (
        'currency_id' if 'currency_id' in model._fields else
        'x_currency_id' if 'x_currency_id' in model._fields else
        None
    )


def _monetary_description_currency_field(self, env):
    """≙ ``Monetary._description_currency_field`` (``:205-206``)."""
    return self.get_currency_field(env[self.model_name])


#: ≙ ``currency_field: Field | None = None`` (``:197``).
models.DecimalField.currency_field = None
models.DecimalField.get_currency_field = _monetary_get_currency_field
models.DecimalField._description_currency_field = (
    _monetary_description_currency_field)
