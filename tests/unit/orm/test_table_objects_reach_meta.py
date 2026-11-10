"""Un objeto de tabla declarado con la forma de la referencia llega a la base.

≙ ``odoo19c: odoo/orm/model_classes.py:455-461`` (``_table_objects`` por
``full_name``) y ``odoo/orm/models.py:3262-3268`` (``_add_sql_constraints``).
Aquí la autoridad del esquema son las migraciones: el objeto llega a
``Meta.constraints``/``Meta.indexes`` y de ahí a ``makemigrations``. Diseño en
``designs/schema-and-translation-symbols-decision.md`` del Workbench
(TASK-API-0514).

*Métrica:* ``Meta``, ``_table_objects``, ``pg_constraint`` y el mensaje del
error, sobre ``test_orm.category._positive_color``.
*Ciega a:* objetos de tabla que un modelo de otro addon añada por extensión.
"""
import pytest
from django.db import IntegrityError, connection, transaction

from addons.test_orm.models.test_orm import TestOrmCategory

pytestmark = pytest.mark.django_db

NAME = 'test_orm_category_positive_color'


def test_the_table_object_reaches_meta_constraints():
    assert NAME in {cons.name for cons in TestOrmCategory._meta.constraints}


def test_table_objects_maps_the_full_name_to_the_declaration():
    assert TestOrmCategory._table_objects[NAME] is (
        TestOrmCategory._positive_color)


def test_the_constraint_exists_in_postgresql():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_constraint WHERE conname = %s", [NAME])
        assert cursor.fetchone()[0] == 1


def test_the_violation_reports_the_declared_message():
    with pytest.raises(IntegrityError) as caught, transaction.atomic():
        TestOrmCategory.objects.create(name='negativa', color=-1)
    assert TestOrmCategory._sql_error_to_message(caught.value) == (
        'The color code must be positive!')
