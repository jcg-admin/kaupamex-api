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
