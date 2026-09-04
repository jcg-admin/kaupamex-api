"""La familia relacional del registro de optimizadores de dominio.

≙ ``odoo19c: odoo/orm/domains.py:1412`` (``_optimize_relational_name_search``)
y ``:1839`` (``_optimize_m2o_bypass_comodel_id_lookup``).

Los dos resuelven la misma clase de condición —una comparación contra un campo
de relación— por caminos opuestos: el primero **entra** al comodelo cuando el
valor es texto, y el segundo **sale** de él cuando la subconsulta no aporta
nada. Ninguno de los dos era portable antes de ``api@5ae823c9``: el primero
necesita que ``display_name`` resuelva en un dominio, que es lo que ``search=``
en el campo sin columna desbloqueó (:ref:`h-api-965`).
"""
import pytest

from orm.domains import (Domain, to_q,
                         _optimize_m2o_bypass_comodel_id_lookup)

from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_groups_privilege import ResGroupsPrivilege

pytestmark = pytest.mark.django_db


class TestRelationalNameSearch:
    """Un relacional comparado con texto busca por ``display_name``."""

    def test_a_like_on_a_relational_enters_the_comodel(self):
        condition = Domain('groups', 'ilike', 'admin')
        assert condition.optimize(IrRule) == Domain(
            'groups', 'any', Domain('display_name', 'ilike', 'admin')
        ).optimize(IrRule)

    def test_a_negated_like_becomes_a_not_any_with_the_positive_inside(self):
        """La fuente lo dice: *"Negative conditions are translated into a
        'not any' for consistency"*. El operador de dentro es el positivo."""
        condition = Domain('groups', 'not ilike', 'admin')
        assert condition.optimize(IrRule) == Domain(
            'groups', 'not any', Domain('display_name', 'ilike', 'admin')
        ).optimize(IrRule)

    def test_an_inequality_against_a_string_is_refused(self):
        """Un ``<`` contra texto sobre un relacional no significa nada, y la
        fuente lo rechaza con ``TypeError`` en vez de inventar un orden."""
        with pytest.raises(TypeError):
            Domain('groups', '>', 'admin').optimize(IrRule)

    def test_a_list_of_strings_searches_them_all_by_display_name(self):
        condition = Domain('groups', 'in', ['uno', 'dos'])
        assert condition.optimize(IrRule) == Domain(
            'groups', 'any', Domain('display_name', 'in', ['uno', 'dos'])
        ).optimize(IrRule)

    def test_a_mixed_list_keeps_the_ids_beside_the_names(self):
        """Con ids y textos mezclados el dominio es la disyunción de los dos:
        los textos por etiqueta, los ids por la columna."""
        optimized = Domain('groups', 'in', ['uno', 7]).optimize(IrRule)
        expected = (Domain('groups', 'any',
                           Domain('display_name', 'in', ['uno']))
                    | Domain('groups', 'in', [7])).optimize(IrRule)
        assert optimized == expected

    def test_a_list_of_only_ids_is_left_alone(self):
        """Sin texto no hay nada que buscar por etiqueta: la condición pasa."""
        condition = Domain('groups', 'in', [1, 2])
        assert condition.optimize(IrRule) == condition.optimize(IrRule)
        assert 'display_name' not in repr(condition.optimize(IrRule))


