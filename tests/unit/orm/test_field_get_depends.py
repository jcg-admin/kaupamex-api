"""``Field.get_depends`` — el PRODUCTOR del mapa de dependencias (tarea #211).

Porta ``Field.get_depends`` (``odoo19c: odoo/orm/fields.py:561-598``) —
*"Return the field's dependencies and cache dependencies"*.

**Por que no lo cubria ``resolve_depends``.** Los dos simbolos son
complementarios, no duplicados: ``get_depends`` **produce** el par
``(depends, depends_context)`` a partir de lo que la clase declara, y
``resolve_depends`` **consume** ese par expandiendo cada nombre punteado a las
tuplas de campos que lo recorren. Aqui el mapa que ``resolve_depends`` lee
—``registry_module.field_depends``— lo poblaba ``_DerivedCollector('_depends')``
leyendo el atributo **en crudo**, asi que dos de las tres ramas de la fuente no
existian:

- la rama ``related``: un campo relacionado deriva ``[self.related]`` como su
  dependencia, y su contexto recorriendo la cadena punteada campo por campo;
- la rama de ``compute`` por **MRO**: la fuente junta el ``_depends`` de
  **todas** las funciones sobreescritas (``resolve_mro``), no el de la unica
  que ``getattr(model, compute)`` devuelve.

**El control que discrimina** (``metrica-decide-la-conclusion.md``, sub-patron
D) es ``test_a_compute_overridden_in_a_subclass_accumulates_both``: la version
anterior —un solo ``getattr``— pasa todos los demas casos y **falla exactamente
ese**, porque un ``getattr`` devuelve la funcion mas derivada y pierde la de la
base. Sin ese caso el verde no distinguiria «junta el MRO» de «lee una sola».
"""
import pytest
from django.db import models

from orm import registry
from orm.fields import get_depends
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry


@pytest.fixture
def users(db):
    return MODELS_BY_NAME['res.users']


def _field(**attrs):
    """Un campo suelto con los atributos que ``get_depends`` consulta.

    Se construye en vez de buscarse: la fuente decide por ``_depends``,
    ``related`` y ``compute``, y ningun campo del arbol combina hoy las tres
    ramas. Es ``models.CharField`` porque ``get_depends`` cuelga de
    ``models.Field`` y no mira el tipo.
    """
    field = models.CharField(max_length=8)
    for name, value in {'_depends': None, '_depends_context': None,
                        'related': None, 'compute': None, **attrs}.items():
        setattr(field, name, value)
    return field


class TestTheExplicitDependsWins:
    """≙ ``:563-565`` — *"the parameter 'depends' has priority over 'depends'
    on compute"*."""

    def test_an_explicit_depends_shadows_the_compute(self, users, monkeypatch):
        def _compute(self):
            pass
        _compute._depends = ('ignored',)
        monkeypatch.setattr(users, '_compute_for_the_test', _compute,
                            raising=False)
        field = _field(_depends=('own',), compute='_compute_for_the_test')

        assert field.get_depends(users) == (('own',), ())

    def test_an_explicit_depends_carries_its_context(self, users):
        field = _field(_depends=('own',), _depends_context=('company',))

        assert field.get_depends(users) == (('own',), ('company',))


class TestTheRelatedBranch:
    """≙ ``:567-580`` — la dependencia de un campo relacionado ES su ruta."""

    def test_the_related_path_is_the_dependency(self, users):
        field = _field(related='partner.name')

        depends, _ = field.get_depends(users)

        assert depends == ['partner.name']

    def test_an_explicit_context_short_circuits_the_walk(self, users):
        field = _field(related='partner.name', _depends_context=('lang',))

        assert field.get_depends(users) == (['partner.name'], ('lang',))

    def test_the_walked_context_gathers_the_chain(self, users, monkeypatch):
        """El contexto sale de recorrer la cadena, no del campo relacionado.

        Sin la rama, el contexto de ``partner_id`` se pierde: es el eslabon
        intermedio, y sus dependencias de contexto son las que hacen que el
        valor calculado dependa de quien lo mira.
        """
        link = model_field_registry(users)['partner']
        monkeypatch.setattr(link, '_depends_context', ('company',),
                            raising=False)
        field = _field(related='partner.name')

        assert field.get_depends(users) == (['partner.name'], ('company',))


