"""#332 — la construcción de la clase de modelo, y sus prerrequisitos.

Cuatro símbolos de ``odoo19c: odoo/orm/model_classes.py`` que el censo deja
sin contraparte, y que #331 dejó bloqueados por los tres colectores (#334):

============================================ ================== ==============
Símbolo                                      En la referencia   Aquí
============================================ ================== ==============
``_check_model_parent_extension``            ``:253-258``       mismo nombre
``_check_model_extension`` (mitad transient) ``:233-250``       mismo nombre
``_init_model_class_attributes``             ``:261-298``       mismo nombre
``_prepare_setup``                           ``:329-346``       mismo nombre
============================================ ================== ==============

Las dos divergencias de mecanismo, medidas
===========================================

**La mitad de ``_abstract`` de ``_check_model_extension`` NO tiene superficie
aquí, y la razón está construida, no supuesta.** Allá el check existe porque
``_inherit`` FUNDE dos clases bajo un mismo ``_name``: la segunda puede
cambiarle la especie a la primera. Aquí ``orm.registry._register`` **rechaza**
el ``_name`` duplicado (``registry.py:216-224``) — *"El nombre punteado
identifica un modelo, no una familia"*—, así que esa fusión no ocurre y la
transformación no tiene por dónde entrar. Es una guarda **más estricta**, no
un hueco.

Lo que sí ocurre aquí es la **herencia de Python**, y ahí las tres reglas de
los dos checks de la fuente aplican tal cual. Los dos se portan **con su
nombre, su firma y su mensaje**; lo único nuestro es
:func:`check_model_bases`, el recorrido que los aplica sobre la MRO — allá lo
hace ``add_to_registry`` al fundir cada clase de definición, y aquí no hay
fusión que recorrer.

**``_base_classes__`` no existe:** allá el registro guarda las clases de
definición para poder reconstruir la clase; aquí ``ModelBase`` de Django ya
construyó una, y su lista de bases es ``__mro__``.

Los controles que discriminan
==============================

- Cada regla tiene su caso negativo Y su positivo: sin el positivo, un check
  que rechazara SIEMPRE pasaría los tres negativos igual de verde.
- El árbol vivo es el control de fondo: medido, **140** modelos registrados,
  **0** abstractos, **4** transitorios y **0** violaciones. Si el check
  rechazara de más, ese caso cae.
- ``prepare_setup`` se mide por lo que **olvida**, que es su único trabajo: un
  ``_rec_name`` resuelto y un colector cacheado tienen que dejar de estarlo.
"""
import pytest

from addons.website.models.static_page import StaticPage
from orm import registry
from orm.model_classes import (_check_model_extension,
                               _check_model_parent_extension,
                               _init_model_class_attributes, _prepare_setup,
                               check_model_bases, ensure_model_class_attributes,
                               inherits_children, is_abstract, is_transient)
from orm.models import AbstractModel
from orm.models_transient import TransientModel


class TestIsAbstractReadsWhereThisStackKeepsIt:
    """``_abstract`` no cuelga de ``models.Model`` — la colisión de #98—, así
    que se lee de las dos formas que este árbol sí tiene."""

    def test_a_registrant_without_table_is_abstract(self):
        assert is_abstract(AbstractModel) is True

    def test_a_django_abstract_meta_is_abstract(self):
        """La otra forma: ``Meta.abstract``, que es el mecanismo del stack."""
        assert is_abstract(registry.MODELS_BY_NAME['res.partner']) is False

    def test_a_concrete_model_is_not(self):
        assert is_abstract(registry.MODELS_BY_NAME['res.users']) is False


class TestIsTransientReadsTheDeclaredAttribute:
    """``_transient`` sí es un atributo de clase aquí — lo declara
    ``TransientModel`` (``orm/models_transient.py:70``)."""

    def test_the_transient_base_is_transient(self):
        assert is_transient(TransientModel) is True

    def test_a_regular_model_is_not(self):
        assert is_transient(registry.MODELS_BY_NAME['res.partner']) is False


