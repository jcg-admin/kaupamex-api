"""La familia de conversion de ``Field`` — ≙ ``odoo19c: odoo/orm/fields.py:975-1095``.

Ejerce los nueve simbolos que la fuente agrupa bajo «Conversion of values»
—``convert_to_column``, ``convert_to_column_insert``, ``get_column_update``,
``convert_to_cache``, ``convert_to_record``, ``convert_to_read``,
``convert_to_write``, ``convert_to_export`` y ``convert_to_display_name``— mas
la propiedad ``column_order``, que la fuente declara justo despues (``:1090``).

El veredicto por el criterio de las dos categorias:

===========================  ==============================================
El stack lo trae hecho       el adaptador de ``jsonb``
                             (``psycopg.types.json.Jsonb``), que es el
                             ``PsycopgJson`` de la fuente traido a psycopg 3;
                             y la tabla de orden de columna, ya portada en
                             ``tools/sql.py`` como ``sql_order_by_type``.
El stack tiene con que       el contrato en si. Django no separa «formato de
construirlo                  cache», «formato de registro» y «formato de
                             lectura»: su ``Field`` declara ``to_python`` y
                             ``get_prep_value`` y nada mas. Las cuatro
                             conversiones se construyen sobre el almacen que
                             ``Transaction.field_data`` ya provee.
===========================  ==============================================

**El control que discrimina.** Cada caso afirma una conducta que cambia si el
method no existe o delega mal. Un ``convert_to_record(None)`` que devolviera
``None`` en vez de ``False`` pasaria un ``assert not result`` — por eso los
casos afirman ``is False``, que si distingue los dos.
"""
import datetime

import pytest
from django.db import models as django_models
from django.db.models import F, Value
from django.db.models.expressions import CombinedExpression
from psycopg.types.json import Jsonb

import fields
from addons.base.models.ir_default import IrDefault
from addons.base.models.res_company import ResCompany
from orm.environments import company_scope, env as ambient_env, transaction_scope


class ConversionProbe(django_models.Model):
    """Sonda con una columna de cada forma que el orden de columna distingue."""

    _name = 'orm.conversion.probe'

    label = fields.Char('Label', max_length=64)
    amount = fields.Integer('Amount', default=0)
    when = fields.Date('When', null=True)
    per_company = fields.Char('Per company', company_dependent=True)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_conversion_probe'


def field_of(name):
    return ConversionProbe._meta.get_field(name)


# --- convert_to_column: los cuatro caminos de la fuente ---------------------

@pytest.mark.parametrize('value, expected', [
    (None, None),
    (False, None),
    ('texto', 'texto'),
    (b'bytes', 'bytes'),
    (42, '42'),
    (datetime.date(2026, 9, 3), '2026-09-03'),
])
def test_the_base_convert_to_column_follows_the_four_branches(value, expected):
    """≙ ``:981-992``: ``None``/``False`` a ``None``, ``str`` tal cual,
    ``bytes`` decodificado, y el resto por ``str``.

    Se invoca **el cuerpo base**, no el del campo: desde que cada tipo declara
    su sobrecarga —como la fuente— un ``Char`` ya no llega hasta aqui, y medir
    la base a traves de el mediria la sobrecarga. La fuente reparte esta
    decision por clase y este caso mide la clase raiz.
    """
    field = field_of('label')
    assert django_models.Field.convert_to_column(field, value, None) == expected


def test_the_base_convert_to_column_keeps_the_empty_string():
    """La cadena vacia NO es ``None``: la rama de ``str`` va antes que
    cualquier prueba de verdad, y la fuente solo descarta ``None`` y ``False``
    por identidad."""
    field = field_of('label')
    assert django_models.Field.convert_to_column(field, '', None) == ''


@pytest.mark.parametrize('name, value, expected', [
    ('label', 0, '0'),
    ('label', '', ''),
    ('label', False, None),
    ('label', b'bytes', 'bytes'),
    ('amount', 0, 0),
    ('amount', False, 0),
    ('amount', '42', 42),
    ('when', False, None),
    ('when', '2026-09-03', datetime.date(2026, 9, 3)),
])
def test_each_type_declares_its_own_vocabulary_of_absence(name, value, expected):
    """El reparto por clase que la fuente declara, medido tipo a tipo.

    ``Char`` delega en su cache, que descarta ``None`` y ``False`` **por
    identidad** y lleva el resto a texto (``odoo19c:
    odoo/orm/fields_textual.py:84-85`` y ``:102-113``) — la cadena vacia y el
    cero sobreviven, porque son valores; ``Integer`` lleva la
    ausencia al cero, no a ``NULL`` (``fields_numeric.py:32-33``); ``Date``
    descarta lo falso y convierte el resto (``fields_temporal.py:97-103``).

    Es el control que discrimina el caso de arriba: si todos heredaran la base,
    los tres darian la misma respuesta —texto— y ninguna de estas filas
    coincidiria.
    """
    assert field_of(name).convert_to_column(value, None) == expected