class TestTheComputeBranch:
    """≙ ``:585-597`` — ``resolve_mro`` sobre la funcion de calculo."""

    def test_a_compute_contributes_its_depends(self, users, monkeypatch):
        def _compute(self):
            pass
        _compute._depends = ('label',)
        monkeypatch.setattr(users, '_compute_for_the_test', _compute,
                            raising=False)
        field = _field(compute='_compute_for_the_test')

        assert field.get_depends(users) == (['label'], [])

    def test_a_callable_depends_is_called_with_the_model(self, users, monkeypatch):
        """≙ ``:594`` — ``deps(model) if callable(deps) else deps``."""
        def _compute(self):
            pass
        _compute._depends = lambda model: ['from_%s' % model.__name__.lower()]
        monkeypatch.setattr(users, '_compute_for_the_test', _compute,
                            raising=False)
        field = _field(compute='_compute_for_the_test')

        depends, _ = field.get_depends(users)

        assert depends == ['from_resusers']

    def test_a_callable_compute_is_used_as_is(self, users):
        """≙ ``:589-590`` — un ``compute`` que ya es funcion no pasa por MRO."""
        def _compute(self):
            pass
        _compute._depends = ('direct',)
        field = _field(compute=_compute)

        assert field.get_depends(users) == (['direct'], [])

    def test_a_compute_overridden_in_a_subclass_accumulates_both(self):
        """EL CONTROL: ``getattr`` devuelve UNA funcion; ``resolve_mro``, todas.

        Una implementacion que lea ``getattr(model, compute)._depends`` pasa
        todos los casos de arriba y falla este, porque el ``_depends`` de la
        base queda fuera. Ese es el defecto que el colector tenia.

        Los casos de arriba instalan su computo con ``monkeypatch`` y no por
        asignacion: mutar ``res.users`` deja el atributo puesto, y el recorrido
        del MRO —que es correcto— lo recogeria tambien desde aqui. El escape
        se midio: la tercera dependencia que aparecia era la del caso invocable
        anterior, no un defecto del porte.

        Las dos clases son **llanas, no modelos de Django**. ``resolve_mro``
        recorre el ``__mro__`` y no consulta el registro de apps, asi que un
        modelo real no aporta nada y **si** contamina: declarado dentro del
        caso, queda registrado para toda la sesion y el barrido de system
        checks lo rechaza por ``models.E023`` (el nombre empieza con guion
        bajo). Se midio: dos errores en
        ``test_run_checks_or_raise_passes_clean_tree``.
        """
        class Base:
            def compute_for_the_test(self):
                pass
            compute_for_the_test._depends = ('from_base',)

        class Derived(Base):
            def compute_for_the_test(self):
                pass
            compute_for_the_test._depends = ('from_derived',)

        field = _field(compute='compute_for_the_test')

        depends, _ = field.get_depends(Derived)

        assert set(depends) == {'from_derived', 'from_base'}


class TestTheEmptyCase:
    """≙ ``:582-583`` — sin ``compute`` la respuesta es vacia, no un error."""

    def test_a_plain_field_depends_on_nothing(self, users):
        assert _field().get_depends(users) == ((), ())

    def test_a_plain_field_keeps_its_declared_context(self, users):
        assert _field(_depends_context=('tz',)).get_depends(users) == ((), ('tz',))


class TestTheCollectorConsumesTheProducer:
    """El cableado: el mapa que ``resolve_depends`` lee sale de ``get_depends``.

    Sin este caso el metodo existiria y el mapa seguiria derivandose del
    atributo en crudo — un porte que compila y no se invoca, la misma frontera
    que ``TestDomainRoutesThroughTheFacade`` cubre para la condicion.
    """

    def test_the_producer_is_exposed_as_a_field_method(self):
        assert models.Field.get_depends is get_depends

    def test_the_collector_asks_the_field(self, users, monkeypatch):
        login = model_field_registry(users)['login']
        monkeypatch.setattr(login, 'related', 'partner.name', raising=False)
        registry.field_depends.clear()

        assert registry.field_depends[login] == ('partner.name',)
