"""El valor nulo de LECTURA de un campo no es su ``falsy_value``.

La fuente lee un campo sobre un registro vacío como
``convert_to_record(convert_to_cache(False))`` (``odoo19c:
odoo/orm/fields.py:1652-1653``). Medido sobre sus once conversiones, eso da
``False`` para todo tipo salvo los numéricos (``0``/``0.0``) y los
relacionales (el recordset vacío; aquí el ``None`` de la FK). ``falsy_value``
es otro contrato —lo que una BÚSQUEDA trata como vacío— y para las cadenas
vale ``''`` (``fields_textual.py:38``): usarlo como valor leído hacía que un
``related`` por un ``Many2one`` vacío leyera ``''`` donde la fuente lee
``False``.
"""
import pytest

import fields
from orm.fields import falsy_value, null_record_value


@pytest.mark.parametrize('field', [
    fields.Char(), fields.Text(), fields.Html(),
    fields.Selection(choices=[('a', 'A')]), fields.Date(),
    fields.Datetime(), fields.Boolean(), fields.Json(), fields.Binary(),
], ids=lambda field: type(field).__name__)
def test_every_non_numeric_type_reads_false(field):
    assert null_record_value(field) is False


@pytest.mark.parametrize('field, expected', [
    (fields.Integer(), 0), (fields.Float(), 0.0),
], ids=['Integer', 'Float'])
def test_numeric_types_read_their_zero(field, expected):
    value = null_record_value(field)
    assert value == expected and value is not False
    assert type(value) is type(expected)


def test_a_relation_reads_the_empty_link():
    assert null_record_value(fields.Many2one('base.ResPartner')) is None


def test_a_string_keeps_its_search_emptiness_apart():
    """Los dos contratos conviven: el de búsqueda no cambia."""
    char = fields.Char()
    assert falsy_value(char) == ''
    assert null_record_value(char) is False
