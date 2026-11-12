"""Un modelo histórico de migración no deja escrituras pendientes en el ORM.

Una migración de datos guarda con los modelos de ``apps.get_model`` —clases
``__fake__`` del ``StateApps``—, que reconstruyen sus campos con las mismas
clases del ORM y por tanto con su ``FieldDescriptor``. Asignar un campo sobre
una fila histórica ya persistida pasaba por ``FieldDescriptor.__set__`` y
marcaba el campo sucio en la transacción global, que es la del modelo VIVO.

El volcado posterior (``flush_all``, al crear el registro de una base de
empresa) escribía entonces las columnas del estado histórico: tras renombrar
``created_at`` → ``create_date`` el ``UPDATE`` nombraba una columna que ya no
existe (ci-multidb sobre ``04c28427``, ``__fake__.ResUsers`` id 1).

La fuente no tiene este caso: una migración de Odoo escribe con SQL o con el
ORM vivo, nunca con una clase de estado. El modelo histórico es de Django, y
su contrato es el de Django: ``setattr`` escribe el atributo y ``save()`` lo
persiste, sin caché ni volcado diferido.

*Métrica:* entradas de ``field_dirty`` tras asignar sobre una fila histórica.
*Ciega a:* un receptor de señal que encole trabajo para el modelo histórico
por otra vía que no sea el descriptor.
"""
import pytest
from django.apps import apps
from django.db import connection, transaction
from django.db.migrations.operations import RunPython
from django.db.migrations.state import ProjectState

from orm.environments import get_transaction

pytestmark = pytest.mark.django_db


def _dirty_fields():
    return {field for field, ids in get_transaction().field_dirty.items()
            if ids}


@pytest.fixture
def historical_country():
    historical_apps = ProjectState.from_apps(apps).apps
    model = historical_apps.get_model('base', 'ResCountry')
    assert model._meta.apps is not apps
    row = model.objects.order_by('pk').first()
    assert row is not None
    return row


def test_assigning_a_historical_row_leaves_the_transaction_clean(
        historical_country):
    before = _dirty_fields()
    historical_country.name = f'{historical_country.name} (historical)'
    assert _dirty_fields() == before


def test_the_historical_assignment_still_reaches_the_attribute(
        historical_country):
    historical_country.name = 'Historical name'
    assert historical_country.__dict__['name'] == 'Historical name'


def test_a_live_row_assignment_is_still_marked_dirty():
    live = apps.get_model('base', 'ResCountry').objects.order_by('pk').first()
    live.name = f'{live.name} (live)'
    assert any(field.model is type(live) for field in _dirty_fields())


def _historical_keys(structure):
    """Campos de modelos históricos presentes en una estructura de la
    transacción (``field_data``, ``field_dirty`` o ``tocompute``)."""
    return {field for field in structure
            if getattr(getattr(field, 'model', None), '_meta', None)
            and field.model._meta.apps is not apps}


def _transaction_is_free_of_historical_fields():
    transaction = get_transaction()
    return not (_historical_keys(transaction.field_data)
                or _historical_keys(transaction.field_dirty)
                or _historical_keys(transaction.tocompute))


def test_loading_a_historical_row_does_not_fill_the_live_cache(
        historical_country):
    # El cargador de Django asigna cada columna al construir la fila: ese
    # tramo poblaba la caché del ORM con campos que el registro vivo no tiene.
    type(historical_country).objects.filter(pk=historical_country.pk).get()
    assert _transaction_is_free_of_historical_fields()


def test_a_historical_save_persists_like_django(historical_country):
    historical_country.name = 'Saved through the migration state'
    historical_country.save(update_fields=['name'])
    live = apps.get_model('base', 'ResCountry')
    assert (live.objects.filter(pk=historical_country.pk)
            .values_list('name', flat=True).get()
            == 'Saved through the migration state')
    assert _transaction_is_free_of_historical_fields()


def test_a_historical_create_persists_and_leaves_the_transaction_clean():
    model = ProjectState.from_apps(apps).apps.get_model('base', 'ResCountry')
    row = model.objects.create(code='QZ', name='Historical country')
    assert apps.get_model('base', 'ResCountry').objects.filter(
        pk=row.pk, code='QZ').exists()
    assert _transaction_is_free_of_historical_fields()


def test_run_python_saves_through_the_state_without_queueing_orm_work():
    """El camino real de una migración de datos: ``RunPython`` recibe el
    ``apps`` del estado y guarda con él."""
    from_state = ProjectState.from_apps(apps)
    to_state = from_state.clone()

    def forwards(state_apps, schema_editor):
        model = state_apps.get_model('base', 'ResCountry')
        row = model.objects.order_by('pk').first()
        row.name = 'Renamed by RunPython'
        row.save()

    operation = RunPython(forwards, RunPython.noop)
    with connection.schema_editor(atomic=False) as editor:
        operation.database_forwards('base', editor, from_state, to_state)
    first = apps.get_model('base', 'ResCountry').objects.order_by('pk').first()
    assert first.name == 'Renamed by RunPython'
    assert _transaction_is_free_of_historical_fields()


def test_a_rolled_back_historical_write_leaves_no_row():
    model = ProjectState.from_apps(apps).apps.get_model('base', 'ResCountry')
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            model.objects.create(code='QY', name='Rolled back')
            raise RuntimeError('rollback')
    assert not apps.get_model('base', 'ResCountry').objects.filter(
        code='QY').exists()
    assert _transaction_is_free_of_historical_fields()