class TestManyToOneBypassesTheSubquery:
    """``a any! (id in X)`` no necesita subconsulta: es ``a in X``.

    Sólo aplica a los operadores con ``!`` —los que ya saltaron el permiso—
    porque con el permiso vigente la subconsulta es lo que lo aplica.

    Los casos llaman al optimizador **directamente**, no al punto fijo: lo que
    la fuente declara son ocho equivalencias de reescritura, y el punto fijo
    las sigue simplificando después. Medirlo por el punto fijo mediría dos
    cosas a la vez y no distinguiría cuál de las dos falló.
    """

    def test_an_id_in_collapses_to_a_direct_comparison(self):
        condition = Domain('privilege', 'any!', Domain('id', 'in', {1, 2}))
        assert _optimize_m2o_bypass_comodel_id_lookup(
            condition, ResGroups) == Domain('privilege', 'in', {1, 2})

    def test_the_false_is_dropped_from_a_positive_in(self):
        """``a any! (id in X)`` es ``a in (X - {False})``: un ``False`` dentro
        del conjunto de ids del comodelo no designa ninguna fila."""
        condition = Domain('privilege', 'any!', Domain('id', 'in', {1, False}))
        assert _optimize_m2o_bypass_comodel_id_lookup(
            condition, ResGroups) == Domain('privilege', 'in', {1})

    def test_the_false_is_added_to_a_negated_in(self):
        """Y al negar entra: sin el ``False``, una fila con el relacional
        vacío pasaría el filtro."""
        condition = Domain('privilege', 'any!', Domain('id', 'not in', {1}))
        assert _optimize_m2o_bypass_comodel_id_lookup(
            condition, ResGroups) == Domain('privilege', 'not in', {1, False})

    def test_a_nested_any_loses_one_level(self):
        inner = Domain('name', '=', 'x')
        condition = Domain('privilege', 'any!', Domain('id', 'any!', inner))
        assert _optimize_m2o_bypass_comodel_id_lookup(
            condition, ResGroups) == Domain('privilege', 'any!', inner)

    def test_a_nested_not_any_also_demands_the_relation_is_set(self):
        """``a any! (id not any! X)`` no es sólo ``a not any! X``: una fila con
        ``a`` vacío no tiene comodelo que evaluar, así que se exige además."""
        inner = Domain('name', '=', 'x')
        condition = Domain('privilege', 'any!', Domain('id', 'not any!', inner))
        assert _optimize_m2o_bypass_comodel_id_lookup(condition, ResGroups) == (
            Domain('privilege', '!=', False)
            & Domain('privilege', 'not any!', inner))

    def test_the_outer_not_any_negates_the_whole_result(self):
        condition = Domain('privilege', 'not any!', Domain('id', 'in', {1, 2}))
        assert _optimize_m2o_bypass_comodel_id_lookup(condition, ResGroups) == \
            ~Domain('privilege', 'in', {1, 2})

    def test_a_subdomain_that_is_not_about_id_is_left_alone(self):
        """El atajo vale porque el ``id`` del comodelo **es** la columna del
        relacional. Sobre cualquier otro campo la subconsulta hace falta."""
        condition = Domain('privilege', 'any!', Domain('name', '=', 'x'))
        assert _optimize_m2o_bypass_comodel_id_lookup(
            condition, ResGroups) is condition

    def test_an_any_without_the_bang_is_left_alone(self):
        """Sin el ``!`` el permiso del comodelo sigue vigente, y saltarse la
        subconsulta se lo saltaría con él."""
        condition = Domain('privilege', 'any', Domain('id', 'in', {1, 2}))
        assert _optimize_m2o_bypass_comodel_id_lookup(
            condition, ResGroups) is condition


class TestAnyCompilesToASubquery:
    """El compilador de hoja traduce ``any`` a la subconsulta de la fuente.

    Los casos **ejecutan** la consulta, no comparan el ``Q``. Es deliberado:
    hasta ``api@707b3e28`` el compilador no conocía el operador y trataba el
    subdominio como una colección de valores, así que producía un ``Q`` que se
    construía sin error y reventaba al consultar con ``invalid literal for
    int()``. Un caso que sólo mirara el ``Q`` habría pasado con el defecto
    presente — el verde que no discrimina.
    """

    @staticmethod
    def _matching(domain):
        return ResGroups.objects.filter(to_q(domain, ResGroups))

    def test_an_any_selects_through_the_relation(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='Compras 966')
        dentro = ResGroups.objects.create(name='Comprador 966',
                                          privilege=privilege)
        fuera = ResGroups.objects.create(name='Suelto 966')
        found = self._matching(
            Domain('privilege', 'any!', Domain('name', '=', 'Compras 966')))
        assert dentro in found and fuera not in found

    def test_a_not_any_excludes_them(self, db):
        privilege = ResGroupsPrivilege.objects.create(name='Ventas 966')
        dentro = ResGroups.objects.create(name='Vendedor 966',
                                          privilege=privilege)
        found = self._matching(
            Domain('privilege', 'not any!', Domain('name', '=', 'Ventas 966')))
        assert dentro not in found

    def test_a_non_relational_field_is_refused(self, db):
        """``any`` exige una relación que atravesar; sobre una columna escalar
        no hay comodelo del que sacar la subconsulta."""
        with pytest.raises(ValueError):
            to_q(Domain('name', 'any!', Domain('name', '=', 'x')), ResGroups)
