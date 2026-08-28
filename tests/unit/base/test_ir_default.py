"""Contrato de ``IrDefault`` (``ir.default``) — portación fiel de Odoo,
iniciativa ``adaptar-familias-odoo-monolito-modular`` (SOL-096, H-BASE-01 C-2,
ÚLTIMO ítem del backlog de control núcleo ``ir.*``).

Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- ``db_table``/``app_label`` fieles a Odoo (``ir_default`` / ``base``),
- campos faithful presentes,
- ``set_default``/``get_default``: round-trip de codificación/decodificación
  JSON (dict, int, string),
- precedencia: ``user`` NULL = global; un default específico de usuario
  prevalece sobre el global para ese usuario (ver docstring de
  ``ir_default.py`` sobre el drift de orden de ``NULL`` Postgres/MariaDB),
- alcance de empresa (``company``),
- unicidad: volver a ``set_default`` sobre el mismo alcance reemplaza, no
  duplica.

Toca DB → django_db.
"""
import pytest

from addons.base.models import IrDefault
from orm import registry
from tools.cache import ormcache
from addons.base.models import ResCompany
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrDefault.__module__ == 'addons.base.models.ir_default'


# --- db_table / app_label fieles a Odoo ------------------------------------

def test_db_table_matches_reference():
    assert IrDefault._meta.db_table == 'ir_default'
    assert IrDefault._meta.app_label == 'base'


def test_campos_faithful_presentes():
    field_names = {f.name for f in IrDefault._meta.get_fields()}
    for expected in (
        'model', 'field', 'user', 'company', 'condition', 'json_value',
    ):
        assert expected in field_names, f'falta el campo {expected!r}'


# --- set_default / get_default: round-trip JSON -----------------------------

def test_round_trip_dict():
    IrDefault.set_default('orders.Order', 'shipping_method', {'code': 'standard', 'days': 3})
    assert IrDefault.get_default('orders.Order', 'shipping_method') == {
        'code': 'standard', 'days': 3,
    }


def test_round_trip_int():
    IrDefault.set_default('catalogue.Product', 'stock_threshold', 10)
    assert IrDefault.get_default('catalogue.Product', 'stock_threshold') == 10


def test_round_trip_string():
    IrDefault.set_default('orders.Order', 'currency', 'MXN')
    assert IrDefault.get_default('orders.Order', 'currency') == 'MXN'


def test_get_default_sin_entrada_devuelve_none():
    assert IrDefault.get_default('orders.Order', 'campo_inexistente') is None


# --- Precedencia: user NULL = global; user-specific prevalece ---------------

def test_default_global_visible_sin_user():
    IrDefault.set_default('orders.Order', 'priority', 'normal')
    assert IrDefault.get_default('orders.Order', 'priority') == 'normal'


def test_default_de_usuario_prevalece_sobre_global():
    user = UserFactory()
    IrDefault.set_default('orders.Order', 'priority', 'normal')
    IrDefault.set_default('orders.Order', 'priority', 'alta', user=user)

    # El usuario ve su propio default...
    assert IrDefault.get_default('orders.Order', 'priority', user=user) == 'alta'
    # ...mientras que sin usuario (u otro usuario) sigue viendo el global.
    assert IrDefault.get_default('orders.Order', 'priority') == 'normal'


def test_otro_usuario_sin_default_propio_ve_el_global():
    user = UserFactory()
    otro_user = UserFactory()
    IrDefault.set_default('orders.Order', 'priority', 'normal')
    IrDefault.set_default('orders.Order', 'priority', 'alta', user=user)

    assert IrDefault.get_default('orders.Order', 'priority', user=otro_user) == 'normal'


# --- Alcance de empresa (company) -------------------------------------------

def test_default_de_company_prevalece_sobre_global():
    company = ResCompany.objects.create(code='acme-corp', name='Acme Corp')
    IrDefault.set_default('orders.Order', 'tax_regime', 'general')
    IrDefault.set_default('orders.Order', 'tax_regime', 'simplificado', company=company)

    assert IrDefault.get_default('orders.Order', 'tax_regime', company=company) == 'simplificado'
    assert IrDefault.get_default('orders.Order', 'tax_regime') == 'general'


