"""Tests — las restricciones de la familia ``ir.actions.*`` y de la categoría.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_actions.py``:
``_check_path`` (``:82-96``), ``_check_model`` (``:270-276``),
``_check_view_mode`` (``:300-307``) y ``_check_children`` (``:968-973``); más
``ir_module.py::_check_parent_not_circular`` (``:102-105``).

Todas rechazan un estado imposible al guardar. Ninguna es cosmética:

- una **ruta** que reclame un prefijo del cliente secuestra una URL que ya
  significa otra cosa;
- un **modelo** inexistente en una acción produce un error al abrirla, lejos
  de donde se escribió;
- un **modo de vista** duplicado hace que el cliente pinte la misma pestaña
  dos veces;
- un **ciclo** de acciones compuestas o de categorías no termina.

Qué haría fallar a cada control se declara en cada caso.
"""

import pytest

from django.core.exceptions import ValidationError

from addons.base.models.ir_actions import (
    IrActionsActWindow,
    IrActionsServer,
)
from addons.base.models.ir_model import IrModel
from addons.base.models.ir_module import IrModuleCategory
from orm.environments import sudo

pytestmark = pytest.mark.integration


@pytest.fixture
def superuser():
    """El ``TransactionCase`` de la fuente corre como superusuario: las
    restricciones se miden sin el control de acceso de por medio."""
    with sudo():
        yield


def _window(**values):
    return IrActionsActWindow.create({
        'name': 'Ventana', 'res_model': 'res.partner',
        'view_mode': 'list,form', **values})


@pytest.mark.usefixtures('superuser')
class TestCheckPath:
    """≙ ``_check_path`` (``odoo19c: ir_actions.py:81-103``), una restricción
    ``@api.constrains('path')``: corre en ``create`` y en ``write``."""

    def test_a_valid_path_is_accepted(self, db):
        """CONTROL de la dirección contraria — la guarda no cierra la puerta.

        Sin este caso, una que rechazara toda ruta pasaría los demás.
        """
        assert _window(path='mi-accion_2').path == 'mi-accion_2'

    @pytest.mark.parametrize(
        'path',
        ['2empieza-con-digito', 'Mayuscula', 'con espacio', 'con.punto'],
    )
    def test_a_path_outside_the_pattern_is_refused(self, db, path):
        """El eje del patrón: minúsculas, dígitos, guion y guion bajo."""
        with pytest.raises(ValidationError):
            _window(path=path)

    @pytest.mark.parametrize('path', ['m-algo', 'action-algo'])
    def test_the_two_reserved_prefixes_are_refused(self, db, path):
        """Los dos prefijos que la fuente reserva para su cliente."""
        with pytest.raises(ValidationError):
            _window(path=path)

    def test_the_reserved_word_new_is_refused(self, db):
        """``new`` cumple el patrón y no empieza por ningún prefijo: sólo lo
        rechaza la comparación por igualdad."""
        with pytest.raises(ValidationError):
            _window(path='new')

    def test_a_path_that_merely_starts_with_new_is_accepted(self, db):
        """CONTROL del alcance: la fuente compara por igualdad, no por
        prefijo; ``newsletter`` es una ruta legítima."""
        assert _window(path='newsletter').path == 'newsletter'

    def test_without_a_path_nothing_is_checked(self, db):
        """CONTROL de la guarda ``if action.path``."""
        assert not _window().path

    def test_the_check_runs_on_write(self, db):
        """``@api.constrains`` corre también al escribir el campo."""
        action = _window()
        with pytest.raises(ValidationError):
            action.write({'path': 'm-algo'})

    def test_the_path_is_unique_across_the_action_tables(self, db):
        """El caso que sólo el ``search_count`` detecta (``:94-103``).

        Las tablas de los subtipos heredan de ``ir_actions`` y un índice
        único vale sólo en su tabla: la misma ruta en una acción de ventana y
        en una de servidor no la ve ninguno de los dos.
        """
        _window(path='compartida')
        with pytest.raises(ValidationError):
            IrActionsServer.create({
                'name': 'Servidor', 'model_id': IrModel._get_id('res.partner'),
                'path': 'compartida'})


@pytest.mark.usefixtures('superuser')
class TestCheckModel:
    """≙ ``_check_model`` (``odoo19c: ir_actions.py:270-276``),
    ``@api.constrains('res_model', 'binding_model_id')``."""

    def test_a_model_that_does_not_exist_is_refused(self, db):
        """El eje: el error sale donde se escribe, no al abrir la acción."""
        with pytest.raises(ValidationError):
            _window(res_model='no.existe.este.modelo')

    def test_a_real_model_is_accepted(self, db):
        """CONTROL de la dirección contraria."""
        assert _window().res_model == 'res.partner'

    def test_the_binding_model_is_checked_too(self, db):
        """CONTROL de la segunda mitad de la restricción: ``binding_model_id``
        también se comprueba contra el entorno."""
        missing = IrModel.objects.create(
            name='No existe', model='x_no_existe', state='manual')
        with pytest.raises(ValidationError):
            _window(binding_model_id=missing.pk)


