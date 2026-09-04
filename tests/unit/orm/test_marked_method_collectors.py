"""#334 — los tres colectores de método marcado, y quién los consume.

``_prepare_setup`` (``odoo19c: odoo/orm/model_classes.py:344-346``) resetea
tres propiedades memoizadas que aquí no existían. Portarlas es portar también
a su consumidor: un colector sin consumidor es capacidad muerta.

=========================== ========================= =========================
Colector                    En la referencia           Su consumidor allá
=========================== ========================= =========================
``constraint_methods``      ``models.py:519-546``      ``_validate_fields`` :1252
``ondelete_methods``        ``models.py:548-558``      ``unlink``           :4206
``onchange_methods``        ``models.py:560-593``      ``_apply_onchange``  :6979
=========================== ========================= =========================

Los tres son ``@property`` sobre ``BaseModel`` que memoizan en la clase. Aquí
``BaseModel`` es el ``Model`` de Django y no admite atributos nuestros (la
colisión que barre #98), así que el hogar es un colector de módulo con la
forma que el árbol ya tiene para ``@api.depends``: ``_DerivedCollector`` de
``orm/registry.py`` — derivado, cacheado y con ``clear()``, que es justo el
reset que ``_prepare_setup`` hace.

Los controles que discriminan
==============================

- Cada colector se mide con el marcador **presente y ausente**: un método sin
  marcar no entra, y el mapa de un modelo sin métodos marcados es vacío.
- ``_validate_fields`` filtra por nombre de campo en los dos sentidos —los que
  se tocaron y los excluidos—; hay un caso por cada filtro.
- La forma **invocable** de ``@api.constrains`` tiene su caso: sin él, el
  ``if callable(...)`` del colector queda verde con la rama anulada — medido
  en ``scripts/evidence/neutering-334-constrains-callable-sin-resolver-*.txt``,
  que es lo que destapó su ausencia.
- El control positivo NO es un doble: ``_check_won_validity``
  (``addons/crm/models/crm_lead.py:557``) está declarado con
  ``@api.constrains`` y **medido sin ningún llamador**. Que el colector lo vea
  es lo que prueba que el marcador dejó de ser decorativo.
"""
import pytest

from orm import registry
from orm.decorators import constrains, ondelete, onchange
from orm.registry import (constraint_methods, ondelete_methods,
                          onchange_methods)


class _Marked:
    """Un modelo de mentira con los tres marcadores, para medir el colector
    sin depender de qué declare hoy un modelo real."""

    _name = 'prueba.marcada'

    @constrains('alpha', 'beta')
    def _check_alpha(self):
        return 'alpha'

    @constrains('beta')
    def _check_beta(self):
        return 'beta'

    @ondelete(at_uninstall=False)
    def _unlink_if_alpha(self):
        return 'unlink'

    @ondelete(at_uninstall=True)
    def _unlink_if_beta(self):
        return 'unlink-uninstall'

    @onchange('alpha')
    def _onchange_alpha(self):
        return 'onchange'

    def _sin_marcar(self):
        return 'nada'


class _Bare:
    """EL CONTROL NEGATIVO: ningún método marcado."""

    _name = 'prueba.pelada'

    def _sin_marcar(self):
        return 'nada'


class _MarkedWithCallable:
    """Un modelo con la forma **invocable** de ``@api.constrains``.

    ``odoo19c`` la usa en **5** sitios, uno en ``base``
    (``res_company.py:426``); aquí ninguno todavía, así que este doble es su
    único ejerciente hasta que se porte aquel.
    """

    _name = 'prueba.invocable'

    _fields = {}

    def _names_to_watch(self):
        return ['gamma', 'delta']

    @constrains(lambda self: self._names_to_watch())
    def _check_gamma(self):
        return 'gamma'


