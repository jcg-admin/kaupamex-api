"""Contrato de ``properties.base.definition`` y su mixin — tarea #126.

Cierra el porte de ``src/addons/base/models/properties_base_definition.py`` y
``properties_base_definition_mixin.py`` contra
``odoo19c: odoo/addons/base/models/properties_base_definition{,_mixin}.py``.

Tres bloques:

1. **Cabecera** — los atributos de clase que la referencia declara
   (``atributos-de-clase-de-modelo.md``): ``_name`` y ``_description`` en
   ambas clases.
2. **Los cinco métodos** de ``PropertiesBaseDefinition``, con su nombre de la
   fuente, más la adopción de ``ormcache`` que retira el ``_DEFINITION_CACHE``
   a mano (H-API-865).
3. **Los cuatro métodos** del mixin, incluido el bloqueo medido de
   ``_field_to_sql`` (tarea #127).
"""
import pytest
from django.core.exceptions import PermissionDenied, ValidationError

import orm.models as orm_models

from addons.base.models import PropertiesBaseDefinition
from addons.base.models import properties_base_definition as definition_module
from addons.base.models import (
    properties_base_definition_mixin as mixin_module,
)
from addons.base.models.ir_model import STATE_BASE, IrModel, IrModelFields
from addons.base.models.properties_base_definition_mixin import (
    PROPERTIES_FIELD_NAME,
    PropertiesBaseDefinitionMixin,
)
from orm import registry
from orm.domains import Domain
from orm.fields_nonstored import NonStored
from tools.cache import ormcache
from tools.sql import SQL


class TestHeaderClassAttributes:
    """Los atributos de clase que la referencia declara, verbatim."""

    def test_definition_name_matches_the_reference(self):
        # odoo19c: properties_base_definition.py:10
        assert PropertiesBaseDefinition._name == 'properties.base.definition'

    def test_definition_description_matches_the_reference(self):
        # odoo19c: properties_base_definition.py:11
        assert (PropertiesBaseDefinition._description
                == 'Properties Base Definition')

    def test_mixin_name_matches_the_reference(self):
        # odoo19c: properties_base_definition_mixin.py:11
        assert (PropertiesBaseDefinitionMixin._name
                == 'properties.base.definition.mixin')

    def test_mixin_description_matches_the_reference(self):
        # odoo19c: properties_base_definition_mixin.py:12
        assert (PropertiesBaseDefinitionMixin._description
                == 'Properties Base Definition Mixin')


class TestOrmcacheAdoption:
    """H-API-865: la caché a mano se retira; el decorador real la sustituye."""

    def test_definition_id_lookup_is_decorated_with_ormcache(self):
        lookup = PropertiesBaseDefinition._get_definition_id_for_property_field
        assert isinstance(lookup.__func__.__cache__, ormcache)

    def test_the_family_is_stable_like_the_reference(self):
        # odoo19c: properties_base_definition.py:51 — cache='stable'
        lookup = PropertiesBaseDefinition._get_definition_id_for_property_field
        assert lookup.__func__.__cache__.cache_name == 'stable'

    def test_the_ad_hoc_module_cache_is_gone(self):
        assert not hasattr(definition_module, '_DEFINITION_CACHE')
        assert not hasattr(definition_module, '_clear_definition_cache')

    def test_the_key_carries_the_model_name_and_the_db_alias(self):
        # DIVERGENCIA DE CLAVE declarada en la cabecera del módulo: 'using'
        # entra en la clave porque aquí el registry es el módulo.
        lookup = PropertiesBaseDefinition._get_definition_id_for_property_field
        assert lookup.__func__.__cache__.args == (
            'model_name', 'field_name', 'using')


class TestPortedMethodNames:
    """Los cinco símbolos que el gate de porte reportaba ausentes."""

    @pytest.mark.parametrize('name', [
        '_check_properties_field_id',
        '_compute_display_name',
        '_get_definition_for_property_field',
        '_get_definition_id_for_property_field',
        'write',
    ])
    def test_the_definition_declares_the_reference_symbol(self, name):
        assert callable(getattr(PropertiesBaseDefinition, name))

    @pytest.mark.parametrize('name', [
        '_compute_properties_base_definition_id',
        '_field_to_sql',
        '_search_properties_base_definition_id',
        'create',
    ])
    def test_the_mixin_declares_the_reference_symbol(self, name):
        assert callable(getattr(PropertiesBaseDefinitionMixin, name))


