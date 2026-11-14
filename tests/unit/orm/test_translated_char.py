"""Contrato de TASK-GEN-0060: ``translate=True`` guarda ``{idioma: valor}``.

Referencia: odoo-tools ``abe4040ec1``, ``odoo19c: odoo/orm/fields_textual.py``
(``convert_to_column_insert`` ``:84-91``, ``translation_lang`` ``:213-214``,
``get_translation_fallback_langs`` ``:216-224``, ``write`` ``:288-325``,
``to_sql`` ``:394-402``) y ``odoo19c: odoo/orm/models.py``
(``_update_field_translations`` ``:3505-3651``, ``get_field_translations``
``:3664-3703``, ``copy_translations`` ``:5465-5528``).

Sujeto: ``hr.departure.reason.name``, la única de las 14 columnas con filas
sembradas por migración. Los valores guardados se leen con SQL: el mapa de la
fila es justo lo que el descriptor oculta.

Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
translate-jsonb-storage.md``.
"""
import json

import pytest
from django.db import connection

from addons.base.models import ResLang
from addons.hr.models import HrDepartureReason
from exceptions import UserError
from orm import registry
from orm.environments import context_scope, sudo
from orm.fields import type_for
from orm.fields_textual import BASE_LANG
from tools.sql import convert_column_translatable

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    """El registro de sonda se escribe como superusuario: con
    ``hr.departure.reason`` sobre ``BaseModel`` la escritura pasa por
    ``check_access``, y estos casos miden la traducción, no el acceso."""
    with sudo():
        yield


def stored(record):
    """El mapa crudo de la columna, sin pasar por el ORM."""
    with connection.cursor() as cr:
        cr.execute('SELECT name FROM hr_departure_reason WHERE id = %s',
                   [record.pk])
        value = cr.fetchone()[0]
    # el cursor crudo de Django entrega ``jsonb`` como texto
    return json.loads(value) if isinstance(value, str) else value


def put(record, value):
    """Fija el mapa crudo con SQL, para preparar lecturas."""
    with connection.cursor() as cr:
        cr.execute(
            'UPDATE hr_departure_reason SET name = %s::jsonb WHERE id = %s',
            [value, record.pk])


@pytest.fixture
def es_mx():
    """Activa ``es_MX`` y vacía la caché ``stable`` al entrar y al salir."""
    lang = ResLang.objects.get(code='es_MX')
    lang.active = True
    lang.save()
    yield 'es_MX'
    registry.clear_cache('stable')


def new_reason(name='Kg'):
    return HrDepartureReason.objects.create(name=name, sequence=99)


def test_the_column_is_jsonb_and_the_type_stays_char():
    field = HrDepartureReason._meta.get_field('name')
    assert field.translate is True
    assert field.db_type(connection) == 'jsonb'
    assert type_for(field) == 'char'


def test_seeded_rows_kept_their_text_as_the_base_language():
    with connection.cursor() as cr:
        cr.execute("SELECT name->>'en_US' FROM hr_departure_reason"
                   " WHERE name->>'en_US' IN"
                   "  ('Despedido', 'Jubilado', 'Renunció')"
                   " AND name - 'en_US' = '{}'::jsonb ORDER BY 1")
        assert [row[0] for row in cr.fetchall()] == [
            'Despedido', 'Jubilado', 'Renunció']


def test_conversion_round_trips_the_text():
    with connection.cursor() as cr:
        convert_column_translatable(
            cr, 'hr_departure_reason', 'name', 'varchar')
        cr.execute("SELECT count(*) FROM hr_departure_reason"
                   " WHERE name = 'Despedido'")
        assert cr.fetchone()[0] == 1
        convert_column_translatable(
            cr, 'hr_departure_reason', 'name', 'jsonb')
        cr.execute("SELECT name FROM hr_departure_reason"
                   " WHERE name->>'en_US' = 'Despedido'")
        assert json.loads(cr.fetchone()[0]) == {BASE_LANG: 'Despedido'}


def test_insert_stores_the_base_and_the_active_language(es_mx):
    assert stored(new_reason()) == {BASE_LANG: 'Kg'}
    with context_scope(lang=es_mx):
        assert stored(new_reason('Kilo')) == {
            BASE_LANG: 'Kilo', 'es_MX': 'Kilo'}


