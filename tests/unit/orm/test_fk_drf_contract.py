"""Qué eje de la FK consume DRF, y por qué ``db_column`` no toca el contrato (#141).

≙ ADR-029. Es la mitad de arriba del stack: ``test_fk_three_axes.py`` mide que
Django separa símbolo / ``attname`` / columna y qué cuesta cada uno; aquí se
mide **cuál de los tres ve la API**.

Medido en el paquete instalado:

- ``rest_framework/relations.py:172-187`` — ``RelatedField.get_attribute``
  llama ``attribute_instance.serializable_value(self.source_attrs[-1])``, y
  ese argumento es el **nombre del campo**, no su columna.
- ``django/db/models/base.py:794-809`` — ``serializable_value`` recibe el
  nombre y devuelve ``getattr(self, field.attname)``.
- ``rest_framework/relations.py:169`` — ``use_pk_only_optimization``: cuando
  vale ``True``, DRF fabrica un ``PKOnlyObject`` y **no** trae el objeto.

De ahí sale la consecuencia que decide la adopción de ADR-029: la cadena que
DRF recorre es ``símbolo → attname``; la columna no aparece en ninguna de sus
capas. Cambiar ``db_column`` es DDL puro — renombra en PostgreSQL y no mueve
ni una clave del JSON.

El segundo bloque mide de qué depende esa optimización: ``PKOnlyObject``
existe **porque** existe el ``attname``. Es el mismo reparto de costes de
consulta del ORM, visto desde el serializer — la referencia no necesita esta
optimización porque su recordset ya se obtiene sin emitir consulta
(``odoo19c: odoo/orm/fields_relational.py:354-358``).

Qué haría fallar a estos casos
==============================

Que DRF empezara a leer la columna: rompe el primero. Que la optimización de
pk dejara de aplicarse: el conteo de consultas del segundo sube de 0 a 1 y
rompe. Un caso que sólo comprobara ``'model_id' in data`` sería verde con y
sin ``db_column`` — por eso el primero afirma también el **valor**, que es lo
que un cambio de eje sí movería.
"""
import pytest
from rest_framework import serializers

from addons.base.models.ir_model import IrModel
from addons.base_automation.models.base_automation import BaseAutomation


class _AutomationSerializer(serializers.ModelSerializer):
    """El serializer mínimo que ejerce la relación, sin capacidad ni vista.

    NO es un endpoint: aquí se mide el mapeo de campos de ``ModelSerializer``,
    no autorización. Toda vista que exponga esto va gateada por
    ``HasCapability`` (DEC-11) — eso se prueba en ``tests/integration/``.
    """

    class Meta:
        model = BaseAutomation
        fields = ['name', 'model_id']


@pytest.mark.django_db
class TestDrfSpeaksTheSymbol:
    """La clave del JSON es el símbolo; la columna no llega a la API."""

    def test_the_field_is_built_as_a_primary_key_related_field(self):
        field = _AutomationSerializer().fields['model_id']

        assert isinstance(field, serializers.PrimaryKeyRelatedField)
        assert field.source == 'model_id'

    def test_the_serialized_key_and_value_are_the_symbol_and_its_pk(self):
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResCompany', defaults={'name': 'Empresa'})
        automation = BaseAutomation.objects.create(name='A', model_id=model_row)

        data = _AutomationSerializer(automation).data

        assert set(data) == {'name', 'model_id'}
        assert data['model_id'] == model_row.pk

    def test_the_column_name_appears_nowhere_in_the_serializer(self):
        """Control de la afirmación *"la columna no toca el contrato"*.

        La columna de este campo es ``model_id`` — la misma cadena que el
        símbolo, por forma C — así que buscarla por nombre no discriminaría
        nada. Lo que sí discrimina es el ``attname``, que es el eje por el que
        DRF pasa internamente y que **no** debe asomar como clave.
        """
        field = BaseAutomation._meta.get_field('model_id')
        data = _AutomationSerializer(BaseAutomation(name='B')).data

        assert field.attname == 'model_id_id'
        assert 'model_id_id' not in data

    def test_writing_binds_the_object_under_the_symbol(self):
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResCurrency', defaults={'name': 'Moneda'})

        serializer = _AutomationSerializer(
            data={'name': 'Nueva', 'model_id': model_row.pk})

        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data['model_id'] == model_row


@pytest.mark.django_db
class TestThePkOnlyOptimizationLivesOffTheSplit:
    """``PKOnlyObject`` depende de que exista un ``attname`` separado."""

    def test_serializing_the_relation_costs_no_extra_query(
            self, django_assert_num_queries):
        model_row, _ = IrModel.objects.get_or_create(
            model='base.ResGroups', defaults={'name': 'Grupo'})
        BaseAutomation.objects.create(name='C', model_id=model_row)
        fresh = BaseAutomation.objects.get(name='C')

        with django_assert_num_queries(0):
            assert _AutomationSerializer(fresh).data['model_id'] == model_row.pk

    def test_the_optimization_is_declared_by_the_field_itself(self):
        field = _AutomationSerializer().fields['model_id']

        assert field.use_pk_only_optimization() is True
