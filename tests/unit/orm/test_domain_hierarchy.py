"""La familia jerárquica del registro de optimizadores: ``child_of``/``parent_of``.

≙ ``odoo19c: odoo/orm/domains.py:1707`` (``_operator_hierarchy``), ``:1780``
(``_operator_child_of_domain``) y ``:1804`` (``_operator_parent_of_domain``).

Los dos operadores no existían en este árbol: no estaban en
``CONDITION_OPERATORS``, así que ``checked()`` los rechazaba al construir el
dominio. Ocho addons resolvían la descendencia a mano, cada uno con su propio
recorrido por niveles, porque el motor de dominios no sabía hacerlo.

Los casos **ejecutan** la consulta. Un caso que sólo comparase el dominio
optimizado mediría la reescritura y no las filas, y la reescritura tiene dos
ramas —la ruta materializada y el recorrido recursivo— que devuelven cosas
distintas (un ``Domain`` y un conjunto de ids) para el mismo conjunto de filas.
"""
import pytest

from django.db import connection
from django.test.utils import CaptureQueriesContext

from orm.domains import (Domain, to_q, _operator_child_of_domain,
                         _operator_parent_of_domain)

from addons.base.models.res_partner import ResPartnerCategory
from addons.mail.models.mail_message_subtype import MailMessageSubtype

pytestmark = pytest.mark.django_db


@pytest.fixture
def arbol(db):
    """Tres niveles con ``_parent_store``: raiz → medio → hoja, más un suelto."""
    raiz = ResPartnerCategory.objects.create(name='Raiz 967')
    medio = ResPartnerCategory.objects.create(name='Medio 967', parent=raiz)
    hoja = ResPartnerCategory.objects.create(name='Hoja 967', parent=medio)
    suelto = ResPartnerCategory.objects.create(name='Suelto 967')
    return raiz, medio, hoja, suelto


def _matching(model_cls, domain):
    return model_cls.objects.filter(to_q(domain, model_cls))


class TestChildOfOverTheMaterializedPath:
    """``child_of`` devuelve el subárbol, incluido el nodo de partida."""

    def test_a_root_selects_its_whole_subtree(self, arbol):
        raiz, medio, hoja, suelto = arbol
        found = set(_matching(
            ResPartnerCategory, Domain('id', 'child_of', [raiz.pk])))
        assert {raiz, medio, hoja} <= found
        assert suelto not in found

    def test_an_intermediate_node_excludes_its_ancestor(self, arbol):
        raiz, medio, hoja, _ = arbol
        found = set(_matching(
            ResPartnerCategory, Domain('id', 'child_of', [medio.pk])))
        assert {medio, hoja} <= found
        assert raiz not in found

    def test_a_leaf_selects_only_itself(self, arbol):
        raiz, medio, hoja, _ = arbol
        found = set(_matching(
            ResPartnerCategory, Domain('id', 'child_of', [hoja.pk])))
        assert hoja in found
        assert raiz not in found and medio not in found


class TestParentOfOverTheMaterializedPath:
    """``parent_of`` devuelve la cadena de ancestros, incluido el nodo."""

    def test_a_leaf_selects_its_whole_ancestry(self, arbol):
        raiz, medio, hoja, suelto = arbol
        found = set(_matching(
            ResPartnerCategory, Domain('id', 'parent_of', [hoja.pk])))
        assert {raiz, medio, hoja} <= found
        assert suelto not in found

    def test_a_root_selects_only_itself(self, arbol):
        raiz, medio, hoja, _ = arbol
        found = set(_matching(
            ResPartnerCategory, Domain('id', 'parent_of', [raiz.pk])))
        assert raiz in found
        assert medio not in found and hoja not in found


class TestTheValueIsResolvedBeforeWalking:
    """El valor de partida puede ser texto: se busca por ``display_name``."""

    def test_a_string_is_searched_by_display_name(self, arbol):
        raiz, medio, hoja, suelto = arbol
        found = set(_matching(
            ResPartnerCategory, Domain('id', 'child_of', 'Medio 967')))
        assert {medio, hoja} <= found
        assert raiz not in found and suelto not in found

    def test_a_false_value_matches_nothing(self, arbol):
        found = _matching(
            ResPartnerCategory, Domain('id', 'child_of', False))
        assert not found.exists()

    def test_a_value_that_resolves_to_nothing_matches_nothing(self, arbol):
        found = _matching(
            ResPartnerCategory, Domain('id', 'child_of', 'No existe 967'))
        assert not found.exists()


