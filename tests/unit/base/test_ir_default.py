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
