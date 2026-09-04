"""``any`` pierde el permiso del comodelo cuando ya está concedido.

≙ ``odoo19c: odoo/orm/domains.py:1832-1836`` (``_optimize_any_with_rights``).

El optimizador es de dos líneas y decide algo grande: si la subconsulta del
comodelo aplica sus reglas de fila o no. Convierte ``any``/``not any`` en su
forma con ``!`` —la que salta el permiso— en dos situaciones, y **sólo** en
esas dos: el contexto ya está elevado, o el propio campo declara que el
permiso del comodelo no aplica (``bypass_search_access``).

Los casos miden la reescritura y no las filas: lo que el optimizador decide es
**qué operador** queda, y de ahí cuelga el resto de la cadena
(``_optimize_m2o_bypass_comodel_id_lookup`` sólo actúa sobre los que llevan
``!``). Medir filas aquí no distinguiría el permiso concedido del permiso
ausente, porque en una base de pruebas sin reglas sembradas las dos formas
devuelven lo mismo — el verde que no discrimina.
"""
import pytest

from orm.domains import Domain, DomainCondition, _optimize_any_with_rights
from orm.environments import sudo
from orm.inherits import apply_inherits

from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups

pytestmark = pytest.mark.django_db


class TestTheElevationGrantsIt:
    """Con el contexto elevado la subconsulta no tiene permiso que aplicar."""

    def test_an_any_becomes_any_bang_under_sudo(self):
        condition = Domain('privilege', 'any', Domain('name', '=', 'x'))
        with sudo():
            assert _optimize_any_with_rights(condition, ResGroups) == \
                DomainCondition('privilege', 'any!', condition.value)

    def test_a_not_any_becomes_not_any_bang_under_sudo(self):
        condition = Domain('privilege', 'not any', Domain('name', '=', 'x'))
        with sudo():
            assert _optimize_any_with_rights(condition, ResGroups) == \
                DomainCondition('privilege', 'not any!', condition.value)

    def test_without_the_elevation_the_condition_is_left_alone(self):
        """Sin elevación el permiso del comodelo sigue vigente, y es la
        subconsulta quien lo aplica: quitarle el ``!`` sería saltárselo."""
        condition = Domain('privilege', 'any', Domain('name', '=', 'x'))
        assert _optimize_any_with_rights(condition, ResGroups) is condition


class TestTheFieldGrantsIt:
    """Un campo que declara ``bypass_search_access`` lo concede por sí solo."""

    def test_a_field_that_bypasses_it_needs_no_elevation(self):
        field = ResGroups._meta.get_field('privilege')
        assert not getattr(field, 'bypass_search_access', False)
        field.bypass_search_access = True
        try:
            condition = Domain('privilege', 'any', Domain('name', '=', 'x'))
            assert _optimize_any_with_rights(condition, ResGroups) == \
                DomainCondition('privilege', 'any!', condition.value)
        finally:
            field.bypass_search_access = False

    def test_the_default_is_false_and_not_absent(self):
        """El atributo se declara en el campo, no se consulta con un
        ``getattr`` de respaldo: un campo relacional que no lo declarase
        haría indistinguible *"no lo concede"* de *"nadie lo marcó"*."""
        assert ResGroups._meta.get_field('privilege').bypass_search_access is False
        assert IrRule._meta.get_field('groups').bypass_search_access is False


class TestTheDelegationImpliesIt:
    """``_inherits`` lo implica — ≙ ``fields_relational.py:257-259``.

    La fuente lo dice en un comentario de una línea: *"self.delegate implies
    self.bypass_search_access"*. Tiene que ser así: un field delegado expone
    los campos del delegado como propios, y aplicar el permiso del comodelo
    por debajo dejaría al registro delegante viendo la mitad de sí mismo.
    """

    def test_a_delegated_fk_bypasses_the_comodel_rights(self):
        field = ResGroups._meta.get_field('privilege')
        assert not field.bypass_search_access
        apply_inherits(ResGroups, field.related_model, 'privilege')
        try:
            assert field.bypass_search_access is True
        finally:
            field.bypass_search_access = False