@pytest.mark.django_db
class TestDefinitionBehaviour:
    """Conducta de los métodos portados contra la base real."""

    def _properties_field(self, model='base.Probe', name='properties'):
        ir_model, _ = IrModel.objects.get_or_create(
            model=model, defaults={'name': model})
        return IrModelFields.objects.create(
            model_id=ir_model, model=model, name=name, ttype='properties',
            state=STATE_BASE, field_description='Propiedades')

    def test_lookup_creates_the_row_when_it_is_missing(self):
        registry.clear_cache('stable')
        field = self._properties_field()
        row_id = PropertiesBaseDefinition._get_definition_id_for_property_field(
            'base.Probe', 'properties')
        assert PropertiesBaseDefinition.objects.get(pk=row_id).properties_field_id == field.pk

    def test_lookup_returns_the_row_object(self):
        registry.clear_cache('stable')
        self._properties_field()
        row = PropertiesBaseDefinition._get_definition_for_property_field(
            'base.Probe', 'properties')
        assert isinstance(row, PropertiesBaseDefinition)

    def test_lookup_without_a_reflected_field_is_rejected(self):
        registry.clear_cache('stable')
        with pytest.raises(ValidationError):
            PropertiesBaseDefinition._get_definition_id_for_property_field(
                'base.Absent', 'properties')

    def test_the_second_call_does_not_reach_the_database(self):
        registry.clear_cache('stable')
        self._properties_field()
        first = PropertiesBaseDefinition._get_definition_id_for_property_field(
            'base.Probe', 'properties')
        PropertiesBaseDefinition.objects.filter(pk=first).delete()
        # La fila ya no está; si la respuesta sigue siendo la misma, salió de
        # la caché y no de la base.
        assert PropertiesBaseDefinition._get_definition_id_for_property_field(
            'base.Probe', 'properties') == first

    def test_check_rejects_a_field_that_is_not_of_type_properties(self):
        ir_model, _ = IrModel.objects.get_or_create(
            model='base.Probe', defaults={'name': 'base.Probe'})
        field = IrModelFields.objects.create(
            model_id=ir_model, model='base.Probe', name='label',
            ttype='char', state=STATE_BASE, field_description='Etiqueta')
        row = PropertiesBaseDefinition(properties_field=field)
        with pytest.raises(ValidationError):
            row._check_properties_field_id()

    def test_clean_delegates_on_the_check(self):
        ir_model, _ = IrModel.objects.get_or_create(
            model='base.Probe', defaults={'name': 'base.Probe'})
        field = IrModelFields.objects.create(
            model_id=ir_model, model='base.Probe', name='label',
            ttype='char', state=STATE_BASE, field_description='Etiqueta')
        with pytest.raises(ValidationError):
            PropertiesBaseDefinition(properties_field=field).clean()

    def test_write_rejects_repointing_the_field(self):
        registry.clear_cache('stable')
        field = self._properties_field()
        other = self._properties_field(name='other_properties')
        row = PropertiesBaseDefinition.objects.create(properties_field=field)
        with pytest.raises(PermissionDenied):
            row.write({'properties_field': other})

    def test_write_accepts_changing_the_definition_payload(self):
        registry.clear_cache('stable')
        field = self._properties_field()
        row = PropertiesBaseDefinition.objects.create(properties_field=field)
        row.write({'properties_definition': [{'name': 'a', 'type': 'char'}]})
        row.refresh_from_db()
        assert row.properties_definition == [{'name': 'a', 'type': 'char'}]

    def test_save_empties_the_stable_family(self):
        registry.clear_cache('stable')
        field = self._properties_field()
        PropertiesBaseDefinition._get_definition_id_for_property_field(
            'base.Probe', 'properties')
        assert registry.cache_of('stable').snapshot
        PropertiesBaseDefinition.objects.create(
            properties_field=self._properties_field(name='second'))
        assert not registry.cache_of('stable').snapshot

    def test_display_name_uses_the_model_description(self):
        field = self._properties_field()
        row = PropertiesBaseDefinition(properties_field=field)
        assert row._compute_display_name().endswith(' Properties')

    def test_display_name_is_false_without_a_pointed_model(self):
        assert PropertiesBaseDefinition()._compute_display_name() is False


class TestMixinContract:
    """El mixin: campo sin columna, búsqueda por modelo y el bloqueo medido."""

    def test_the_definition_link_has_no_column(self):
        # `compute` sin `store` en la fuente: no es una columna.
        assert isinstance(
            PropertiesBaseDefinitionMixin.__dict__[
                'properties_base_definition_id'],
            NonStored)

    def test_the_field_name_matches_the_reference(self):
        assert PROPERTIES_FIELD_NAME == 'properties'

    def test_search_returns_not_implemented_for_another_operator(self):
        # odoo19c: properties_base_definition_mixin.py:32-33
        assert (PropertiesBaseDefinitionMixin
                ._search_properties_base_definition_id('=', 1)
                is NotImplemented)

    def test_field_to_sql_delegation_names_its_blocking_task(self):
        # Tarea #127: BaseModel._field_to_sql no existe todavía en src/orm.
        # El bloqueo se declara levantando, no callando: un `return None`
        # aquí sería un verde que no discrimina.
        # El mixin es abstracto: se ejercita la función sin ligar, que es la
        # que porta el cuerpo. La rama de delegación no toca `self`.
        with pytest.raises(NotImplementedError, match='#127'):
            PropertiesBaseDefinitionMixin._field_to_sql(
                None, 'alias', 'another_field')

    def test_the_base_orm_still_lacks_field_to_sql(self):
        # La premisa del bloqueo, medida y no leída: si esto empieza a fallar,
        # la tarea #127 está hecha y el `raise` de arriba sobra.
        assert not hasattr(orm_models, '_field_to_sql')
        assert mixin_module is not None and SQL is not None