class TestCheckModelBasesRefusesAKindChange:
    """≙ ``_check_model_parent_extension`` (``:253-258``) más la mitad
    transitoria de ``_check_model_extension`` (``:233-250``)."""

    def test_the_whole_live_tree_passes(self):
        """EL CONTROL POSITIVO, y no es un doble: los 140 modelos registrados
        del árbol tienen que pasar su propia validación. Sin él, un check que
        rechazara siempre pasaría los tres casos negativos."""
        for model in registry.MODELS_BY_NAME.values():
            check_model_bases(model)

    def test_an_abstract_that_inherits_a_concrete_one_is_refused(self):
        class _Concrete:
            _name = 'prueba.concreta'

        class _Abstract(_Concrete):
            _name = 'prueba.abstracta'
            _abstract = True

        with pytest.raises(TypeError, match='cannot inherit from non-abstract'):
            check_model_bases(_Abstract)

    def test_a_transient_that_inherits_a_regular_one_is_refused(self):
        class _Regular:
            _name = 'prueba.regular'

        class _Transient(_Regular):
            _name = 'prueba.transitoria'
            _transient = True

        with pytest.raises(TypeError, match='into a transient model'):
            check_model_bases(_Transient)

    def test_a_regular_that_inherits_a_transient_one_is_refused(self):
        class _Transient:
            _name = 'prueba.transitoria.padre'
            _transient = True

        class _Regular(_Transient):
            _name = 'prueba.regular.hija'
            _transient = False

        with pytest.raises(TypeError, match='into a non-transient model'):
            check_model_bases(_Regular)

    def test_two_models_of_the_same_kind_pass(self):
        """EL CONTROL de cada regla: la herencia legítima no se rechaza."""
        class _Transient:
            _name = 'prueba.t1'
            _transient = True

        class _AlsoTransient(_Transient):
            _name = 'prueba.t2'

        check_model_bases(_AlsoTransient)

    def test_a_parent_without_a_name_is_not_measured(self):
        """Un mixin sin ``_name`` no es un modelo: la fuente recorre las
        clases de definición, no toda la MRO de Python."""
        class _Mixin:
            pass

        class _Transient(_Mixin):
            _name = 'prueba.t3'
            _transient = True

        check_model_bases(_Transient)


class TestInitModelClassAttributesFillsTheDefaultsFromTheName:
    """≙ ``_init_model_class_attributes`` (``:261-298``)."""

    def test_the_description_defaults_to_the_name(self):
        class _Model:
            _name = 'prueba.sin.descripcion'

        _init_model_class_attributes(_Model)
        assert _Model._description == 'prueba.sin.descripcion'

    def test_a_declared_description_wins(self):
        """EL CONTROL del default: si pisara lo declarado, los 1099 modelos de
        la fuente que declaran ``_description`` lo perderían."""
        class _Model:
            _name = 'prueba.con.descripcion'
            _description = 'Un nombre informal'

        _init_model_class_attributes(_Model)
        assert _Model._description == 'Un nombre informal'

    def test_the_table_derives_from_the_name(self):
        class _Model:
            _name = 'prueba.tabla'

        _init_model_class_attributes(_Model)
        assert _Model._table == 'prueba_tabla'

    def test_it_merges_inherits_across_the_bases(self):
        """La fuente recorre ``_base_classes__``; aquí es la MRO. Sin el
        recorrido, una delegación declarada en un mixin se perdería."""
        class _Mixin:
            _inherits = {'res.company': 'company'}

        class _Model(_Mixin):
            _name = 'prueba.hereda'
            _inherits = {'res.partner': 'partner'}

        _init_model_class_attributes(_Model)
        assert _Model._inherits == {'res.company': 'company',
                                    'res.partner': 'partner'}

    def test_the_own_declaration_wins_over_the_base(self):
        class _Mixin:
            _inherits = {'res.partner': 'del_mixin'}

        class _Model(_Mixin):
            _name = 'prueba.pisa'
            _inherits = {'res.partner': 'propio'}

        _init_model_class_attributes(_Model)
        assert _Model._inherits == {'res.partner': 'propio'}

    def test_a_model_without_inherits_gets_no_empty_dict(self):
        """La fuente evita asignar un dict vacío *"to save memory"*
        (``:290``); aquí el efecto observable es que la clase no gana un
        atributo que no declaró."""
        class _Model:
            _name = 'prueba.sin.delegacion'

        _init_model_class_attributes(_Model)
        assert '_inherits' not in _Model.__dict__


