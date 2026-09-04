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

from addons.base.models.ir_actions import (IrActionsActWindow,
                                           IrActionsActions,
                                           IrActionsServer)
from addons.base.models.ir_module import IrModuleCategory

pytestmark = pytest.mark.integration


class TestCheckPath:
    """≙ ``_check_path`` (``odoo19c: ir_actions.py:82-96``)."""

    def test_a_valid_path_is_accepted(self, db):
        """CONTROL de la dirección contraria — la guarda no cierra la puerta.

        Sin este caso, una que rechazara toda ruta pasaría los demás.
        """
        action = IrActionsActions(name='Válida', type='ir.actions.actions',
                                  path='mi-accion_2')
        action.clean()

    @pytest.mark.parametrize('path', ['2empieza-con-digito', 'Mayuscula',
                                      'con espacio', 'con.punto'])
    def test_a_path_outside_the_pattern_is_refused(self, db, path):
        """El eje del patrón: minúsculas, dígitos, guion y guion bajo."""
        action = IrActionsActions(name='Mala', type='ir.actions.actions',
                                  path=path)
        with pytest.raises(ValidationError):
            action.clean()

    @pytest.mark.parametrize('path', ['m-algo', 'action-algo'])
    def test_the_two_reserved_prefixes_are_refused(self, db, path):
        """Los dos prefijos que la fuente reserva para su cliente."""
        action = IrActionsActions(name='Reservada', type='ir.actions.actions',
                                  path=path)
        with pytest.raises(ValidationError):
            action.clean()

    def test_the_reserved_word_new_is_refused(self, db):
        """CONTROL del cuarto chequeo, que este puerto NO tenía.

        Mensaje de la fuente, verbatim: *"'new' is reserved, and can not be
        used as path."* Es una comprobación aparte de los dos prefijos —
        ``new`` no empieza por ``m-`` ni por ``action-`` y **sí** cumple el
        patrón, así que los tres chequeos que había lo dejaban pasar.

        Qué lo haría fallar: quitar la comparación. Y qué lo hacía fallar
        antes de este pase: que no existiera.
        """
        action = IrActionsActions(name='Nueva', type='ir.actions.actions',
                                  path='new')
        with pytest.raises(ValidationError):
            action.clean()

    def test_a_path_that_merely_starts_with_new_is_accepted(self, db):
        """CONTROL del alcance del cuarto chequeo.

        La fuente compara por **igualdad**, no por prefijo. Qué lo haría
        fallar: escribirlo como ``startswith('new')``, que prohibiría
        ``newsletter`` sin que la fuente lo pida.
        """
        action = IrActionsActions(name='Boletin', type='ir.actions.actions',
                                  path='newsletter')
        action.clean()

    def test_without_a_path_nothing_is_checked(self, db):
        """CONTROL de la guarda ``if action.path``.

        Una acción sin ruta es lo normal: la mayoría no expone URL.
        """
        IrActionsActions(name='Sin ruta', type='ir.actions.actions').clean()


class TestCheckModel:
    """≙ ``_check_model`` (``odoo19c: ir_actions.py:270-276``)."""

    def test_a_model_that_does_not_exist_is_refused(self, db):
        """El eje: el error sale donde se escribe, no al abrir la acción."""
        action = IrActionsActWindow(name='Fantasma',
                                    type='ir.actions.act_window',
                                    res_model='no.existe.este.modelo',
                                    view_mode='list,form')
        with pytest.raises(ValidationError):
            action.clean()

    def test_a_real_model_is_accepted(self, db):
        """CONTROL de la dirección contraria."""
        IrActionsActWindow(name='Buena', type='ir.actions.act_window',
                           res_model='res.partner',
                           view_mode='list,form').clean()

    def test_the_binding_model_is_checked_too(self, db):
        """CONTROL de la segunda mitad de la restricción.

        La fuente comprueba ``res_model`` **y** ``binding_model_id``. Qué lo
        haría fallar: mirar sólo el primero, y entonces una acción anclada a
        un modelo inexistente no aparecería en ninguna barra lateral sin que
        nadie supiera por qué.
        """
        action = IrActionsActWindow(name='Anclada',
                                    type='ir.actions.act_window',
                                    res_model='res.partner',
                                    view_mode='list,form',
                                    binding_model_name='no.existe')
        with pytest.raises(ValidationError):
            action.clean()


class TestCheckViewMode:
    """≙ ``_check_view_mode`` (``odoo19c: ir_actions.py:300-307``)."""

    def test_a_duplicated_mode_is_refused(self, db):
        """El eje: el cliente pintaría la misma pestaña dos veces."""
        action = IrActionsActWindow(name='Repetida',
                                    type='ir.actions.act_window',
                                    res_model='res.partner',
                                    view_mode='list,form,list')
        with pytest.raises(ValidationError):
            action.clean()

    def test_a_space_in_the_list_is_refused(self, db):
        """CONTROL de la segunda comprobación.

        ``'list, form'`` parece correcto y no lo es: la fuente parte por coma
        sin recortar, así que el modo queda como ``' form'`` y no resuelve.
        """
        action = IrActionsActWindow(name='Con espacio',
                                    type='ir.actions.act_window',
                                    res_model='res.partner',
                                    view_mode='list, form')
        with pytest.raises(ValidationError):
            action.clean()

    def test_distinct_modes_are_accepted(self, db):
        """CONTROL de la dirección contraria."""
        IrActionsActWindow(name='Buena', type='ir.actions.act_window',
                           res_model='res.partner',
                           view_mode='list,form,kanban').clean()


class TestCheckChildren:
    """≙ ``_check_children`` (``odoo19c: ir_actions.py:968-973``), su mitad
    portable."""

    def test_an_action_cannot_be_its_own_parent(self, db):
        """El eje. Mensaje de la fuente: *"Recursion found in child server
        actions"*."""
        action = IrActionsServer.objects.create(
            name='Ciclo', type='ir.actions.server', state='multi')
        action.parent = action
        with pytest.raises(ValidationError):
            action.save()

    def test_a_cycle_of_three_is_refused(self, db):
        """CONTROL de la profundidad del recorrido."""
        a = IrActionsServer.objects.create(name='A', type='ir.actions.server',
                                           state='multi')
        b = IrActionsServer.objects.create(name='B', type='ir.actions.server',
                                           state='multi', parent=a)
        c = IrActionsServer.objects.create(name='C', type='ir.actions.server',
                                           state='multi', parent=b)
        a.parent = c
        with pytest.raises(ValidationError):
            a.save()

    def test_a_legitimate_chain_is_accepted(self, db):
        """CONTROL de la dirección contraria — encadenar no es un ciclo.

        El modo ``multi`` existe **para** encadenar; una guarda que lo
        impidiera vaciaría el modo de contenido.
        """
        a = IrActionsServer.objects.create(name='Raiz',
                                           type='ir.actions.server',
                                           state='multi')
        b = IrActionsServer.objects.create(name='Hija',
                                           type='ir.actions.server',
                                           state='multi', parent=a)
        assert b.parent_id == a.pk


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
