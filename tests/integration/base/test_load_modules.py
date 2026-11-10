"""El ciclo de instalación sobre ``INSTALLED_APPS`` — ≙ ``load_modules`` y
``load_module_graph`` (``odoo19c: odoo/modules/loading.py``).

Por módulo, en orden de grafo: ``init_models`` con el módulo en el contexto
(reflexión y XML-ID de modelos), ``load_data`` de su clave ``data`` y estado
``installed``. Corre tras ``migrate`` (``post_migrate`` con ``plan``) y no
tras un ``flush``. Diseño: ``designs/module-install-cycle.md``, L3.
"""
import pytest
from django.apps import apps
from django.core.management.sql import emit_post_migrate_signal

import modules.loading as loading
from modules.module import installed_addon_names

pytestmark = pytest.mark.django_db


def _module_states():
    IrModule = apps.get_model('base', 'IrModule')
    return dict(IrModule.objects.values_list('name', 'state'))


def _xmlid_exists(module, name):
    return apps.get_model('base', 'IrModelData').objects.filter(
        module=module, name=name).exists()


def _forget_the_installation():
    """La base de pruebas ya pasó por ``migrate`` y con él por el ciclo: se
    deshace, dentro de la transacción de la prueba, lo que el ciclo hace."""
    apps.get_model('base', 'IrModule').objects.update(state='uninstalled')
    apps.get_model('base', 'IrModelData').objects.filter(
        name__startswith='model_').delete()


def test_every_installed_addon_ends_installed():
    _forget_the_installation()
    assert 'installed' not in set(_module_states().values())
    loading.load_modules('default')
    states = _module_states()
    assert {name: states.get(name) for name in installed_addon_names()} == {
        name: 'installed' for name in installed_addon_names()}


def test_the_models_get_their_module_xmlid():
    _forget_the_installation()
    assert not _xmlid_exists('hr', 'model_hr_employee')
    loading.load_modules('default')
    assert _xmlid_exists('hr', 'model_hr_employee')
    assert _xmlid_exists('hr_skills', 'model_hr_skill_type')


def test_the_data_files_load_in_graph_order(monkeypatch):
    calls = []
    real = loading.load_data

    def spy(idref, mode, kind, package, *, using):
        calls.append((package.name, mode, kind))
        return real(idref, mode, kind, package, using=using)

    monkeypatch.setattr(loading, 'load_data', spy)
    _forget_the_installation()
    loading.load_modules('default')
    names = [name for name, _, _ in calls]
    assert names.index('base') < names.index('hr') < names.index('hr_skills')
    assert {kind for _, _, kind in calls} == {'data'}
    assert {mode for _, mode, _ in calls} == {'init'}
    calls.clear()
    loading.load_modules('default')
    assert {mode for _, mode, _ in calls} == {'update'}


def test_a_second_run_changes_nothing():
    _forget_the_installation()
    loading.load_modules('default')
    IrModelData = apps.get_model('base', 'IrModelData')
    before = IrModelData.objects.count()
    loading.load_modules('default')
    assert IrModelData.objects.count() == before


def test_migrate_runs_the_cycle_and_flush_does_not(monkeypatch):
    seen = []
    monkeypatch.setattr(loading, 'load_modules', seen.append)
    emit_post_migrate_signal(0, False, 'default', plan=[])
    emit_post_migrate_signal(0, False, 'default')
    assert seen == ['default']


def test_a_failing_module_leaves_none_of_its_rows(monkeypatch):
    """Cada módulo se instala en su transacción: un archivo de datos que falla
    a medias no deja filas, como en la fuente, que confirma tras cargar un
    módulo y revierte el que falla (``loading.py:186-260``)."""
    privilege = apps.get_model('base', 'ResGroupsPrivilege')
    real = loading.load_data

    def failing(idref, mode, kind, package, *, using):
        if package.name == 'hr':
            privilege.objects.using(using).create(name='Carga a medias')
            raise RuntimeError('archivo de datos roto')
        return real(idref, mode, kind, package, using=using)

    monkeypatch.setattr(loading, 'load_data', failing)
    with pytest.raises(RuntimeError):
        loading.load_modules('default')
    assert not privilege.objects.filter(name='Carga a medias').exists()
