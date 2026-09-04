"""``any`` — la familia que resuelve el subdominio de una relacion.

Cuarta del registro. Dos optimizadores con formas distintas:

- ``_optimize_any_domain`` normaliza el VALOR a un ``Domain`` y resuelve el
  caso ``id any (...)``, que no necesita subconsulta ninguna.
- ``_optimize_any_domain_at_level`` optimiza el subdominio CONTRA EL COMODELO,
  y se registra en los cuatro niveles a la vez.

La fuente resuelve el comodelo con ``model.env[field.comodel_name]``. Aqui no
hay ``env`` sobre una clase de Django —medido: ``IrRule.env`` levanta
``AttributeError``— y no hace falta: Django lo resuelve en el propio campo,
con ``field.related_model``. Es divergencia de MECANISMO, no de alcance.
"""
import pytest

from addons.base.models.ir_rule import IrRule
from addons.base.models.res_groups import ResGroups
from orm.domains import Domain, DomainCondition


class TestTheValueBecomesADomain:
    """``_optimize_any_domain`` — el valor de un ``any`` es siempre un dominio."""

    def test_a_list_value_becomes_a_domain(self):
        result = Domain('groups', 'any', [('name', '=', 'x')]).optimize(IrRule)
        assert isinstance(result, DomainCondition), result
        assert isinstance(result.value, Domain)

    def test_a_domain_value_is_left_alone(self):
        """La fuente lo comenta: *"avoid recreating the same condition"*.

        Esa identidad es lo que corta el bucle de punto fijo, que compara
        por ``is``.
        """
        result = Domain('groups', 'any', [('name', '=', 'x')]).optimize(IrRule)
        assert isinstance(result.value, Domain)


class TestAnyOverTheIdCollapses:
    """``id any (dominio)`` es el dominio; no hay relacion que atravesar.

    La fuente lo escribe como equivalencia::

        id ANY domain      <=>  domain
        id NOT ANY domain  <=>  ~domain
    """

    def test_any_over_id_is_the_subdomain(self):
        result = Domain('id', 'any', [('name', '=', 'x')]).optimize(IrRule)
        assert isinstance(result, DomainCondition), result
        assert result.field_expr == 'name'

    def test_not_any_over_id_is_the_negated_subdomain(self):
        """El espejo: la negacion del subdominio, no el subdominio."""
        positive = Domain('id', 'any', [('name', '=', 'x')]).optimize(IrRule)
        negative = Domain('id', 'not any', [('name', '=', 'x')]).optimize(IrRule)
        assert negative != positive

    def test_a_relational_field_does_NOT_collapse(self):
        """El control del alcance: solo el pk colapsa.

        Sin este caso, los dos anteriores no distinguirian *"``id`` es
        especial"* de *"todo ``any`` colapsa a su subdominio"*.
        """
        result = Domain('groups', 'any', [('name', '=', 'x')]).optimize(IrRule)
        assert result.field_expr == 'groups'
        assert isinstance(result.value, Domain)


class TestTheSubdomainIsOptimizedAgainstTheComodel:
    """``_optimize_any_domain_at_level`` — el subdominio se optimiza alla.

    Es lo que hace observable que el comodelo se resuelva: el subdominio se
    optimiza con las reglas del OTRO modelo, no con las de este.
    """

    def test_the_comodel_resolves_from_the_field(self):
        """La divergencia de mecanismo, medida: Django lo trae en el campo."""
        assert IrRule._meta.get_field('groups').related_model is ResGroups

    def test_a_boolean_subdomain_is_optimized_with_the_comodel_rules(self):
        """``share`` es booleano en ``ResGroups``, y su optimizador aplica.

        Si el subdominio no se optimizara, ``in [False]`` llegaria intacto; al
        optimizarse contra el comodelo, el optimizador de booleano lo invierte
        a ``not in [True]``.
        """
        result = Domain('groups', 'any', [('share', 'in', [False])]).optimize(IrRule)
        inner = result.value
        assert isinstance(inner, DomainCondition), inner
        assert inner.operator == 'not in'
        assert list(inner.value) == [True]

    def test_a_field_of_this_model_does_NOT_resolve_in_the_subdomain(self):
        """El caso que discrimina, y lo destapo el propio porte.

        ``active`` existe en ``IrRule`` y NO en ``ResGroups``. Si el subdominio
        se optimizara contra este modelo, el campo resolveria y el caso
        pasaria en silencio. Que levante es la evidencia de que el comodelo es
        quien manda — sin este caso, el anterior no distinguiria *"se optimiza
        contra el comodelo"* de *"se optimiza contra cualquiera"*.
        """
        assert any(f.name == 'active' for f in IrRule._meta.get_fields())
        assert not any(f.name == 'active' for f in ResGroups._meta.get_fields())
        with pytest.raises(ValueError):
            Domain('groups', 'any', [('active', '=', True)]).optimize(IrRule)

    def test_a_field_only_the_comodel_has_DOES_resolve(self):
        """El espejo: un campo propio del comodelo si resuelve."""
        assert not any(f.name == 'share' for f in IrRule._meta.get_fields())
        result = Domain('groups', 'any', [('share', '=', True)]).optimize(IrRule)
        assert isinstance(result, DomainCondition), result

    def test_an_empty_subdomain_collapses_the_condition(self):
        """Un subdominio FALSO hace la condicion constante.

        La fuente lo comenta: *"if the domain is empty, the result is a
        constant"*. ``any`` sobre nada es FALSO; ``not any`` sobre nada es
        VERDADERO.
        """
        assert Domain('groups', 'any', Domain.FALSE).optimize_full(
            IrRule) == Domain.FALSE
        assert Domain('groups', 'not any', Domain.FALSE).optimize_full(
            IrRule) == Domain.TRUE


class TestAnyOverANonRelationalFieldRaises:
    """El contrato: ``any`` exige una relacion que atravesar."""

    def test_it_raises(self):
        with pytest.raises(ValueError):
            Domain('name', 'any', [('x', '=', 1)]).optimize_full(IrRule)
