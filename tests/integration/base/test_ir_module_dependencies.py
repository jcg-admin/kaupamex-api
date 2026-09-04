"""Tests — el grafo de dependencias y exclusiones del catálogo técnico.

Contrato adaptado de ``odoo19c: odoo/addons/base/models/ir_module.py``:
``_compute_depend`` (``:1021-1030``), ``_search_depend`` (``:1032-1037``),
``_compute_state`` (``:1038-1041``), ``all_dependencies`` (``:1043-1060``) y
la clase ``ir.module.module.exclusion`` entera (``:1065-1102``).

Nada de esto necesita el instalador: son aristas declaradas en el manifest y
su resolución contra el catálogo. Lo que el instalador haría con ellas —negarse
a instalar— es otra cosa, y no se porta.

Qué haría fallar a cada control se declara en su caso.
"""
import pytest

from django.db import IntegrityError, transaction

from addons.base.models import (IrModule, IrModuleDependency,
                                IrModuleExclusion)

pytestmark = pytest.mark.integration


@pytest.fixture
def catalogue(db):
    """Tres addons: ``sale`` depende de ``product``, que depende de ``base``."""
    base    = IrModule.objects.create(name='base', state='installed')
    product = IrModule.objects.create(name='product', state='installed')
    sale    = IrModule.objects.create(name='sale', state='uninstalled')
    IrModuleDependency.objects.create(module=product, name='base')
    IrModuleDependency.objects.create(module=sale, name='product')
    return {'base': base, 'product': product, 'sale': sale}


class TestComputeDepend:
    """≙ ``_compute_depend`` (``odoo19c: ir_module.py:1021-1030``)."""

    def test_the_name_resolves_to_the_module_in_the_catalogue(self, catalogue):
        edge = IrModuleDependency.objects.get(name='product')
        assert edge._compute_depend() == catalogue['product']

    def test_a_name_absent_from_the_catalogue_resolves_to_none(self, catalogue):
        """El caso que justifica que la tabla guarde un nombre y no una FK.

        Sin él, un porte que hubiera declarado la columna como FK pasaría todo
        lo demás: la arista huérfana es el único caso que una FK prohíbe.
        """
        edge = IrModuleDependency.objects.create(
            module=catalogue['sale'], name='addon_que_no_esta')
        assert edge._compute_depend() is None

    def test_the_batch_resolves_every_edge_in_one_query(
            self, catalogue, django_assert_num_queries):
        """La razón de portar la forma de lote de la fuente, medida.

        Sin ella, resolver N aristas cuesta N consultas. El caso fija el
        número: si alguien reescribe el lote como un bucle de
        ``_compute_depend``, el conteo sube y el caso cae.
        """
        edges = list(IrModuleDependency.objects.all())
        assert len(edges) == 2
        with django_assert_num_queries(1):
            resolved = IrModuleDependency._compute_depend_batch(edges)
        assert set(resolved.values()) == {catalogue['base'],
                                          catalogue['product']}


class TestSearchDepend:
    """≙ ``_search_depend`` (``odoo19c: ir_module.py:1032-1037``)."""

    def test_it_finds_the_edges_that_point_at_a_module(self, catalogue):
        found = IrModuleDependency._search_depend([catalogue['product']])
        assert [edge.name for edge in found] == ['product']

    def test_a_module_nobody_depends_on_yields_nothing(self, catalogue):
        """CONTROL de la dirección contraria: sin él, una búsqueda que
        devolviera SIEMPRE todas las aristas pasaría el caso anterior.
        """
        assert not IrModuleDependency._search_depend([catalogue['sale']])

    def test_it_accepts_primary_keys_as_well_as_instances(self, catalogue):
        found = IrModuleDependency._search_depend([catalogue['base'].pk])
        assert [edge.name for edge in found] == ['base']


class TestComputeState:
    """≙ ``_compute_state`` (``odoo19c: ir_module.py:1038-1041``)."""

    def test_the_state_is_that_of_the_module_it_points_at(self, catalogue):
        edge = IrModuleDependency.objects.get(name='product')
        assert edge._compute_state() == 'installed'

    def test_an_orphan_edge_is_unknown_not_uninstalled(self, catalogue):
        """La distinción entera del método.

        Sin la caída a ``unknown``, una arista huérfana heredaría el default
        del campo —``uninstalled``— y se leería como "está y no se instaló",
        que es un hecho distinto de "no sé si existe".
        """
        edge = IrModuleDependency.objects.create(
            module=catalogue['sale'], name='addon_que_no_esta')
        assert edge._compute_state() == 'unknown'
        assert edge._compute_state() != IrModule.STATE_UNINSTALLED

    def test_unknown_is_in_the_vocabulary_and_the_module_states_too(self):
        codes = [code for code, _label in IrModuleDependency.DEP_STATES]
        assert 'unknown' in codes
        for code, _label in IrModule.STATES:
            assert code in codes


