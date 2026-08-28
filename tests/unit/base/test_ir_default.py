"""Contrato de ``IrDefault`` (``ir.default``) — portación fiel de Odoo,
iniciativa ``adaptar-familias-odoo-monolito-modular`` (SOL-096, H-BASE-01 C-2,
ÚLTIMO ítem del backlog de control núcleo ``ir.*``).

Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- ``db_table``/``app_label`` fieles a Odoo (``ir_default`` / ``base``),
- campos faithful presentes,
- ``set``/``_get``: round-trip de codificación/decodificación
  JSON (dict, int, string),
- precedencia: ``user`` NULL = global; un default específico de usuario
  prevalece sobre el global para ese usuario (ver docstring de
  ``ir_default.py`` sobre el drift de orden de ``NULL`` Postgres/MariaDB),
- alcance de empresa (``company``),
- unicidad: volver a ``set`` sobre el mismo alcance reemplaza, no
  duplica.

Toca DB → django_db.
"""
import json

import pytest
from django.core.exceptions import ValidationError

from addons.base.models import IrDefault, ResPartner
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


# --- set / _get: round-trip JSON -----------------------------

def test_round_trip_dict():
    IrDefault.set('orders.Order', 'shipping_method', {'code': 'standard', 'days': 3})
    assert IrDefault._get('orders.Order', 'shipping_method') == {
        'code': 'standard', 'days': 3,
    }


def test_round_trip_int():
    IrDefault.set('catalogue.Product', 'stock_threshold', 10)
    assert IrDefault._get('catalogue.Product', 'stock_threshold') == 10


def test_round_trip_string():
    IrDefault.set('orders.Order', 'currency', 'MXN')
    assert IrDefault._get('orders.Order', 'currency') == 'MXN'


def test_get_default_sin_entrada_devuelve_none():
    assert IrDefault._get('orders.Order', 'campo_inexistente') is None


# --- Precedencia: user NULL = global; user-specific prevalece ---------------

def test_default_global_visible_sin_user():
    IrDefault.set('orders.Order', 'priority', 'normal')
    assert IrDefault._get('orders.Order', 'priority') == 'normal'


def test_default_de_usuario_prevalece_sobre_global():
    user = UserFactory()
    IrDefault.set('orders.Order', 'priority', 'normal')
    IrDefault.set('orders.Order', 'priority', 'alta', user=user)

    # El usuario ve su propio default...
    assert IrDefault._get('orders.Order', 'priority', user=user) == 'alta'
    # ...mientras que sin usuario (u otro usuario) sigue viendo el global.
    assert IrDefault._get('orders.Order', 'priority') == 'normal'


def test_otro_usuario_sin_default_propio_ve_el_global():
    user = UserFactory()
    otro_user = UserFactory()
    IrDefault.set('orders.Order', 'priority', 'normal')
    IrDefault.set('orders.Order', 'priority', 'alta', user=user)

    assert IrDefault._get('orders.Order', 'priority', user=otro_user) == 'normal'


# --- Alcance de empresa (company) -------------------------------------------

def test_default_de_company_prevalece_sobre_global():
    company = ResCompany.objects.create(code='acme-corp', name='Acme Corp')
    IrDefault.set('orders.Order', 'tax_regime', 'general')
    IrDefault.set('orders.Order', 'tax_regime', 'simplificado', company=company)

    assert IrDefault._get('orders.Order', 'tax_regime', company=company) == 'simplificado'
    assert IrDefault._get('orders.Order', 'tax_regime') == 'general'


def test_default_user_y_company_prevalece_sobre_ambos_parciales():
    user = UserFactory()
    company = ResCompany.objects.create(code='acme-corp-2', name='Acme Corp 2')
    IrDefault.set('orders.Order', 'warehouse', 'central', user=user)
    IrDefault.set('orders.Order', 'warehouse', 'norte', company=company)
    IrDefault.set('orders.Order', 'warehouse', 'especifico', user=user, company=company)

    assert IrDefault._get(
        'orders.Order', 'warehouse', user=user, company=company,
    ) == 'especifico'