class TestTheCallableFormIsResolvedWithoutDestroyingIt:
    """≙ el ``wrap`` de la fuente (``odoo19c: odoo/orm/models.py:526-532``)."""

    def _collect(self):
        registry.clear_marked_methods()
        return constraint_methods(_MarkedWithCallable)

    def test_the_resolved_names_come_from_calling_it(self):
        assert self._collect()[0]._constrains == ('gamma', 'delta')

    def test_the_original_keeps_its_callable(self):
        """EL CONTROL que discrimina envolver de sobreescribir.

        Sobreescribir ``func._constrains`` resuelve igual la primera vez y
        **destruye** el invocable: tras un ``clear_marked_methods`` el método
        ya sólo tendría la tupla de aquella vez. La fuente re-resuelve en cada
        reconstrucción porque nunca toca el original.
        """
        self._collect()
        declared = _MarkedWithCallable.__dict__['_check_gamma']._constrains
        assert callable(declared)

    def test_it_re_resolves_after_the_reset(self):
        """Y por eso un cambio de estado se ve en la siguiente pasada."""
        assert self._collect()[0]._constrains == ('gamma', 'delta')
        original = _MarkedWithCallable._names_to_watch
        _MarkedWithCallable._names_to_watch = lambda self: ['epsilon']
        try:
            assert self._collect()[0]._constrains == ('epsilon',)
        finally:
            _MarkedWithCallable._names_to_watch = original
            registry.clear_marked_methods()

    def test_the_wrapper_still_calls_the_original(self):
        """El proxy no es un envoltorio vacío: delega."""
        assert self._collect()[0](_MarkedWithCallable()) == 'gamma'


class TestItWarnsAboutADeclaredNameThatIsNotAWriteableField:
    """≙ los dos avisos de la fuente (``models.py:539-542``).

    Sin ellos un ``@api.constrains('nombre_con_errata')`` queda mudo: el
    método nunca corre y nada lo dice.

    Se miden sobre un modelo **real**, no sobre un doble: el aviso compara
    contra ``_fields``, que sale de ``_meta``, y una clase suelta no tiene
    ninguno de los dos.
    """

    def _collect_with(self, method_name, method, caplog):
        model = registry.MODELS_BY_NAME['res.partner']
        setattr(model, method_name, method)
        registry.clear_marked_methods()
        try:
            with caplog.at_level('WARNING', logger='kaupamex.registry'):
                constraint_methods(model)
        finally:
            delattr(model, method_name)
            registry.clear_marked_methods()

    def test_a_name_that_is_not_a_field_warns(self, caplog):
        @constrains('campo_con_errata')
        def _check_typo(self):
            return None

        self._collect_with('_check_typo', _check_typo, caplog)

        assert 'is not a field name' in caplog.text

    def test_the_warning_names_the_model_the_method_and_the_field(self, caplog):
        """EL CONTROL de que el aviso sirva: sin las tres piezas no localiza
        la errata, que es para lo único que existe."""
        @constrains('campo_con_errata')
        def _check_typo(self):
            return None

        self._collect_with('_check_typo', _check_typo, caplog)

        assert 'res.partner' in caplog.text
        assert '_check_typo' in caplog.text
        assert "'campo_con_errata'" in caplog.text

    def test_a_real_field_does_not_warn(self, caplog):
        """EL CONTROL POSITIVO: sin él, un aviso que se emitiera SIEMPRE
        pasaría los dos casos de arriba igual de verde."""
        @constrains('name')
        def _check_name(self):
            return None

        self._collect_with('_check_name', _check_name, caplog)

        assert 'is not a field name' not in caplog.text


class TestConstraintMethodsCollectsTheMarkedOnes:
    """≙ ``_constraint_methods`` (``odoo19c: odoo/orm/models.py:519-546``) —
    «Return a list of methods implementing Python constraints»."""

    def test_it_finds_both_marked_methods(self):
        names = {m.__name__ for m in constraint_methods(_Marked)}
        assert names == {'_check_alpha', '_check_beta'}

    def test_an_unmarked_method_stays_out(self):
        names = {m.__name__ for m in constraint_methods(_Marked)}
        assert '_sin_marcar' not in names

    def test_a_model_without_markers_gives_the_empty_tuple(self):
        assert constraint_methods(_Bare) == ()

    def test_each_method_keeps_its_declared_field_names(self):
        by_name = {m.__name__: m for m in constraint_methods(_Marked)}
        assert by_name['_check_alpha']._constrains == ('alpha', 'beta')
        assert by_name['_check_beta']._constrains == ('beta',)


class TestOndeleteMethodsCollectsTheMarkedOnes:
    """≙ ``_ondelete_methods`` (``models.py:548-558``) — «Return a list of
    methods implementing checks before unlinking»."""

    def test_it_finds_both_marked_methods(self):
        names = {m.__name__ for m in ondelete_methods(_Marked)}
        assert names == {'_unlink_if_alpha', '_unlink_if_beta'}

    def test_a_model_without_markers_gives_the_empty_tuple(self):
        assert ondelete_methods(_Bare) == ()

    def test_the_at_uninstall_flag_survives_the_collection(self):
        """La fuente lo lee en ``unlink`` (``:4207``) para decidir si el
        método corre tambien al desinstalar el modulo."""
        by_name = {m.__name__: m for m in ondelete_methods(_Marked)}
        assert by_name['_unlink_if_alpha']._ondelete is False
        assert by_name['_unlink_if_beta']._ondelete is True


