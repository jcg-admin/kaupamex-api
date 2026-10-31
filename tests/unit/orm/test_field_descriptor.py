"""Contrato del descriptor y de la asignación sin volcado SQL.

Referencia fijada: Odoo19Community Field.__get__/__set__. Las pruebas de
caché, protección y escritura conservan sus responsabilidades históricas.
La expectativa de ausencia de setter en columnas ordinarias se reconcilia
con el fallo medido de invalidación de TASK-GEN-0633; los nuevos casos
PostgreSQL prueban el efecto, no sólo la presencia de un método.
"""
import pytest
from django.db import connection, models
from django.db.models.query_utils import DeferredAttribute
from django.test.utils import CaptureQueriesContext

from orm.environments import env as get_environment
from orm.fields import ComputedFieldDescriptor, FieldDescriptor
from orm.registry import MODELS_BY_NAME
from orm.utils import model_field_registry


@pytest.fixture
def partner_model(db):
    return MODELS_BY_NAME['res.partner']


def descriptor_of(model_class, field_name):
    """El objeto que ocupa el atributo de clase — no el campo."""
    return inspect_class_attribute(model_class, field_name)


def inspect_class_attribute(model_class, field_name):
    for klass in model_class.__mro__:
        if field_name in vars(klass):
            return vars(klass)[field_name]
    return None


class TestTheDescriptorIsInstalledWhereItHasWork:
    """La poblacion del descriptor se decide por ``compute``, no por gusto."""

    def test_a_computed_field_gets_the_data_descriptor(self, partner_model):
        """Con ``compute`` hay que INTERCEPTAR la escritura: ``__set__``."""
        field = model_field_registry(partner_model)['commercial_company_name']
        assert getattr(field, 'compute', None)

        descriptor = descriptor_of(partner_model, 'commercial_company_name')

        assert isinstance(descriptor, ComputedFieldDescriptor)
        assert hasattr(descriptor, '__set__')

    def test_a_plain_column_has_the_dependency_notifying_setter(self, partner_model):
        """Una columna ordinaria también puede alimentar un cómputo."""
        descriptor = descriptor_of(partner_model, 'name')
        assert isinstance(descriptor, DeferredAttribute)
        assert isinstance(descriptor, FieldDescriptor)
        assert not isinstance(descriptor, ComputedFieldDescriptor)
        assert hasattr(descriptor, '__set__')



class TestGetOnTheClass:
    """``:1644-1645`` — ``if record is None: return self``."""

    def test_class_level_access_returns_the_descriptor(self, partner_model):
        assert isinstance(partner_model.commercial_company_name, FieldDescriptor)


class TestGetGoesThroughTheEnvironmentCache:
    """``:1668-1673`` — el acierto de cache no toca la base."""

    def test_it_returns_what_the_cache_holds(self, partner_model):
        record = partner_model.objects.create(name='En cache')
        field = model_field_registry(partner_model)['commercial_company_name']
        field._update_cache(record, 'Valor sembrado', dirty=False)

        assert record.commercial_company_name == 'Valor sembrado'

    def test_a_cache_miss_repopulates_the_cache(self, partner_model):
        """``:1694-1804`` — al fallar la cache el cuerpo la vuelve a poblar.

        El observable NO es el valor —el computo puede dar ``None`` y un caso
        que lo mire pasaria con la cache vacia y con ella poblada—. El
        observable es que tras la lectura la clave EXISTE en la cache.
        """
        record = partner_model.objects.create(name='Sin sembrar')
        field = model_field_registry(partner_model)['commercial_company_name']
        field._invalidate_cache(record_environment())
        assert record.pk not in field._get_cache(record_environment())

        record.commercial_company_name

        assert record.pk in field._get_cache(record_environment())


class TestSetPartitionsTheRecordAsTheSourceDoes:
    """``:1809-1817`` — protegida / nueva / real, los tres cubos."""

    def test_a_protected_record_gets_no_business_logic(self, partner_model):
        """``:1819-1822`` — durante su propio computo no se recalcula.

        Sin este cubo, escribir el resultado de un computo dispararia el
        recalculo del propio campo: recursion infinita.
        """
        record = partner_model.objects.create(name='Protegida')
        field = model_field_registry(partner_model)['commercial_company_name']
        environment = record_environment()

        with environment.protecting([field], record):
            record.commercial_company_name = 'Escrito bajo proteccion'

        assert field._get_cache(environment)[record.pk] == 'Escrito bajo proteccion'

    def test_a_real_record_is_not_flushed_on_assignment(self, partner_model):
        """La divergencia de mecanismo, medida y declarada en el modulo.

        La fuente manda el cubo real a ``records.write()``. Aqui
        ``BaseModel.write`` llama a ``save()``, asi que portarlo literal haria
        que ``p.campo = x`` emitiera un UPDATE — y en Django la asignacion no
        vuelca la fila. Se porta lo que ``write`` hace SIN el volcado: marcar
        sucia la cache. El volcado sigue siendo ``save()``.

        **El observable son las sentencias de ESCRITURA, no el conteo de
        consultas.** Una primera version afirmaba ``0`` consultas y media el
        fenomeno equivocado: ``modified()`` recorre los dependientes y para eso
        SELECTea, que es lo que la fuente tambien hace y no es un volcado
        (``metrica-decide-la-conclusion.md``). El lote de ese recorrido es
        trabajo de #273.

        El control que discrimina es la tercera asercion: si el cubo real
        volcara, la fila releida de la base traeria el valor nuevo.
        """
        record = partner_model.objects.create(name='Real')
        field = model_field_registry(partner_model)['commercial_company_name']
        stored_before = partner_model.objects.values_list(
            'commercial_company_name', flat=True).get(pk=record.pk)

        with CaptureQueriesContext(connection) as capturadas:
            record.commercial_company_name = 'Asignado'

        escrituras = [q['sql'] for q in capturadas
                      if q['sql'].lstrip().upper().startswith(
                          ('UPDATE', 'INSERT', 'DELETE'))]
        assert escrituras == []
        assert partner_model.objects.values_list(
            'commercial_company_name', flat=True).get(
                pk=record.pk) == stored_before
        assert field._get_cache(record_environment())[record.pk] == 'Asignado'


def record_environment():
    return get_environment()
