"""Contrato de ``IrFilters`` (``ir.filters``) — portación fiel de Odoo,
iniciativa ``adaptar-familias-odoo-monolito-modular`` (SOL-096, H-BASE-01 C-2).

Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- ``db_table``/``app_label`` fieles a Odoo (``ir_filters`` / ``base``),
- campos faithful presentes + defaults de ``context``/``domain``/``sort``/
  ``active``,
- ``user`` NULL = filtro global/compartido; set = filtro privado,
- invariante "un solo default por (model_id, user)" — al guardar un segundo
  filtro por defecto en el mismo alcance, el primero se desmarca (``save()``,
  ver docstring de ``ir_filters.py`` sobre la simplificación frente a Odoo).

Toca DB → django_db.
"""
import pytest

from addons.base.models import IrFilters
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrFilters.__module__ == 'addons.base.models.ir_filters'


# --- db_table / app_label fieles a Odoo ------------------------------------

def test_db_table_fiel_a_odoo():
    assert IrFilters._meta.db_table == 'ir_filters'
    assert IrFilters._meta.app_label == 'base'


def test_campos_faithful_presentes():
    field_names = {f.name for f in IrFilters._meta.get_fields()}
    for expected in (
        'name', 'user', 'model_id', 'domain', 'context', 'sort',
        'is_default', 'action_id', 'active',
    ):
        assert expected in field_names, f'falta el campo Odoo {expected!r}'


# --- Creación con defaults ---------------------------------------------------

def test_create_minimo_aplica_defaults():
    filtro = IrFilters.objects.create(name='Mis pendientes', model_id='orders.Order')
    filtro.refresh_from_db()

    assert filtro.domain == '[]'
    assert filtro.context == '{}'
    assert filtro.sort == '[]'
    assert filtro.active is True
    assert filtro.is_default is False
    assert filtro.user_id is None
    assert filtro.action_id is None


# --- user NULL = global; set = privado --------------------------------------

def test_user_null_es_filtro_global():
    filtro = IrFilters.objects.create(name='Global', model_id='catalogue.Product')
    assert filtro.user_id is None


def test_user_set_es_filtro_privado():
    user = UserFactory()
    filtro = IrFilters.objects.create(
        name='Mio', model_id='catalogue.Product', user=user,
    )
    filtro.refresh_from_db()
    assert filtro.user_id == user.pk


# --- Invariante: un solo default por (model_id, user) -----------------------

def test_segundo_default_global_desmarca_al_primero():
    primero = IrFilters.objects.create(
        name='Default A', model_id='orders.Order', is_default=True,
    )
    segundo = IrFilters.objects.create(
        name='Default B', model_id='orders.Order', is_default=True,
    )

    primero.refresh_from_db()
    segundo.refresh_from_db()

    assert primero.is_default is False
    assert segundo.is_default is True


def test_default_personal_no_afecta_default_global():
    user = UserFactory()
    global_default = IrFilters.objects.create(
        name='Default global', model_id='orders.Order', is_default=True,
    )
    personal_default = IrFilters.objects.create(
        name='Default personal', model_id='orders.Order', user=user, is_default=True,
    )

    global_default.refresh_from_db()
    personal_default.refresh_from_db()

    # Alcances distintos (user=None vs user=<user>): no se pisan entre sí.
    assert global_default.is_default is True
    assert personal_default.is_default is True


def test_default_no_afecta_otro_modelo():
    primero = IrFilters.objects.create(
        name='Default orders', model_id='orders.Order', is_default=True,
    )
    segundo = IrFilters.objects.create(
        name='Default catalogue', model_id='catalogue.Product', is_default=True,
    )

    primero.refresh_from_db()
    segundo.refresh_from_db()

    assert primero.is_default is True
    assert segundo.is_default is True


def test_update_no_default_no_desmarca_nada():
    primero = IrFilters.objects.create(
        name='Default único', model_id='orders.Order', is_default=True,
    )
    otro = IrFilters.objects.create(name='No-default', model_id='orders.Order')
    otro.name = 'No-default (editado)'
    otro.save()

    primero.refresh_from_db()
    assert primero.is_default is True


# --- __str__ -----------------------------------------------------------

def test_str_devuelve_name():
    filtro = IrFilters.objects.create(name='Mi filtro', model_id='orders.Order')
    assert str(filtro) == 'Mi filtro'