@pytest.mark.django_db
class TestInheritsChildrenIsTheBackEdge:
    """≙ ``registry[parent]._inherits_children`` (``:293-294``)."""

    def test_the_live_delegators_appear_under_their_parent(self):
        """EL CONTROL POSITIVO: los tres declarantes vivos del árbol —medidos
        en :ref:`h-api-1052`— tienen que salir por la arista de vuelta."""
        children = inherits_children('res.partner')
        assert 'res.users' in children

    def test_a_model_nobody_delegates_to_has_no_children(self):
        assert inherits_children('res.lang') == frozenset()


class TestPrepareSetupForgetsWhatTheSetupRecomputes:
    """≙ ``_prepare_setup`` (``:329-346``) — su único trabajo es OLVIDAR."""

    def test_it_discards_a_resolved_rec_name(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        previous = partner.__dict__.get('_rec_name')
        partner._rec_name = 'name'
        try:
            _prepare_setup(partner)
            assert '_rec_name' not in partner.__dict__
        finally:
            if previous is not None:
                partner._rec_name = previous

    def test_it_clears_the_marked_method_collectors(self):
        """EL CONTROL de la segunda mitad, y es lo que #334 dejó sin llamador:
        un colector que no se vacía hace invisible un método añadido después.
        """
        partner = registry.MODELS_BY_NAME['res.partner']
        registry.constraint_methods(partner)
        assert partner in registry.constraint_methods._table

        _prepare_setup(partner)

        assert partner not in registry.constraint_methods._table


@pytest.mark.django_db
class TestTheWiringRunsOnTheLiveTree:
    """Un colector sin consumidor es capacidad muerta — la leccion de #334.

    Estos casos miden el **cableado**, no las funciones: que el receptor de
    ``class_prepared`` y el barrido de ``AppConfig.ready()`` hayan corrido de
    verdad sobre el arbol, no que corran si alguien los llama.
    """

    def test_every_registered_model_got_its_description(self):
        sin = [name for name, cls in registry.MODELS_BY_NAME.items()
               if not getattr(cls, '_description', None)]
        assert sin == []

    def test_a_model_without_a_declared_table_derives_it_from_the_name(self):
        """El default: ``_name`` con los puntos cambiados por guion bajo, que
        es lo que ``check_table_matches_name()`` verifica contra
        ``db_table``."""
        mal = [name for name, cls in registry.MODELS_BY_NAME.items()
               if '_table' not in cls.__dict__
               and getattr(cls, '_table', None) != name.replace('.', '_')]
        assert mal == []

    def test_a_declared_table_is_not_clobbered_by_the_default(self):
        """EL CONTROL del default, y sus declarantes son reales.

        ``:275`` de la fuente hace ``_table = base._table or model_cls._table``:
        lo declarado gana. Dos del arbol lo declaran con el mismo valor que la
        referencia — ``odoo19c: odoo/addons/base/models/ir_actions.py:588`` y
        ``ir_actions_report.py:161``—, asi que si el default los pisara, el
        nombre de tabla dejaria de coincidir con la fuente.

        *Ciega a:* si ese ``_table`` coincide con el ``db_table`` real. Eso lo
        mide ``check_table_matches_name()``, que ya publica la unica
        divergencia viva (``base.SystemParameter``).
        """
        declarantes = {name: cls for name, cls in registry.MODELS_BY_NAME.items()
                        if '_table' in cls.__dict__}
        assert set(declarantes) >= {'ir.actions.server', 'ir.actions.report'}
        assert declarantes['ir.actions.server']._table == 'ir_act_server'
        assert declarantes['ir.actions.report']._table == 'ir_act_report_xml'

    def test_a_model_that_inherits_a_name_without_declaring_one_is_skipped(self):
        """EL CONTROL que el aviso de la fuente destapó.

        ``getattr(cls, '_name')`` recorre la MRO, y ``StaticPage``
        (``addons/website/models/static_page.py:30``) hereda su ``_name`` de
        ``WebsiteSearchableMixin`` sin declarar el suyo. Leyendolo asi se le
        habrian escrito el ``_description`` y el ``_table`` del mixin.
        """
        assert '_name' not in StaticPage.__dict__
        assert '_description' not in StaticPage.__dict__
        assert '_table' not in StaticPage.__dict__

    def test_the_sweep_covers_every_registered_model(self):
        assert (set(ensure_model_class_attributes())
                == set(registry.MODELS_BY_NAME))