def test_reading_a_missing_language_falls_back_to_the_base(es_mx):
    record = new_reason()
    put(record, '{"en_US": "Kg", "fr_FR": "Kilo FR"}')
    record = HrDepartureReason.objects.get(pk=record.pk)
    with context_scope(lang=es_mx):
        assert record.name == 'Kg'
    put(record, '{"en_US": "Kg", "es_MX": "Kilo"}')
    record = HrDepartureReason.objects.get(pk=record.pk)
    with context_scope(lang=es_mx):
        assert record.name == 'Kilo'
    assert record.name == 'Kg'


def test_writing_under_a_language_touches_only_its_key(es_mx):
    record = new_reason()
    put(record, '{"en_US": "Kg", "fr_FR": "Kilo FR"}')
    record = HrDepartureReason.objects.get(pk=record.pk)
    with context_scope(lang=es_mx):
        record.name = 'Kilo'
        record.save(update_fields=['name'])
    assert stored(record) == {
        BASE_LANG: 'Kg', 'fr_FR': 'Kilo FR', 'es_MX': 'Kilo'}


def test_update_field_translations_keeps_the_base_language(es_mx):
    record = new_reason()
    assert record.update_field_translations('name', {'es_MX': 'Kilo'})
    assert stored(record) == {BASE_LANG: 'Kg', 'es_MX': 'Kilo'}


def test_a_false_translation_removes_the_language(es_mx):
    record = new_reason()
    record.update_field_translations('name', {'es_MX': 'Kilo'})
    record.update_field_translations('name', {'es_MX': False})
    assert stored(record) == {BASE_LANG: 'Kg'}


def test_an_inactive_language_is_refused():
    record = new_reason()
    with pytest.raises(UserError, match='not activated'):
        record.update_field_translations('name', {'fr_FR': 'Kilo'})


def test_get_field_translations_lists_each_installed_language(es_mx):
    record = new_reason()
    record.update_field_translations('name', {'es_MX': 'Kilo'})
    translations, context = record.get_field_translations('name')
    assert sorted(translations, key=lambda t: t['lang']) == [
        {'lang': 'en_US', 'source': 'Kg', 'value': 'Kg'},
        {'lang': 'es_MX', 'source': 'Kg', 'value': 'Kilo'},
    ]
    assert context == {'translation_type': 'char',
                       'translation_show_source': False}


def test_django_filters_compare_the_active_language_text(es_mx):
    record = new_reason('Kg-probe')
    record.update_field_translations('name', {'es_MX': 'Kilo-probe'})
    assert list(HrDepartureReason.objects.filter(name='Kg-probe')) == [record]
    assert not HrDepartureReason.objects.filter(name='Kilo-probe').exists()
    with context_scope(lang=es_mx):
        assert list(HrDepartureReason.objects.filter(
            name__icontains='kilo-pro')) == [record]


def test_to_sql_reads_the_language_with_fallback(es_mx):
    field = HrDepartureReason._meta.get_field('name')
    with context_scope(lang=es_mx):
        sql = field.to_sql(HrDepartureReason, 'hr_departure_reason')
    code = sql.code if hasattr(sql, 'code') else str(sql)
    assert 'COALESCE' in code and '->>' in code
    assert list(sql.params) == ['es_MX', 'en_US']


def test_copy_translations_copies_every_language(es_mx):
    record = new_reason()
    record.update_field_translations('name', {'es_MX': 'Kilo'})
    duplicate = new_reason('otro')
    record.copy_translations(duplicate)
    assert stored(duplicate) == {BASE_LANG: 'otro', 'es_MX': 'Kilo'}


def test_queryset_update_writes_only_the_active_language(es_mx):
    """``QuerySet.update`` no pasa por el descriptor; la escritura es la
    fusión de ``_write_multi`` (``odoo19c: odoo/orm/models.py:4564-4576``)."""
    record = new_reason()
    record.update_field_translations('name', {'es_MX': 'Kilo'})
    HrDepartureReason.objects.filter(pk=record.pk).update(name='Kg2')
    assert stored(record) == {BASE_LANG: 'Kg2', 'es_MX': 'Kilo'}
    with context_scope(lang=es_mx):
        HrDepartureReason.objects.filter(pk=record.pk).update(name='Kilo2')
    assert stored(record) == {BASE_LANG: 'Kg2', 'es_MX': 'Kilo2'}
