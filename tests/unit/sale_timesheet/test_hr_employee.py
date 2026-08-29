"""Contrato de ``default_get`` de ``hr.employee`` — addon ``sale_timesheet``.

Adaptación de Odoo ``sale_timesheet/models/hr_employee.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``, LGPL-3).

Un solo símbolo en la referencia y un solo comportamiento: cuando el empleado
se crea desde el formulario de tarifas de un proyecto, hereda la compañía de
ese proyecto. El canal es una clave de contexto, y aquí también.

**Por qué este archivo existe.** El puerto declaraba el símbolo como
bloqueado *"por mecanismo ausente"* sobre dos premisas que habían caducado —
``default_get`` y el contexto de entorno se construyeron después— y por tanto
no tenía caso que lo midiera. Sin él, la corrección sería una afirmación.
"""
import pytest

from django.apps import apps

from addons.sale_timesheet.models.hr_employee import (
    CREATE_PROJECT_EMPLOYEE_MAPPING,
)
from orm.environments import context_scope

pytestmark = pytest.mark.django_db

HrEmployee = apps.get_model('hr', 'HrEmployee')


class TestDefaultGetInheritsTheProjectCompany:
    def test_the_context_key_supplies_the_company(self):
        """El caso de la fuente: con la clave puesta, ese id gana."""
        with context_scope(**{CREATE_PROJECT_EMPLOYEE_MAPPING: 7}):
            defaults = HrEmployee.default_get(['company_id'])
        assert defaults['company_id'] == 7

    def test_without_the_key_nothing_is_added(self):
        """La guarda ``if project_company_id`` de la fuente."""
        defaults = HrEmployee.default_get(['company_id'])
        assert 'company_id' not in defaults

    def test_a_falsy_value_is_treated_as_absent(self):
        """La fuente lee con ``.get(clave, False)`` y ramifica sobre la
        verdad del valor, no sobre la presencia de la clave. Un ``False``
        explícito no debe inventar un default."""
        with context_scope(**{CREATE_PROJECT_EMPLOYEE_MAPPING: False}):
            defaults = HrEmployee.default_get(['company_id'])
        assert 'company_id' not in defaults

    def test_the_base_defaults_survive_the_chain(self):
        """El control que distingue ``combine`` del relevo por ``None``.

        ``extend_model(metodos=)`` instala con relevo: el eslabón previo corre
        SÓLO si el nuevo devuelve ``None``. Esta aportación devuelve ``{}``
        cuando no hay contexto —que no es ``None``— así que con el relevo el
        ``default_get`` de la base entera se perdería.

        Se mide pidiendo un campo que la base SÍ resuelve por contexto
        (``default_<campo>``, paso 1 de ``orm.models.BaseModel.default_get``)
        y comprobando que sigue llegando.

        Escribirlo destapó que la base **no estaba**: ``hr.employee`` no
        adoptaba ``models.DefaultGetMixin``, así que la cadena no tenía
        eslabón previo y esta aportación era la respuesta entera. En la fuente
        todo modelo lleva ``default_get``; aquí es un mixin que el modelo
        adopta, y ``hr.employee`` no lo hacía. Se le añadió — sin migración:
        el mixin no declara campos.

        Dos premisas mías fallaron antes de llegar aquí, y las dos habrían
        dado un verde que no discrimina: ``name`` no es campo de
        ``hr.employee`` (viene por ``related`` del recurso) y
        ``resource_calendar`` tampoco resolvía por contexto. ``company_id``
        sí, y es además el campo que la fuente toca.
        """
        with context_scope(default_company_id=11):
            defaults = HrEmployee.default_get(['company_id'])
        assert defaults['company_id'] == 11

    def test_the_base_link_is_reached_when_this_addon_adds_nothing(self):
        """Sin la clave de este addon, la respuesta es la de la base entera.

        Es el otro lado del control anterior: si el relevo por ``None``
        sustituyera a ``combine``, esta aportación devolvería ``{}`` —que no
        es ``None``— y la base no correría.
        """
        with context_scope(default_company_id=11):
            defaults = HrEmployee.default_get(['company_id'])
        assert defaults['company_id'] == 11

    def test_this_addon_wins_over_the_base_for_the_same_key(self):
        """El orden de la fusión, que la fuente fija con ``result[...] = ...``
        DESPUÉS del ``super()``: ante la misma clave, este addon pisa."""
        with context_scope(default_company_id=99,
                           **{CREATE_PROJECT_EMPLOYEE_MAPPING: 3}):
            defaults = HrEmployee.default_get(['company_id'])
        assert defaults['company_id'] == 3