def test_default_user_y_company_prevalece_sobre_ambos_parciales():
    user = UserFactory()
    company = ResCompany.objects.create(code='acme-corp-2', name='Acme Corp 2')
    IrDefault.set_default('orders.Order', 'warehouse', 'central', user=user)
    IrDefault.set_default('orders.Order', 'warehouse', 'norte', company=company)
    IrDefault.set_default('orders.Order', 'warehouse', 'especifico', user=user, company=company)

    assert IrDefault.get_default(
        'orders.Order', 'warehouse', user=user, company=company,
    ) == 'especifico'


# --- Unicidad: re-set_default sobre el mismo alcance reemplaza --------------

def test_re_set_default_mismo_alcance_reemplaza_no_duplica():
    IrDefault.set_default('orders.Order', 'priority', 'normal')
    IrDefault.set_default('orders.Order', 'priority', 'baja')

    qs = IrDefault.objects.filter(
        model='orders.Order', field='priority', user=None, company=None, condition='',
    )
    assert qs.count() == 1
    assert IrDefault.get_default('orders.Order', 'priority') == 'baja'


def test_set_default_devuelve_la_instancia():
    default = IrDefault.set_default('orders.Order', 'priority', 'normal')
    assert isinstance(default, IrDefault)
    assert default.json_value == '"normal"'


# --- __str__ -----------------------------------------------------------

def test_str_devuelve_model_punto_field():
    default = IrDefault.set_default('orders.Order', 'priority', 'normal')
    assert str(default) == 'orders.Order.priority'


# --- `_get_model_defaults` y la cabecera — tarea #111 -----------------------
#
# El batch por modelo estuvo diferido por dos razones que ya no valen: «queda
# diferido» y que `@tools.ormcache` no existía. El decorador existe desde
# `api@c636e68c`, y el consumidor llegó — `get_company_dependent_fallback` lo
# llama por su nombre.


class TestHeaderClassAttributes:
    """Los cuatro atributos que la referencia declara
    (``odoo19c: ir_default.py``, medidos por AST)."""

    def test_name_matches_the_reference(self):
        assert IrDefault._name == 'ir.default'

    def test_description_matches_the_reference(self):
        assert IrDefault._description == 'Default Values'

    def test_allow_sudo_commands_matches_the_reference(self):
        assert IrDefault._allow_sudo_commands is False

    def test_rec_name_points_at_a_real_field(self):
        # Diverge de la fuente —allá es `field_id`, la FK que este puerto no
        # tiene— y por eso se comprueba que apunte a un campo que existe: un
        # `_rec_name` colgando es peor que ninguno.
        assert IrDefault._rec_name in {f.name for f in IrDefault._meta.get_fields()}


class TestGetModelDefaultsIsMemoized:
    """La adopción de ``ormcache``, con la clave que declara."""

    def test_it_is_decorated(self):
        assert isinstance(IrDefault._get_model_defaults.__func__.__cache__, ormcache)

    def test_the_key_carries_the_model_name_and_the_db_alias(self):
        # La divergencia de clave que `tools/cache.py` declara: el alias de
        # base entra porque aquí el registry es el módulo, no la base.
        key = IrDefault._get_model_defaults.__func__.__cache__.key(
            IrDefault, 'base.ResPartner', '', 1, 2, 'otra_base')
        assert key[0] == 'ir.default'
        assert key[2] == 'base.ResPartner'
        assert key[-1] == 'otra_base'


