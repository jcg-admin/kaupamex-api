"""Condición x2many cuyo comodelo es un modelo de Django.

≙ ``odoo19c: odoo/orm/fields_relational.py:779-837``
(``_RelationalMulti.condition_to_sql``), con la rama de comodelo de Django
que ya lleva el ``Many2one``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
x2many-django-comodel-condition.md``.
"""
import pytest
from django.db import connection, models

from addons.base.models import TimeStampedModel
from orm.environments import sudo
from orm.models import BaseModel
from tests.fixtures.probe_tables import create_probe_tables


class TagDjXc(models.Model):
    _name = 'orm.tag.dj.xc'
    name = models.CharField(max_length=32)

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_tag_dj_xc'


class ItemXc(BaseModel, TimeStampedModel):
    _name = 'orm.item.xc'
    name = models.CharField(max_length=32)
    tags = models.ManyToManyField(TagDjXc, db_table='orm_item_xc_tag_rel')

    class Meta:
        app_label = 'base'
        managed = False
        db_table = 'orm_item_xc'


MODELS = (TagDjXc, ItemXc)


@pytest.fixture(scope='session')
def tables(django_db_setup, django_db_blocker):
    """Las tablas de sonda se crean fuera de la transacción del caso."""
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            create_probe_tables(editor, MODELS)
    yield
    with django_db_blocker.unblock():
        with connection.schema_editor() as editor:
            for model in reversed(MODELS):
                editor.delete_model(model)


@pytest.fixture
def rows(tables, db):
    red = TagDjXc.objects.create(name='red')
    blue = TagDjXc.objects.create(name='blue')
    tagged = ItemXc.objects.create(name='tagged')
    other = ItemXc.objects.create(name='other')
    bare = ItemXc.objects.create(name='bare')
    through = ItemXc._meta.get_field('tags').remote_field.through
    through.objects.create(itemxc=tagged, tagdjxc=red)
    through.objects.create(itemxc=other, tagdjxc=blue)
    return {'red': red, 'blue': blue, 'tagged': tagged, 'other': other,
            'bare': bare}


def _names(domain):
    with sudo():
        return set(ItemXc.search(domain).mapped('name'))


def test_in_ids(rows):
    assert _names([('tags', 'in', [rows['red'].pk])]) == {'tagged'}


def test_not_in_ids(rows):
    assert _names([('tags', 'not in', [rows['red'].pk])]) == {'other', 'bare'}


def test_in_false_selects_the_rows_without_tags(rows):
    assert _names([('tags', 'in', [False])]) == {'bare'}


def test_any_with_a_domain_on_the_django_comodel(rows):
    assert _names([('tags', 'any', [('name', '=', 'blue')])]) == {'other'}