def test_the_boolean_is_the_one_that_keeps_false():
    """``Boolean`` es el UNICO tipo para el que ``False`` es un valor y no la
    ausencia de valor (``odoo19c: odoo/orm/fields_misc.py:28-29``). Sin su
    sobrecarga la base lo llevaria a ``NULL`` y la columna perderia la mitad
    de su dominio — por eso este caso va aparte y no como una fila mas."""
    field = django_models.BooleanField()
    assert field.convert_to_column(False, None) is False
    assert field.convert_to_column(None, None) is False


# --- convert_to_column_insert ----------------------------------------------

def test_convert_to_column_insert_delegates_when_not_company_dependent():
    """≙ ``:994-1006``: sin ``company_dependent`` es ``convert_to_column``."""
    assert field_of('label').convert_to_column_insert('texto', None) == 'texto'


@pytest.mark.django_db
def test_convert_to_column_insert_wraps_the_value_by_company():
    """≙ ``:1003-1006``: un field dependiente de empresa guarda un mapa
    ``{empresa: valor}``, envuelto para la columna ``jsonb``."""
    with company_scope(7):
        envuelto = field_of('per_company').convert_to_column_insert(
            'ABC', ConversionProbe(id=1))
    assert isinstance(envuelto, Jsonb)
    assert envuelto.obj == {7: 'ABC'}


@pytest.mark.django_db
def test_convert_to_column_insert_omits_the_value_equal_to_the_fallback():
    """≙ ``:1002-1004``: si el valor coincide con el default de ``ir.default``
    no se guarda — la fila hereda el fallback y la columna queda en ``None``.

    Es la mitad que discrimina: sin la comparacion, este caso devolveria un
    ``Jsonb`` y el mapa crecería con un valor que ya estaba declarado.
    """
    IrDefault.set(ConversionProbe._meta.label, 'per_company', 'ABC')
    with company_scope(7):
        assert field_of('per_company').convert_to_column_insert(
            'ABC', ConversionProbe(id=1)) is None


# --- convert_to_cache / record / read / write / export ----------------------

def test_the_base_convert_to_cache_returns_the_value_verbatim():
    """≙ ``:1034-1044``: el ``Field`` base no transforma nada.

    Se invoca el cuerpo base por la clase raiz, no por un campo: ``Char`` ya
    declara el suyo (``odoo19c: odoo/orm/fields_textual.py:102-113``), asi que
    medirlo a traves de el mediria la sobrecarga.
    """
    mark = object()
    assert django_models.Field.convert_to_cache(
        field_of('label'), mark, None) is mark


@pytest.mark.parametrize('method', ['convert_to_record', 'convert_to_read'])
def test_none_becomes_false_not_none(method):
    """≙ ``:1046-1063``: ``False if value is None else value``.

    Se afirma ``is False`` y no ``not result``: un ``None`` devuelto pasaria
    la segunda forma y el caso no discriminaria.
    """
    assert getattr(field_of('label'), method)(None, None) is False


@pytest.mark.parametrize('method', ['convert_to_record', 'convert_to_read'])
def test_a_value_survives_the_conversion(method):
    assert getattr(field_of('label'), method)('texto', None) == 'texto'


def test_convert_to_write_chains_the_three_conversions():
    """≙ ``:1065-1071``: cache, registro y lectura, en ese orden."""
    field = field_of('label')
    assert field.convert_to_write(None, None) is False
    assert field.convert_to_write('texto', None) == 'texto'


@pytest.mark.parametrize('value, expected', [
    (None, ''),
    (False, ''),
    (0, ''),
    ('', ''),
    ('texto', 'texto'),
])
def test_convert_to_export_empties_the_falsy(value, expected):
    """≙ ``:1073-1077``: todo lo falso sale como cadena vacia."""
    assert field_of('label').convert_to_export(value, None) == expected


# --- convert_to_display_name ------------------------------------------------

def test_convert_to_display_name_is_a_method_of_the_field():
    """≙ ``:1079-1081``. Era una funcion de modulo y nada mas; la fuente lo
    declara method, y sus cinco sobrecargas son metodos de su clase."""
    field = field_of('label')
    assert field.convert_to_display_name('texto', None) == 'texto'
    assert field.convert_to_display_name(None, None) is False
    assert field.convert_to_display_name(0, None) is False