class TestTheRecursiveWalkWhenThereIsNoMaterializedPath:
    """Sin ``_parent_store`` el recorrido es por niveles — ≙ ``:1793-1801``.

    ``mail.message.subtype`` declara ``parent`` autorreferente y **no** declara
    ``parent_path``, así que ejercita la otra rama del mismo constructor. Es la
    rama que ocho addons de este árbol reescribían a mano.
    """

    @pytest.fixture
    def cadena(self, db):
        raiz = MailMessageSubtype.objects.create(name='Raiz sub 967')
        medio = MailMessageSubtype.objects.create(name='Medio sub 967',
                                                  parent=raiz)
        hoja = MailMessageSubtype.objects.create(name='Hoja sub 967',
                                                 parent=medio)
        return raiz, medio, hoja

    def test_child_of_walks_down_level_by_level(self, cadena):
        raiz, medio, hoja = cadena
        found = set(_matching(
            MailMessageSubtype, Domain('id', 'child_of', [raiz.pk])))
        assert {raiz, medio, hoja} <= found

    def test_parent_of_walks_up_level_by_level(self, cadena):
        raiz, medio, hoja = cadena
        found = set(_matching(
            MailMessageSubtype, Domain('id', 'parent_of', [hoja.pk])))
        assert {raiz, medio, hoja} <= found


class TestTheOperatorIsRefusedOnANonHierarchicalField:
    """El operador exige un campo que sea ``id`` o una relación."""

    def test_a_scalar_column_is_refused(self, db):
        with pytest.raises(ValueError):
            to_q(Domain('name', 'child_of', [1]), ResPartnerCategory)


class TestTheMaterializedPathIsAShortcutAndNotAnotherResult:
    """La rama rápida se mide por su FORMA y por su costo, no por sus filas.

    Los casos de arriba miden filas devueltas, y con eso **no pueden ver** la
    rama de ``parent_path``: anularla deja el recorrido recursivo, que devuelve
    exactamente el mismo conjunto — medido, los once casos siguen en verde con
    la rama anulada. Un verde así no distingue *"el atajo funciona"* de *"el
    atajo no existe"*.

    Lo que sí las separa es lo que la fuente declara en su propio docstring:
    *"Return a set of ids **or a domain**"*. La rama materializada devuelve un
    ``Domain`` que el motor resuelve de una pasada; la recursiva, el conjunto
    de ids que costó una consulta por nivel.
    """

    def test_child_of_returns_a_domain_when_the_path_is_materialized(self, arbol):
        raiz = arbol[0]
        resultado = _operator_child_of_domain(
            ResPartnerCategory.objects.filter(pk=raiz.pk), 'parent')
        assert isinstance(resultado, Domain)

    def test_child_of_returns_a_set_of_ids_when_it_has_to_walk(self, db):
        raiz = MailMessageSubtype.objects.create(name='Raiz 967 sin ruta')
        MailMessageSubtype.objects.create(name='Hija 967 sin ruta', parent=raiz)
        resultado = _operator_child_of_domain(
            MailMessageSubtype.objects.filter(pk=raiz.pk), 'parent')
        assert not isinstance(resultado, Domain)
        assert set(resultado) == set(
            MailMessageSubtype.objects.filter(name__endswith='967 sin ruta')
            .values_list('pk', flat=True))

    def test_parent_of_reads_the_ancestors_from_the_path_without_walking(self, arbol):
        """Los ancestros salen de la propia ``parent_path``: **una** consulta,
        sea cual sea la profundidad. El recorrido recursivo necesita una por
        nivel más su comprobación de fin, así que el conteo los separa."""
        hoja = arbol[2]
        with CaptureQueriesContext(connection) as consultas:
            resultado = _operator_parent_of_domain(
                ResPartnerCategory.objects.filter(pk=hoja.pk), 'parent')
        assert set(resultado) == {arbol[0].pk, arbol[1].pk, hoja.pk}
        assert len(consultas) == 1, [c['sql'] for c in consultas]
