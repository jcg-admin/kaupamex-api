"""``parent_path`` de ``ir.ui.menu`` y ``_check_parent_path``.

≙ ``odoo19c: odoo/orm/models.py:3255-3260`` (``_check_parent_path``, que
``_auto_init`` llama para todo modelo con ``_parent_store``, ``:3214``) y
``odoo/addons/base/models/ir_ui_menu.py:20,28``. Diseño en
``designs/parent-path-check.md`` del Workbench.

*Métrica:* filas que devuelve ``child_of`` y ``parent_path`` tras reparentar;
mensajes del check de Django.
*Ciega a:* el índice en la base, que el check no consulta (la referencia
tampoco: lee el atributo ``index`` del campo).
"""
import itertools

import pytest
from django.db import models
from django.test.utils import isolate_apps

from orm.domains import to_q
from orm.environments import sudo
from orm.models import RecordLoaderMixin
from orm.registry import MODELS_BY_NAME

pytestmark = pytest.mark.django_db

MISSING = ("add a field parent_path on model %r: `parent_path = "
           "fields.Char(index=True)`.")
NOT_INDEXED = ("parent_path field on model %r should be indexed! "
               "Add index=True to the field definition.")
_PROBES = itertools.count()


def _menu(name, parent=None):
    return MODELS_BY_NAME['ir.ui.menu'].objects.create(
        name=name, key=name, parent=parent)


def test_child_of_on_menus_follows_the_materialized_path():
    Menu = MODELS_BY_NAME['ir.ui.menu']
    with sudo():
        root = _menu('pp-root')
        child = _menu('pp-child', root)
        _menu('pp-grandchild', child)
        _menu('pp-other')
        found = Menu.objects.filter(to_q([('id', 'child_of', root.pk)], Menu))
        assert sorted(found.values_list('name', flat=True)) == [
            'pp-child', 'pp-grandchild', 'pp-root']


def test_reparenting_rewrites_the_path_of_the_subtree():
    Menu = MODELS_BY_NAME['ir.ui.menu']
    with sudo():
        root = _menu('pp-a')
        other = _menu('pp-b')
        child = _menu('pp-a-child', root)
        grandchild = _menu('pp-a-grandchild', child)
        child.parent = other
        child.save()
        paths = dict(Menu.objects.filter(pk__in=[child.pk, grandchild.pk])
                     .values_list('pk', 'parent_path'))
        assert paths[child.pk] == f'{other.pk}/{child.pk}/'
        assert paths[grandchild.pk] == (
            f'{other.pk}/{child.pk}/{grandchild.pk}/')


def test_the_menu_model_passes_the_parent_path_check():
    messages = MODELS_BY_NAME['ir.ui.menu']._check_parent_path()
    assert messages == []


def _probe(attrs):
    with isolate_apps():
        meta = type('Meta', (), {'app_label': 'base'})
        number = next(_PROBES)
        body = {'__module__': __name__, 'Meta': meta,
                '_name': f'test.parent.path.probe{number}',
                '_parent_store': True, **attrs}
        return type(f'ParentPathProbe{number}',
                    (RecordLoaderMixin, models.Model), body)


def test_the_check_names_a_missing_parent_path():
    probe = _probe({})
    expected = MISSING % probe._name
    assert [m.msg for m in probe._check_parent_path()] == [expected]
    assert expected in [m.msg for m in probe.check()]


def test_the_check_asks_for_an_index():
    probe = _probe({'parent_path': models.CharField(max_length=255,
                                                    null=True)})
    expected = NOT_INDEXED % probe._name
    assert [m.msg for m in probe._check_parent_path()] == [expected]


def test_an_isolated_probe_stays_out_of_the_name_registry():
    """Una sonda de ``isolate_apps`` no es un modelo instalado de ``base``.

    Si entra en el registro por nombre, ``load_modules`` la elige para
    ``base`` y ``_auto_init`` falla en el teardown porque su tabla no existe
    (``designs/isolated-apps-registry-leak.md``).
    """
    probe = _probe({})
    assert probe._name not in MODELS_BY_NAME
    assert MODELS_BY_NAME['ir.ui.menu']._meta.label == 'base.IrUiMenu'
