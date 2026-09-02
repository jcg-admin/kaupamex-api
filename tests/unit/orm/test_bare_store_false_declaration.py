"""``store=False`` a secas — la forma que la fuente usa para un ``compute``
sin columna (#288).

:ref:`h-api-1020` corrigió el enrutador de :func:`make_dispatcher`, que miraba
``related`` en vez del ``store`` ya resuelto y sacaba con columna un
``fields.Integer(compute='_compute_x')``. Los siete tipos de ese molde
quedaron cerrados; los que **no** lo usan siguen enrutando por
:func:`~orm.fields_nonstored.projection_or_none`, que tiene exactamente la
misma condición.

Medido en ``odoo19c`` sobre ``addons/*/models/*.py`` y
``odoo/addons/*/models/*.py`` — declaraciones con ``compute=`` y sin
``store=True``: ``Many2many`` 137 · ``One2many`` 70 · ``Binary`` 40 ·
``Html`` 26 · ``Image`` 19 · ``Properties`` 1. No es un caso de borde: es la
forma normal de un campo calculado.

Qué haría fallar a estos casos: que un constructor devuelva algo con columna
—o levante ``TypeError``, que es lo que hacía— ante la declaración que la
fuente escribe.
"""
import pytest

import fields
from orm.fields_nonstored import NonStored


#: Los que enrutan por ``projection_or_none`` y admiten construirse sin más
#: argumentos que la declaración. ``Many2many`` va aparte: su constructor de
#: Django exige ``to`` posicional, y el punto del caso es que el enrutador
#: atienda **antes** de llegar ahí.
TYPES_WITHOUT_ARGUMENTS = ('Html', 'Binary', 'Image', 'PropertiesDefinition')


class TestTheRouterReadsTheResolvedStore:
    """El enrutador decide por ``store``, no por la presencia de ``related``."""

    @pytest.mark.parametrize('name', TYPES_WITHOUT_ARGUMENTS)
    def test_a_bare_store_false_has_no_column(self, name):
        field = getattr(fields, name)(store=False, compute='_compute_x')
        assert isinstance(field, NonStored), type(field).__name__

    def test_the_many_to_many_does_not_need_its_comodel(self):
        """Sin columna no hay tabla intermedia que definir, así que el
        comodelo deja de hacer falta — la misma asimetría que ya rige para el
        ``related=`` de los relacionales."""
        field = fields.Many2many(store=False, compute='_compute_x')
        assert isinstance(field, NonStored), type(field).__name__

    def test_the_properties_field_has_no_column_either(self):
        field = fields.Properties('Properties', store=False,
                                  definition='company_id.employee_props')
        assert isinstance(field, NonStored), type(field).__name__


class TestTheColumnBranchStillExists:
    """El control que discrimina: si el enrutador devolviera siempre el
    descriptor, la rama con columna dejaría de existir sin que nadie lo note.
    """

    @pytest.mark.parametrize('name', TYPES_WITHOUT_ARGUMENTS)
    def test_without_the_declaration_the_field_keeps_its_column(self, name):
        field = getattr(fields, name)()
        assert not isinstance(field, NonStored), type(field).__name__

    def test_an_explicit_store_true_keeps_its_column(self):
        field = fields.Html(store=True)
        assert not isinstance(field, NonStored), type(field).__name__


class TestTheDeclarationSurvivesInTheField:
    """Lo declarado queda greppeable en el campo, no sólo en la rama tomada."""

    def test_the_compute_is_kept(self):
        field = fields.Binary(store=False, compute='_compute_payload')
        assert field.compute == '_compute_payload'

    def test_the_store_is_false(self):
        assert fields.Html(store=False, compute='_compute_x').store is False


class TestTheExclusionSurvivesTheRouter:
    """``store=False`` y ``company_dependent=True`` siguen siendo excluyentes.

    La comprobación vivía **después** de la llamada al enrutador, así que sólo
    se alcanzaba cuando éste devolvía ``None``. Al enseñarle a atender un
    ``store=False`` a secas, la contradicción pasó a resolverse antes y el
    ``ValueError`` dejó de emitirse: un campo declarado imposible salía como
    descriptor sin columna, en silencio. Ahora la exclusión vive en el propio
    enrutador, que es donde se resuelve si hay columna.
    """

    def test_the_many_to_one_still_refuses_the_contradiction(self):
        with pytest.raises(ValueError, match='excluyentes'):
            fields.Many2one('base.ResPartner', store=False,
                            company_dependent=True)

    def test_the_html_field_refuses_it_too(self):
        with pytest.raises(ValueError, match='excluyentes'):
            fields.Html(store=False, company_dependent=True)

    def test_the_company_dependent_branch_still_exists(self):
        """El control: sin ``store=False`` la rama con jsonb sigue viva."""
        field = fields.Html(company_dependent=True)
        assert not isinstance(field, NonStored), type(field).__name__