def test_the_django_class_check_keeps_its_own_check_model(db):
    """``Model.check`` llama a ``cls._check_model()``, el ``classmethod`` de
    Django con el mismo nombre que la restricción de la fuente. Sobre la
    clase tiene que seguir respondiendo el de Django; sin
    ``ClassCheckShadow`` el sistema de checks muere con un ``TypeError``."""
    assert isinstance(IrActionsActWindow.check(), list)
    assert IrActionsActWindow._check_model() == []


@pytest.mark.usefixtures('superuser')
class TestCheckViewMode:
    """≙ ``_check_view_mode`` (``odoo19c: ir_actions.py:300-307``),
    ``@api.constrains('view_mode')``."""

    def test_a_duplicated_mode_is_refused(self, db):
        """El eje: el cliente pintaría la misma pestaña dos veces."""
        with pytest.raises(ValidationError):
            _window(view_mode='list,form,list')

    def test_a_mode_that_is_a_single_space_is_refused(self, db):
        """``' ' in modes`` es pertenencia en la lista: rechaza un modo que
        es exactamente un espacio."""
        with pytest.raises(ValidationError):
            _window(view_mode='list, ,form')

    def test_a_mode_with_a_leading_space_is_accepted(self, db):
        """CONTROL del alcance de la pertenencia: ``'list, form'`` parte en
        ``['list', ' form']``, y ``' '`` no está en esa lista. La fuente lo
        admite; rechazarlo sería otra regla."""
        assert _window(view_mode='list, form').view_mode == 'list, form'

    def test_distinct_modes_are_accepted(self, db):
        """CONTROL de la dirección contraria."""
        assert _window(view_mode='list,form,kanban').view_mode == (
            'list,form,kanban')


@pytest.mark.usefixtures('superuser')
class TestCheckChildren:
    """≙ ``_check_children`` (``odoo19c: ir_actions.py:968-973``), su mitad
    portable."""

    def test_an_action_cannot_be_its_own_parent(self, db):
        """El eje. Mensaje de la fuente: *"Recursion found in child server
        actions"*."""
        action = IrActionsServer.objects.create(
            name='Ciclo', type='ir.actions.server', state='multi',
            model_id=IrModel._get('res.partner')
        )
        with pytest.raises(ValidationError):
            action.write({'parent_id': action.id})

    def test_a_cycle_of_three_is_refused(self, db):
        """CONTROL de la profundidad del recorrido."""
        a = IrActionsServer.objects.create(
            name='A', type='ir.actions.server', state='multi',
            model_id=IrModel._get('res.partner')
        )
        b = IrActionsServer.objects.create(
            name='B', type='ir.actions.server', state='multi', parent_id=a,
            model_id=IrModel._get('res.partner')
        )
        c = IrActionsServer.objects.create(
            name='C', type='ir.actions.server', state='multi', parent_id=b,
            model_id=IrModel._get('res.partner')
        )
        with pytest.raises(ValidationError):
            a.write({'parent_id': c.id})

    def test_a_legitimate_chain_is_accepted(self, db):
        """CONTROL de la dirección contraria — encadenar no es un ciclo.

        El modo ``multi`` existe **para** encadenar; una guarda que lo
        impidiera vaciaría el modo de contenido.
        """
        a = IrActionsServer.objects.create(
            name='Raiz', type='ir.actions.server', state='multi',
            model_id=IrModel._get('res.partner')
        )
        b = IrActionsServer.objects.create(
            name='Hija', type='ir.actions.server', state='multi', parent_id=a,
            model_id=IrModel._get('res.partner')
        )
        assert b.parent_id == a


class TestCheckParentNotCircular:
    """≙ ``_check_parent_not_circular`` (``odoo19c: ir_module.py:102-105``)."""

    def test_a_category_cannot_be_its_own_parent(self, db):
        """El eje. Mensaje de la fuente: *"You cannot create recursive
        categories."*"""
        category = IrModuleCategory.objects.create(name='Ciclo')
        category.parent = category
        with pytest.raises(ValidationError):
            category.save()

    def test_a_cycle_of_three_is_refused(self, db):
        """CONTROL de la profundidad del recorrido."""
        a = IrModuleCategory.objects.create(name='A')
        b = IrModuleCategory.objects.create(name='B', parent=a)
        c = IrModuleCategory.objects.create(name='C', parent=b)
        a.parent = c
        with pytest.raises(ValidationError):
            a.save()

    def test_a_legitimate_hierarchy_is_accepted(self, db):
        """CONTROL de la dirección contraria — las categorías anidan."""
        a = IrModuleCategory.objects.create(name='Raiz')
        b = IrModuleCategory.objects.create(name='Hija', parent=a)
        assert b.parent_id == a.pk