@pytest.mark.django_db
class TestGetModelDefaults:
    """El batch por modelo — ≙ ``_get_model_defaults`` (``odoo19c: :170-203``)."""

    def _clear(self):
        # El resultado se memoriza; cada caso parte de la familia vacía.
        registry.clear_cache('default')

    def test_it_returns_every_field_of_the_model_in_one_dict(self):
        self._clear()
        IrDefault.set_default('base.ResPartner', 'campo_a', 'uno')
        IrDefault.set_default('base.ResPartner', 'campo_b', 2)
        assert IrDefault._get_model_defaults('base.ResPartner') == {
            'campo_a': 'uno', 'campo_b': 2}

    def test_it_ignores_other_models(self):
        self._clear()
        IrDefault.set_default('base.ResPartner', 'mio', 1)
        IrDefault.set_default('base.ResUsers', 'ajeno', 2)
        assert IrDefault._get_model_defaults('base.ResPartner') == {'mio': 1}

    def test_an_empty_model_gives_an_empty_dict(self):
        self._clear()
        assert IrDefault._get_model_defaults('base.SinDefaults') == {}

    def test_the_user_default_wins_over_the_global_one(self):
        self._clear()
        user = UserFactory()
        IrDefault.set_default('base.ResPartner', 'campo', 'global')
        IrDefault.set_default('base.ResPartner', 'campo', 'del_usuario', user=user)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', user_id=user.pk)['campo'] == 'del_usuario'

    def test_another_user_still_sees_the_global_one(self):
        self._clear()
        user, other = UserFactory(), UserFactory()
        IrDefault.set_default('base.ResPartner', 'campo', 'global')
        IrDefault.set_default('base.ResPartner', 'campo', 'del_usuario', user=user)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', user_id=other.pk)['campo'] == 'global'

    def test_the_company_default_wins_over_the_global_one(self):
        self._clear()
        company = ResCompany.objects.create(name='Empresa 111', code='e111')
        IrDefault.set_default('base.ResPartner', 'campo', 'global')
        IrDefault.set_default('base.ResPartner', 'campo', 'de_empresa',
                              company=company)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', company_id=company.pk)['campo'] == 'de_empresa'

    def test_user_and_company_wins_over_either_alone(self):
        self._clear()
        user = UserFactory()
        company = ResCompany.objects.create(name='Empresa 111b', code='e111b')
        IrDefault.set_default('base.ResPartner', 'campo', 'global')
        IrDefault.set_default('base.ResPartner', 'campo', 'solo_usuario', user=user)
        IrDefault.set_default('base.ResPartner', 'campo', 'solo_empresa',
                              company=company)
        IrDefault.set_default('base.ResPartner', 'campo', 'ambos',
                              user=user, company=company)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', user_id=user.pk,
            company_id=company.pk)['campo'] == 'ambos'

    def test_the_precedence_matches_get_default(self):
        # La fuente resuelve las dos por el mismo ORDER BY; aquí son dos
        # caminos distintos —uno en Python por fila, otro por lookups
        # secuenciales—, así que se comprueba que coincidan. Si divergieran,
        # el mismo campo tendría dos defaults según por dónde se pregunte.
        self._clear()
        user = UserFactory()
        IrDefault.set_default('base.ResPartner', 'campo', 'global')
        IrDefault.set_default('base.ResPartner', 'campo', 'del_usuario', user=user)
        assert (IrDefault._get_model_defaults('base.ResPartner',
                                              user_id=user.pk)['campo']
                == IrDefault.get_default('base.ResPartner', 'campo', user=user))

    def test_the_condition_scopes_the_lookup(self):
        self._clear()
        IrDefault.set_default('base.ResPartner', 'campo', 'sin_condicion')
        IrDefault.set_default('base.ResPartner', 'campo', 'con_condicion',
                              condition='x=1')
        assert IrDefault._get_model_defaults('base.ResPartner') == \
            {'campo': 'sin_condicion'}
        assert IrDefault._get_model_defaults('base.ResPartner', 'x=1') == \
            {'campo': 'con_condicion'}

    def test_writing_a_default_invalidates_what_was_memoized(self):
        # El defecto que esto cierra es invisible sin el caso: el dict caduco
        # se ve bien formado, sólo trae el valor viejo.
        self._clear()
        IrDefault.set_default('base.ResPartner', 'campo', 'primero')
        assert IrDefault._get_model_defaults('base.ResPartner') == \
            {'campo': 'primero'}
        IrDefault.set_default('base.ResPartner', 'campo', 'segundo')
        assert IrDefault._get_model_defaults('base.ResPartner') == \
            {'campo': 'segundo'}

    def test_the_family_it_clears_is_the_one_it_reads(self):
        self._clear()
        IrDefault.set_default('base.ResPartner', 'campo', 'x')
        IrDefault._get_model_defaults('base.ResPartner')
        registry.cache_of('default')['centinela'] = 1
        IrDefault.set_default('base.ResPartner', 'otro', 'y')
        assert 'centinela' not in registry.cache_of('default').snapshot
