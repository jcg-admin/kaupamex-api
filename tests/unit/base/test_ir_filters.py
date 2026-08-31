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

from django.db import IntegrityError, transaction

from addons.base.models import IrFilters
from addons.base.models.ir_actions import IrActionsActions
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrFilters.__module__ == 'addons.base.models.ir_filters'


# --- db_table / app_label fieles a Odoo ------------------------------------

def test_db_table_matches_reference():
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


# --- Los objetos de tabla de la fuente (#250) --------------------------------
#
# La referencia declara CUATRO piezas que este porte no traia: la FK real a
# ``ir.actions.actions`` y sus tres objetos de tabla
# (``odoo19c: ir_filters.py:19``, ``:26-40``). La FK se declinaba con una razon
# que el propio bloque reconocia caduca —«ir.actions.actions ya esta portado,
# asi que el FK real cabe»— y difiriendola «a su propio pase», que
# ``hallazgo-abierto-genera-sucesor.md`` no admite como bloqueo.

def test_the_action_is_a_real_foreign_key():
    """``:19`` — ``fields.Many2one('ir.actions.actions', ...)``.

    Que lo haria fallar: un ``Integer`` plano. Guarda el mismo numero y no
    puede garantizar que apunte a una accion que exista, que es lo unico que
    una FK compra.
    """
    field = IrFilters._meta.get_field('action_id')
    assert field.is_relation
    assert field.related_model is IrActionsActions


def test_deleting_the_action_takes_its_filters(db):
    """``ondelete='cascade'`` de ``:19``.

    Que lo haria fallar: ``SET NULL`` o ``PROTECT``. Con el primero el filtro
    sobrevive apuntando a nada y reaparece en todos los menus del modelo; con
    el segundo la accion no se puede borrar.
    """
    action = IrActionsActions.objects.create(name='Accion de prueba')
    IrFilters.objects.create(name='Filtro colgado', model_id='base.ResPartner',
                             action_id=action)
    action.delete()
    assert not IrFilters.objects.filter(name='Filtro colgado').exists()


def test_a_sort_that_is_not_an_array_is_rejected():
    """``_check_sort_json`` (``:37-40``) — ``jsonb_typeof(sort::jsonb) =
    'array'``.

    Que lo haria fallar: aceptar cualquier cadena. ``sort`` se deserializa
    como lista; un objeto o un escalar revientan en el lector, lejos de aqui.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IrFilters.objects.create(name='Orden invalido',
                                     model_id='base.ResPartner', sort='{}')


def test_a_valid_sort_passes_the_same_check(db):
    """El control positivo del anterior: sin el, una restriccion que rechazara
    TODO tambien pasaria el caso de arriba."""
    filtro = IrFilters.objects.create(name='Orden valido',
                                      model_id='base.ResPartner',
                                      sort='["name asc"]')
    assert filtro.pk is not None


def test_the_parent_res_id_needs_its_embedded_action():
    """``_check_res_id_only_when_embedded_action`` (``:33-36``).

    Docstring de la fuente, verbatim: *"Constraint to ensure that the
    embedded_parent_res_id is only defined when a top_action_id is defined."*

    Que lo haria fallar: admitir el id del padre sin la accion embebida. El
    filtro quedaria acotado a una fila de un modelo que nadie declaro.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IrFilters.objects.create(name='Padre sin embebida',
                                     model_id='base.ResPartner',
                                     embedded_parent_res_id=7)


def test_the_lookup_index_of_the_source_is_declared():
    """``_get_filters_index`` (``:26-28``) — ``(model_id, action_id,
    embedded_action_id, embedded_parent_res_id)``.

    Es la consulta que ``get_filters`` hace en cada apertura de vista. Que lo
    haria fallar: no declararlo — el barrido secuencial no da error, solo
    tarda, que es la clase de defecto que nadie reporta.
    """
    indexes = {index.name: list(index.fields)
               for index in IrFilters._meta.indexes}
    assert 'ir_filters_get_filters_index' in indexes
    assert indexes['ir_filters_get_filters_index'] == [
        'model_id', 'action_id', 'embedded_action', 'embedded_parent_res_id']