# --- Unicidad: re-set_default sobre el mismo alcance reemplaza --------------

def test_re_set_default_mismo_alcance_reemplaza_no_duplica():
    IrDefault.set('orders.Order', 'priority', 'normal')
    IrDefault.set('orders.Order', 'priority', 'baja')

    qs = IrDefault.objects.filter(
        model='orders.Order', field='priority', user=None, company=None, condition='',
    )
    assert qs.count() == 1
    assert IrDefault._get('orders.Order', 'priority') == 'baja'


def test_set_default_devuelve_la_instancia():
    default = IrDefault.set('orders.Order', 'priority', 'normal')
    assert isinstance(default, IrDefault)
    assert default.json_value == '"normal"'


# --- __str__ -----------------------------------------------------------

def test_str_devuelve_model_punto_field():
    default = IrDefault.set('orders.Order', 'priority', 'normal')
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
        IrDefault.set('base.ResPartner', 'campo_a', 'uno')
        IrDefault.set('base.ResPartner', 'campo_b', 2)
        assert IrDefault._get_model_defaults('base.ResPartner') == {
            'campo_a': 'uno', 'campo_b': 2}

    def test_it_ignores_other_models(self):
        self._clear()
        IrDefault.set('base.ResPartner', 'mio', 1)
        IrDefault.set('base.ResUsers', 'ajeno', 2)
        assert IrDefault._get_model_defaults('base.ResPartner') == {'mio': 1}

    def test_an_empty_model_gives_an_empty_dict(self):
        self._clear()
        assert IrDefault._get_model_defaults('base.SinDefaults') == {}

    def test_the_user_default_wins_over_the_global_one(self):
        self._clear()
        user = UserFactory()
        IrDefault.set('base.ResPartner', 'campo', 'global')
        IrDefault.set('base.ResPartner', 'campo', 'del_usuario', user=user)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', user_id=user.pk)['campo'] == 'del_usuario'

    def test_another_user_still_sees_the_global_one(self):
        self._clear()
        user, other = UserFactory(), UserFactory()
        IrDefault.set('base.ResPartner', 'campo', 'global')
        IrDefault.set('base.ResPartner', 'campo', 'del_usuario', user=user)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', user_id=other.pk)['campo'] == 'global'

    def test_the_company_default_wins_over_the_global_one(self):
        self._clear()
        company = ResCompany.objects.create(name='Empresa 111', code='e111')
        IrDefault.set('base.ResPartner', 'campo', 'global')
        IrDefault.set('base.ResPartner', 'campo', 'de_empresa',
                              company=company)
        assert IrDefault._get_model_defaults(
            'base.ResPartner', company_id=company.pk)['campo'] == 'de_empresa'

    def test_user_and_company_wins_over_either_alone(self):
        self._clear()
        user = UserFactory()
        company = ResCompany.objects.create(name='Empresa 111b', code='e111b')
        IrDefault.set('base.ResPartner', 'campo', 'global')
        IrDefault.set('base.ResPartner', 'campo', 'solo_usuario', user=user)
        IrDefault.set('base.ResPartner', 'campo', 'solo_empresa',
                              company=company)
        IrDefault.set('base.ResPartner', 'campo', 'ambos',
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
        IrDefault.set('base.ResPartner', 'campo', 'global')
        IrDefault.set('base.ResPartner', 'campo', 'del_usuario', user=user)
        assert (IrDefault._get_model_defaults('base.ResPartner',
                                              user_id=user.pk)['campo']
                == IrDefault._get('base.ResPartner', 'campo', user=user))

    def test_the_condition_scopes_the_lookup(self):
        self._clear()
        IrDefault.set('base.ResPartner', 'campo', 'sin_condicion')
        IrDefault.set('base.ResPartner', 'campo', 'con_condicion',
                              condition='x=1')
        assert IrDefault._get_model_defaults('base.ResPartner') == \
            {'campo': 'sin_condicion'}
        assert IrDefault._get_model_defaults('base.ResPartner', 'x=1') == \
            {'campo': 'con_condicion'}

    def test_writing_a_default_invalidates_what_was_memoized(self):
        # El defecto que esto cierra es invisible sin el caso: el dict caduco
        # se ve bien formado, sólo trae el valor viejo.
        self._clear()
        IrDefault.set('base.ResPartner', 'campo', 'primero')
        assert IrDefault._get_model_defaults('base.ResPartner') == \
            {'campo': 'primero'}
        IrDefault.set('base.ResPartner', 'campo', 'segundo')
        assert IrDefault._get_model_defaults('base.ResPartner') == \
            {'campo': 'segundo'}

    def test_the_family_it_clears_is_the_one_it_reads(self):
        self._clear()
        IrDefault.set('base.ResPartner', 'campo', 'x')
        IrDefault._get_model_defaults('base.ResPartner')
        registry.cache_of('default')['centinela'] = 1
        IrDefault.set('base.ResPartner', 'otro', 'y')
        assert 'centinela' not in registry.cache_of('default').snapshot


# --- Los ocho símbolos que la tarea #128 construyó --------------------------
#
# Hasta ese pase se declaraban fuera de alcance con razones que ya no valían
# (ver el docstring del módulo portado). Cada clase mide uno.


class TestCheckJsonFormat:
    """``_check_json_format`` — el JSON tiene que caber en el tipo del campo."""

    def _row(self, **kwargs):
        base = dict(model='base.ResPartner', field='name',
                    json_value='"algo"', condition='')
        base.update(kwargs)
        return IrDefault(**base)

    def test_a_malformed_json_is_rejected(self):
        with pytest.raises(ValidationError, match='Formato JSON'):
            self._row(json_value='{no es json}').clean()

    def test_a_value_of_the_wrong_type_is_rejected(self):
        with pytest.raises(ValidationError, match='Valor inválido'):
            self._row(field='active', json_value='"ni true ni false"').clean()

    def test_a_value_of_the_right_type_passes(self):
        self._row(field='active', json_value='true').clean()

    def test_an_unknown_field_does_not_fail_by_this_route(self):
        """Una fila puede sobrevivir al símbolo que nombraba.

        Eso es un dato caduco, no un JSON mal formado: rechazarlo aquí
        confundiría dos defectos distintos.
        """
        self._row(field='campo_que_ya_no_existe').clean()

    def test_an_unknown_model_does_not_fail_by_this_route(self):
        self._row(model='inventado.NoExiste').clean()

    def test_null_is_accepted_whatever_the_field(self):
        self._row(field='active', json_value='null').clean()


class TestDiscardValues:
    """``discard_values`` — retirar una opción retira su default."""

    def test_it_deletes_only_the_listed_values(self):
        IrDefault.set('base.ResPartner', 'tz', 'America/Mexico_City')
        other = IrDefault.set('base.ResPartner', 'lang', 'es_MX')

        deleted = IrDefault.discard_values(
            'base.ResPartner', 'tz', ['America/Mexico_City'])

        assert deleted == 1
        assert IrDefault._get('base.ResPartner', 'tz') is None
        assert IrDefault.objects.filter(pk=other.pk).exists()

    def test_a_value_that_is_not_a_default_deletes_nothing(self):
        IrDefault.set('base.ResPartner', 'tz', 'America/Mexico_City')
        assert IrDefault.discard_values('base.ResPartner', 'tz', ['UTC']) == 0

    def test_it_invalidates_what_was_memoized(self):
        IrDefault.set('base.ResPartner', 'tz', 'UTC')
        assert IrDefault._get_model_defaults('base.ResPartner')['tz'] == 'UTC'
        IrDefault.discard_values('base.ResPartner', 'tz', ['UTC'])
        assert 'tz' not in IrDefault._get_model_defaults('base.ResPartner')


class TestDiscardRecords:
    """``discard_records`` — borrar un registro borra los defaults que lo citan.

    La fuente filtra por ``field_id.ttype``/``field_id.relation``; aquí esos
    dos datos se derivan del registro de Django, porque el objetivo se guarda
    como texto. Estos casos miden esa derivación, que es donde está el riesgo.
    """

    def test_it_deletes_the_default_that_pointed_at_the_record(self):
        company = ResCompany.objects.create(code='disc-uno', name='Disc Uno')
        IrDefault.set('base.IrDefault', 'company', company.pk)

        deleted = IrDefault.discard_records([company])

        assert deleted >= 1
        assert IrDefault._get('base.IrDefault', 'company') is None

    def test_it_leaves_a_default_pointing_at_another_record(self):
        una = ResCompany.objects.create(code='disc-dos', name='Disc Dos')
        otra = ResCompany.objects.create(code='disc-tres', name='Disc Tres')
        IrDefault.set('base.IrDefault', 'company', otra.pk)

        IrDefault.discard_records([una])

        assert IrDefault._get('base.IrDefault', 'company') == otra.pk

    def test_it_leaves_a_default_of_another_field_with_the_same_value(self):
        """El id coincide pero el campo no apunta a ese modelo.

        Sin la derivación por registro, un filtro que sólo mirara
        ``json_value`` borraría éste — y sería un borrado silencioso de datos
        ajenos.
        """
        company = ResCompany.objects.create(code='disc-cuatro', name='Cuatro')
        IrDefault.set('base.ResPartner', 'color', company.pk)

        IrDefault.discard_records([company])

        assert IrDefault._get('base.ResPartner', 'color') == company.pk

    def test_no_records_is_a_no_op(self):
        assert IrDefault.discard_records([]) == 0

    def test_a_model_that_nothing_points_at_deletes_nothing(self):
        partner = ResPartner.objects.create(name='Sin defaults')
        assert IrDefault.discard_records([partner]) == 0


class TestManyToOnePairs:
    """``_many2one_pairs_to`` — la mitad que la fuente lee de ``ir.model.fields``."""

    def test_it_finds_the_plain_foreign_key(self):
        pairs = IrDefault._many2one_pairs_to('base.ResCompany')
        assert ('base.IrDefault', 'company') in pairs

    def test_it_does_not_find_a_field_pointing_elsewhere(self):
        pairs = IrDefault._many2one_pairs_to('base.ResCompany')
        assert ('base.ResPartner', 'color') not in pairs

    def test_a_model_nobody_points_at_gives_an_empty_list(self):
        assert IrDefault._many2one_pairs_to('inventado.NoExiste') == []


class TestFieldColumnFallbacks:
    """``_get_field_column_fallbacks`` — el respaldo por empresa, como ``jsonb``."""

    def _clear(self):
        registry.clear_cache('default')

    def test_it_maps_every_company_to_its_own_fallback(self):
        self._clear()
        una = ResCompany.objects.create(code='fb-uno', name='FB Uno')
        otra = ResCompany.objects.create(code='fb-dos', name='FB Dos')
        IrDefault.set('base.ResPartner', 'tz', 'UTC', company=una)
        IrDefault.set('base.ResPartner', 'tz', 'America/Mexico_City',
                      company=otra)

        fallbacks = json.loads(
            IrDefault._get_field_column_fallbacks('base.ResPartner', 'tz'))

        assert fallbacks[str(una.pk)] == 'UTC'
        assert fallbacks[str(otra.pk)] == 'America/Mexico_City'

    def test_a_company_without_its_own_default_gets_the_global_one(self):
        self._clear()
        company = ResCompany.objects.create(code='fb-tres', name='FB Tres')
        IrDefault.set('base.ResPartner', 'tz', 'UTC')

        fallbacks = json.loads(
            IrDefault._get_field_column_fallbacks('base.ResPartner', 'tz'))

        assert fallbacks[str(company.pk)] == 'UTC'

    def test_a_field_without_any_default_maps_to_null(self):
        self._clear()
        company = ResCompany.objects.create(code='fb-cuatro', name='FB Cuatro')
        fallbacks = json.loads(IrDefault._get_field_column_fallbacks(
            'base.ResPartner', 'campo_sin_default'))
        assert fallbacks[str(company.pk)] is None


class TestEvaluateConditionWithFallback:
    """``_evaluate_condition_with_fallback`` — el valor que no está en ninguna fila.

    Es el método que exigía ``filtered_domain``: el respaldo de un campo
    dependiente de empresa es lo que el campo responde *cuando la empresa no
    tiene el suyo*, así que no hay fila que un ``WHERE`` pueda devolver.
    """

    FIELD = 'default_applicability'
    MODEL = 'analytic.AccountAnalyticPlan'

    def _clear(self):
        registry.clear_cache('default')

    def test_the_fallback_satisfying_the_condition_is_true(self):
        self._clear()
        IrDefault.set(self.MODEL, self.FIELD, 'optional')
        assert IrDefault._evaluate_condition_with_fallback(
            self.MODEL, self.FIELD, '=', 'optional') is True

    def test_the_fallback_failing_the_condition_is_false(self):
        self._clear()
        IrDefault.set(self.MODEL, self.FIELD, 'optional')
        assert IrDefault._evaluate_condition_with_fallback(
            self.MODEL, self.FIELD, '=', 'mandatory') is False

    def test_without_any_default_the_fallback_is_empty(self):
        self._clear()
        assert IrDefault._evaluate_condition_with_fallback(
            self.MODEL, self.FIELD, '=', 'optional') is False


class TestWriteSurface:
    """``create``/``write``/``unlink`` — y que ``save``/``delete`` no se salten."""

    def _clear(self):
        registry.clear_cache('default')

    def test_create_makes_every_row_of_the_list(self):
        rows = IrDefault.create([
            {'model': 'base.ResPartner', 'field': 'a', 'json_value': '1'},
            {'model': 'base.ResPartner', 'field': 'b', 'json_value': '2'},
        ])
        assert [row.field for row in rows] == ['a', 'b']
        assert IrDefault._get('base.ResPartner', 'a') == 1

    def test_write_updates_the_row(self):
        row = IrDefault.set('base.ResPartner', 'campo', 'viejo')
        row.write({'json_value': '"nuevo"'})
        assert IrDefault._get('base.ResPartner', 'campo') == 'nuevo'

    def test_unlink_removes_the_row(self):
        row = IrDefault.set('base.ResPartner', 'campo', 'x')
        row.unlink()
        assert not IrDefault.objects.filter(pk=row.pk).exists()

    def test_a_plain_save_also_invalidates(self):
        """El camino que la fuente no tiene y aquí sí.

        Poner la guarda sólo en ``create``/``write`` la dejaría saltarse con
        un ``instancia.save()``, y el dict caduco no se ve caduco.
        """
        self._clear()
        row = IrDefault.set('base.ResPartner', 'campo', 'primero')
        assert IrDefault._get_model_defaults('base.ResPartner')['campo'] == \
            'primero'

        row.json_value = '"segundo"'
        row.save()

        assert IrDefault._get_model_defaults('base.ResPartner')['campo'] == \
            'segundo'

    def test_a_plain_delete_also_invalidates(self):
        self._clear()
        row = IrDefault.set('base.ResPartner', 'campo', 'x')
        assert 'campo' in IrDefault._get_model_defaults('base.ResPartner')
        row.delete()
        assert 'campo' not in IrDefault._get_model_defaults('base.ResPartner')