def test_the_temporal_overload_still_wins_over_the_base():
    """La sobrecarga de ``Date`` estaba adjunta desde antes; adjuntar la base a
    ``models.Field`` no la puede tapar — la busqueda de atributo entra por la
    clase concreta."""
    assert (field_of('when').convert_to_display_name(datetime.date(2026, 9, 3), None)
            == '2026-09-03')


def test_the_collection_overload_refuses():
    """≙ ``fields_relational.py:715``: una coleccion no tiene etiqueta unica, y
    la fuente levanta ``NotImplementedError`` en vez de inventar una."""
    field = django_models.ManyToManyField('base.ResUsers')
    with pytest.raises(NotImplementedError):
        field.convert_to_display_name(None, None)


# --- column_order -----------------------------------------------------------

@pytest.mark.parametrize('name, expected', [
    ('label', 2),        # varchar
    ('amount', 1),       # int4
    ('when', 3),         # date
    ('per_company', 4),  # jsonb — la columna del field por empresa
])
def test_column_order_reads_the_table_of_the_source(name, expected):
    """≙ ``:1090-1093``: el orden prescrito por tipo, que minimiza el relleno
    de la fila. Los valores son los de ``odoo19c: odoo/tools/sql.py:261``."""
    assert field_of(name).column_order == expected


def test_column_order_of_a_field_without_column_is_zero():
    """≙ ``:1093``: ``0 if self.column_type is None``."""
    assert fields.Char('Sin columna', store=False).column_order == 0


# --- get_column_update ------------------------------------------------------

def test_get_column_update_reads_the_cache_of_the_transaction():
    """≙ ``:1008-1032``: el valor que se va a escribir sale de la cache, no del
    atributo de la instancia."""
    with transaction_scope():
        field = field_of('label')
        registro = ConversionProbe(id=7)
        field._get_cache_impl(ambient_env())[7] = 'de la cache'
        registro.label = 'del atributo'
        assert field.get_column_update(registro) == 'de la cache'


def test_get_column_update_refuses_when_the_value_is_not_cached():
    """La ausencia no se lee como ``None``: sin valor en cache el field no sabe
    que escribir, y la fuente lo dice con un ``KeyError``."""
    with transaction_scope():
        with pytest.raises(KeyError):
            field_of('label').get_column_update(ConversionProbe(id=99))


# --- el cableado a get_db_prep_save y la expresion SQL -----------------------

class TestTheWiringLetsAnExpressionThrough:
    """El conversor traduce un VALOR; una expresion SQL no lo es.

    ``convert_to_column`` esta cableado a ``Field.get_db_prep_save`` — el
    ultimo metro hacia el motor— para que el vocabulario de la fuente llegue a
    la columna. Ese metro tambien lo recorre lo que **no** es un valor: en un
    ``UPDATE`` con ``F()``, el compilador resuelve la expresion y se la pasa al
    campo (``django/db/models/sql/compiler.py:2035-2065``).

    El discriminador NO se inventa: lo declara la propia funcion envuelta,
    ``django/db/models/fields/__init__.py:1007-1011``::

        def get_db_prep_save(self, value, connection):
            if hasattr(value, "as_sql"):
                return value
            return self.get_db_prep_value(value, connection=connection,
                                          prepared=False)

    Y la fuente coincide en el fondo: sus dos unicos llamadores de
    ``convert_to_column`` (``odoo19c: odoo/orm/models.py:3145`` y ``:4870``)
    le pasan un valor del formato de cache, nunca un fragmento de SQL — los
    suyos viajan como ``SQL()`` y no entran por aqui.

    **El control discrimina:** sin la guarda, ``int(value or 0)`` recibe un
    ``CombinedExpression`` y revienta con ``TypeError``. Medido: 8 casos de la
    suite cayeron asi antes de portarla.
    """

    def test_an_update_with_an_expression_reaches_the_column(self, db):
        company = ResCompany.objects.create(
            code='orm-conv-expr', name='ORM conversion expression',
            quotation_validity_days=30,
        )
        ResCompany.objects.filter(pk=company.pk).update(
            quotation_validity_days=F('quotation_validity_days') + 1)

        assert ResCompany.objects.filter(pk=company.pk).values_list(
            'quotation_validity_days', flat=True)[0] == 31

    def test_the_wiring_refuses_to_convert_what_carries_its_own_sql(self):
        """La guarda se mide sola, sin motor: lo que trae ``as_sql`` sale
        intacto del cableado."""
        expression = CombinedExpression(F('amount'), '+', Value(1))
        assert hasattr(expression, 'as_sql')
        assert field_of('amount').get_db_prep_save(
            expression, connection=None) is expression