class TestOnchangeMethodsMapsFieldNameToMethod:
    """≙ ``_onchange_methods`` (``models.py:560-593``) — «Return a dictionary
    mapping field names to onchange methods»."""

    def test_the_field_name_keys_the_map(self):
        mapa = onchange_methods(_Marked)
        assert [m.__name__ for m in mapa['alpha']] == ['_onchange_alpha']

    def test_a_field_without_method_is_absent(self):
        assert 'beta' not in onchange_methods(_Marked)

    def test_a_model_without_markers_gives_the_empty_map(self):
        assert onchange_methods(_Bare) == {}


class TestTheCollectorsAreDerivedAndClearable:
    """El reset de ``_prepare_setup`` (``model_classes.py:344-346``): allá se
    reasigna la ``@property`` de ``BaseModel`` sobre la clase; aquí el mapa es
    derivado y se invalida."""

    def test_clearing_makes_the_next_read_see_a_method_added_after(self):
        assert '_check_gamma' not in {
            m.__name__ for m in constraint_methods(_Marked)}

        @constrains('gamma')
        def _check_gamma(self):
            return 'gamma'

        _Marked._check_gamma = _check_gamma
        try:
            registry.clear_marked_methods()
            assert '_check_gamma' in {
                m.__name__ for m in constraint_methods(_Marked)}
        finally:
            del _Marked._check_gamma
            registry.clear_marked_methods()


@pytest.mark.django_db
class TestValidateFieldsRunsOnlyTheAffectedConstraints:
    """≙ ``_validate_fields`` (``odoo19c: odoo/orm/models.py:1252-1268``) —
    «Invoke the constraint methods for which at least one field name is in
    ``field_names`` and none is in ``excluded_names``»."""

    def test_a_constraint_that_names_a_touched_field_runs(self):
        runs = []
        model, restore = _with_constraint(runs)
        try:
            model()._validate_fields(['name'])
            assert runs == ['_check_probe']
        finally:
            restore()

    def test_a_constraint_that_names_no_touched_field_stays_quiet(self):
        """EL CONTROL del primer filtro."""
        runs = []
        model, restore = _with_constraint(runs)
        try:
            model()._validate_fields(['active'])
            assert runs == []
        finally:
            restore()

    def test_an_excluded_field_vetoes_the_constraint(self):
        """EL CONTROL del segundo filtro: la fuente exige que NINGUNO de los
        nombres declarados este excluido."""
        runs = []
        model, restore = _with_constraint(runs)
        try:
            model()._validate_fields(['name'], excluded_names=['comment'])
            assert runs == []
        finally:
            restore()

    def test_a_model_without_constraints_does_nothing(self):
        partner = registry.MODELS_BY_NAME['res.partner']
        assert partner()._validate_fields(['name']) is None


def _with_constraint(runs):
    """Cuelga un ``@api.constrains`` sobre ``res.partner`` y devuelve cómo
    retirarlo. Se usa el modelo real —no un doble— porque lo que se mide es el
    método que el ORM le adjunta, y los dos nombres declarados son campos
    reales suyos: con nombres inventados el ayudante dispararía el aviso de
    ``is not a field name``, que es ruido sobre un caso que no mide eso."""
    partner = registry.MODELS_BY_NAME['res.partner']

    @constrains('name', 'comment')
    def _check_probe(self):
        runs.append('_check_probe')

    partner._check_probe = _check_probe
    registry.clear_marked_methods()

    def restore():
        del partner._check_probe
        registry.clear_marked_methods()

    return partner, restore


@pytest.mark.django_db
class TestTheLiveDeclarantIsSeenByTheCollector:
    """EL CONTROL POSITIVO, y no es un doble."""

    def test_the_crm_constraint_without_a_caller_is_collected(self):
        """``_check_won_validity`` (``addons/crm/models/crm_lead.py:557``)
        estaba declarado con ``@api.constrains`` y medido **sin ningun
        llamador**. Que el colector lo vea es lo que prueba que el marcador
        dejo de ser decorativo."""
        lead = registry.MODELS_BY_NAME['crm.lead']
        names = {m.__name__ for m in constraint_methods(lead)}
        assert '_check_won_validity' in names
