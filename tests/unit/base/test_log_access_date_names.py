"""Las columnas del log-access con el nombre de la fuente.

Fechas ``create_date``/``write_date`` y autoría ``create_uid``/``write_uid``.

≙ ``odoo19c: odoo/orm/models.py:287-296``. Diseño en
``designs/log-access-date-names.md`` del Workbench: el nombre ORM y la
columna física son los de la fuente; la API v2 conserva ``created_at`` y
``updated_at`` con ``source=``.

*Métrica:* nombre de campo y de columna en ``_meta``, el SQL que genera un
filtro, y la clave que emite un serializador de la API v2.
*Ciega a:* un consumidor externo que lea la columna por SQL propio; el
contrato que se protege es el de la API v2.
"""
import pytest
from django.db import connection

from addons.base.models.res_partner import ResPartnerCategory
from addons.website_sale_wishlist.controllers.serializers import (
    WishlistItemSerializer)
from orm.model_classes import LOG_ACCESS_COLUMNS

pytestmark = pytest.mark.django_db

SOURCE_LOG_ACCESS_COLUMNS = ['create_uid', 'create_date',
                             'write_uid', 'write_date']


def test_log_access_columns_are_those_of_the_source():
    assert LOG_ACCESS_COLUMNS == SOURCE_LOG_ACCESS_COLUMNS


def test_field_and_column_carry_the_source_name():
    for name in ('create_date', 'write_date'):
        field = ResPartnerCategory._meta.get_field(name)
        assert field.column == name


def test_a_filter_on_the_date_reaches_the_physical_column():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name IN "
            "('create_date', 'write_date', 'created_at', 'updated_at')",
            [ResPartnerCategory._meta.db_table])
        columns = {row[0] for row in cursor.fetchall()}
    assert columns == {'create_date', 'write_date'}
    query = str(ResPartnerCategory.objects.filter(
        create_date__isnull=False).query)
    assert '"create_date" IS NOT NULL' in query


def test_the_api_keeps_its_external_names():
    """El contrato vigente de la API v2 no cambia: ``created_at`` sale con el
    valor de ``create_date``."""
    fields = WishlistItemSerializer().fields
    assert 'created_at' in fields
    assert fields['created_at'].source == 'create_date'
    assert 'create_date' not in fields


def test_the_authorship_columns_carry_the_source_name():
    """``create_uid``/``write_uid`` son columnas ``create_uid``/``write_uid``
    en la fuente, no ``*_id`` (``odoo19c: odoo/orm/models.py:287-292``,
    forma C de ADR-029)."""
    for name in ('create_uid', 'write_uid'):
        assert ResPartnerCategory._meta.get_field(name).column == name
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = %s AND column_name IN "
            "('create_uid', 'write_uid', 'create_uid_id', 'write_uid_id')",
            [ResPartnerCategory._meta.db_table])
        columns = {row[0] for row in cursor.fetchall()}
    assert columns == {'create_uid', 'write_uid'}