class TestAllDependencies:
    """≙ ``all_dependencies`` (``odoo19c: ir_module.py:1043-1060``)."""

    def test_it_closes_over_the_transitive_reach(self, catalogue):
        """El punto del método: ``sale`` no declara ``base`` y aun así lo
        alcanza por ``product``.
        """
        graph = IrModuleDependency.all_dependencies(['sale'])
        assert graph == {'sale': ['product'], 'product': ['base']}

    def test_a_module_without_dependencies_yields_an_empty_graph(self, catalogue):
        assert IrModuleDependency.all_dependencies(['base']) == {}

    def test_a_cycle_terminates(self, catalogue):
        """La razón por la que la fuente resuelve por oleadas y no recursivo.

        Sin la marca de lo ya buscado, este caso no termina — no falla: cuelga.
        Es el control que distingue "resuelve el grafo" de "resuelve el árbol".
        """
        IrModuleDependency.objects.create(
            module=catalogue['base'], name='sale')
        graph = IrModuleDependency.all_dependencies(['sale'])
        assert graph == {'sale': ['product'], 'product': ['base'],
                         'base': ['sale']}


class TestExclusion:
    """≙ ``ir.module.module.exclusion`` (``odoo19c: ir_module.py:1065-1102``)."""

    def test_the_name_resolves_to_the_excluded_module(self, catalogue):
        excl = IrModuleExclusion.objects.create(
            module=catalogue['sale'], name='product')
        assert excl._compute_exclusion() == catalogue['product']

    def test_an_absent_name_resolves_to_none_and_the_state_is_unknown(
            self, catalogue):
        excl = IrModuleExclusion.objects.create(
            module=catalogue['sale'], name='addon_que_no_esta')
        assert excl._compute_exclusion() is None
        assert excl._compute_state() == 'unknown'

    def test_the_state_is_that_of_the_excluded_module(self, catalogue):
        excl = IrModuleExclusion.objects.create(
            module=catalogue['sale'], name='base')
        assert excl._compute_state() == 'installed'

    def test_the_search_finds_the_edges_that_exclude_a_module(self, catalogue):
        IrModuleExclusion.objects.create(
            module=catalogue['sale'], name='product')
        found = IrModuleExclusion._search_exclusion([catalogue['product']])
        assert [edge.name for edge in found] == ['product']

    def test_the_search_of_a_module_nobody_excludes_yields_nothing(
            self, catalogue):
        IrModuleExclusion.objects.create(
            module=catalogue['sale'], name='product')
        assert not IrModuleExclusion._search_exclusion([catalogue['base']])

    def test_the_same_pair_cannot_be_declared_twice(self, catalogue):
        """``unique_together``, igual que en la dependencia: una arista es un
        hecho, no una cuenta.
        """
        IrModuleExclusion.objects.create(
            module=catalogue['sale'], name='product')
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                IrModuleExclusion.objects.create(
                    module=catalogue['sale'], name='product')


class TestWalkDependencies:
    """≙ ``downstream_dependencies`` / ``upstream_dependencies``
    (``odoo19c: ir_module.py:531-580``).
    """

    def test_upstream_reaches_the_transitive_dependency(self, catalogue):
        """``sale`` no declara ``base``; lo alcanza por ``product``.

        Los dos están ``installed``, así que se excluyen por el default. El
        caso pasa ``()`` para medir el recorrido y no el filtro — son dos
        cosas distintas y el caso siguiente mide la otra.
        """
        reached = catalogue['sale'].upstream_dependencies(exclude_states=())
        assert {module.name for module in reached} == {'product', 'base'}

    def test_upstream_excludes_what_is_already_installed(self, catalogue):
        """El default de la fuente: lo instalado no hace falta traerlo.

        Con los tres addons instalados el resultado es vacío; sin el filtro
        serían dos. Sin este caso, un recorrido que ignorara ``exclude_states``
        pasaría el anterior.
        """
        assert not catalogue['sale'].upstream_dependencies()

    def test_downstream_reaches_who_depends_on_me(self, catalogue):
        reached = catalogue['base'].downstream_dependencies(exclude_states=())
        assert {module.name for module in reached} == {'product', 'sale'}

    def test_downstream_excludes_what_is_not_installed(self, catalogue):
        """El default simétrico: ``sale`` está ``uninstalled`` y cae.

        ``product`` sobrevive porque está instalado. El caso fija los dos
        lados: si el filtro no se aplicara habría dos, si se aplicara de más
        habría cero.
        """
        reached = catalogue['base'].downstream_dependencies()
        assert {module.name for module in reached} == {'product'}

    def test_a_module_never_reaches_itself(self, catalogue):
        """La marca de visitado incluye al origen.

        Sin ella, un ciclo devolvería el propio módulo como su dependencia, que
        no es un hecho del grafo sino un artefacto del recorrido.
        """
        IrModuleDependency.objects.create(
            module=catalogue['base'], name='sale')
        reached = catalogue['sale'].upstream_dependencies(exclude_states=())
        assert catalogue['sale'] not in reached
        assert {module.name for module in reached} == {'product', 'base'}

    def test_a_cycle_terminates_in_both_directions(self, catalogue):
        """Igual que ``all_dependencies``: sin marca de visitado esto cuelga,
        no falla. Es el control que separa grafo de árbol.
        """
        IrModuleDependency.objects.create(
            module=catalogue['base'], name='sale')
        assert catalogue['product'].upstream_dependencies(exclude_states=())
        assert catalogue['product'].downstream_dependencies(exclude_states=())

    def test_an_isolated_module_reaches_nothing(self, catalogue):
        """CONTROL de la dirección contraria — sin él, un recorrido que
        devolviera SIEMPRE todo el catálogo pasaría los demás.
        """
        lonely = IrModule.objects.create(name='addon_aislado')
        assert not lonely.upstream_dependencies(exclude_states=())
        assert not lonely.downstream_dependencies(exclude_states=())
