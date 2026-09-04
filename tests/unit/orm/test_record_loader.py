"""``RecordLoaderMixin`` — el lado ORM del cargador de datos, tarea #115.

Cierra el porte de los cuatro símbolos que ``BaseModel`` declara en
``odoo19c: odoo/orm/models.py`` — ``_clean_properties`` (``:5054``),
``_load_records_write`` (``:5085``), ``_load_records_create`` (``:5102``) y
``_load_records`` (``:5108``) — más el override de ``ResPartner``
(``odoo19c: addons/base/models/res_partner.py:966``), que hasta esta tarea
declaraba BLOQUEADO por ``el cargador de data XML`` — no existía aquí.

Cuatro bloques: los símbolos y su adopción, la partición crear/actualizar, la
bandera ``noupdate`` que protege el dato, y los dos avisos de contexto.
"""
import pytest

from addons.base.models import ResPartner
from addons.base.models.ir_model import IrModelData
from exceptions import UserError
from django.core.exceptions import ValidationError
from orm import registry
from orm.environments import context_scope
from orm.models import FieldSqlMixin, RecordLoaderMixin


class TestPortedSymbols:
    """Los cuatro de la fuente, con el guion bajo que declara."""

    @pytest.mark.parametrize('name', [
        '_clean_properties', '_load_records_write', '_load_records_create',
        '_load_records',
    ])
    def test_the_mixin_declares_the_reference_symbol(self, name):
        assert callable(getattr(RecordLoaderMixin, name))

    def test_it_carries_the_field_registry_like_basemodel(self):
        # Allá los ocho símbolos cuelgan del MISMO objeto (``BaseModel``); aquí
        # la herencia reproduce ese hecho en vez de pedir dos adopciones.
        assert issubclass(RecordLoaderMixin, FieldSqlMixin)

    def test_res_partner_adopts_it(self):
        assert RecordLoaderMixin in ResPartner.__mro__

    def test_res_partner_overrides_the_create_hook(self):
        # odoo19c: res_partner.py:966 — el enganche cuya arista se cerró:
        # BLOQUEADO por ``el cargador de data XML`` — construido en #115.
        assert '_load_records_create' in vars(ResPartner)


@pytest.mark.django_db
class TestLoadRecords:
    """La partición de la fuente: crear, actualizar, saltar."""

    def test_it_creates_a_record_and_assigns_the_xmlid(self):
        registry.clear_cache('default')
        records = ResPartner._load_records([
            {'xml_id': 'base.rl_one', 'values': {'name': 'Uno'}},
        ])
        assert records[0].name == 'Uno'
        row = IrModelData.objects.get(module='base', name='rl_one')
        assert (row.model, row.res_id) == ('base.ResPartner', records[0].pk)

    def test_a_second_load_updates_instead_of_duplicating(self):
        registry.clear_cache('default')
        first = ResPartner._load_records([
            {'xml_id': 'base.rl_upd', 'values': {'name': 'Antes'}}])[0]
        second = ResPartner._load_records([
            {'xml_id': 'base.rl_upd', 'values': {'name': 'Despues'}}])[0]
        assert second.pk == first.pk
        assert ResPartner.objects.get(pk=first.pk).name == 'Despues'

    def test_it_returns_the_records_in_the_order_of_data_list(self):
        registry.clear_cache('default')
        records = ResPartner._load_records([
            {'xml_id': 'base.rl_a', 'values': {'name': 'A'}},
            {'xml_id': 'base.rl_b', 'values': {'name': 'B'}},
            {'xml_id': 'base.rl_c', 'values': {'name': 'C'}},
        ])
        assert [r.name for r in records] == ['A', 'B', 'C']

    def test_without_an_xmlid_it_creates(self):
        registry.clear_cache('default')
        records = ResPartner._load_records([{'values': {'name': 'Anonimo'}}])
        assert records[0].pk is not None
        assert not IrModelData.objects.filter(
            model='base.ResPartner', res_id=records[0].pk).exists()

    def test_without_an_xmlid_but_with_an_id_it_updates(self):
        registry.clear_cache('default')
        partner = ResPartner.objects.create(name='Previo')
        ResPartner._load_records([
            {'values': {'id': partner.pk, 'name': 'Corregido'}}])
        assert ResPartner.objects.get(pk=partner.pk).name == 'Corregido'

    def test_an_update_without_id_or_xmlid_is_rejected(self):
        # odoo19c: :5148 — "Cannot update a record without specifying its id
        # or xml_id". Sin ninguno de los dos no hay a qué registro apuntar.
        with pytest.raises(ValidationError):
            ResPartner._load_records(
                [{'values': {'name': 'Sin ancla'}}], update=True)

    def test_an_xmlid_of_another_model_is_rejected(self):
        # La guarda que impide que un xml_id reutilizado apunte a otra tabla.
        registry.clear_cache('default')
        IrModelData.objects.create(
            module='base', name='rl_wrong', model='base.ResCompany', res_id=1)
        with pytest.raises(ValidationError):
            ResPartner._load_records([
                {'xml_id': 'base.rl_wrong', 'values': {'name': 'X'}}])

    def test_an_orphan_xmlid_is_dropped_and_the_record_recreated(self):
        registry.clear_cache('default')
        first = ResPartner._load_records([
            {'xml_id': 'base.rl_orphan', 'values': {'name': 'Primero'}}])[0]
        ResPartner.objects.filter(pk=first.pk).delete()
        registry.clear_cache('default')
        second = ResPartner._load_records([
            {'xml_id': 'base.rl_orphan', 'values': {'name': 'Segundo'}}])[0]
        assert second.pk != first.pk
        assert IrModelData.objects.filter(
            module='base', name='rl_orphan').count() == 1


@pytest.mark.django_db
class TestNoupdateProtection:
    """``noupdate`` protege al registro que alguien tocó a mano."""

    def test_noupdate_blocks_the_write_when_updating(self):
        registry.clear_cache('default')
        first = ResPartner._load_records([
            {'xml_id': 'base.rl_keep', 'noupdate': True,
             'values': {'name': 'A mano'}}])[0]
        ResPartner._load_records(
            [{'xml_id': 'base.rl_keep', 'values': {'name': 'Del modulo'}}],
            update=True)
        assert ResPartner.objects.get(pk=first.pk).name == 'A mano'

    def test_without_update_the_flag_does_not_protect(self):
        # La fuente sólo añade la condición cuando ``update``: una instalación
        # limpia sí escribe.
        registry.clear_cache('default')
        first = ResPartner._load_records([
            {'xml_id': 'base.rl_fresh', 'noupdate': True,
             'values': {'name': 'A mano'}}])[0]
        ResPartner._load_records([
            {'xml_id': 'base.rl_fresh', 'values': {'name': 'Del modulo'}}])
        assert ResPartner.objects.get(pk=first.pk).name == 'Del modulo'


@pytest.mark.django_db
class TestContextWarnings:
    """Los dos avisos que la fuente lee del contexto."""

    def test_import_file_rejects_a_prefix_of_an_installed_module(self):
        # odoo19c: :5185-5193 — el prefijo de un módulo instalado haría que la
        # próxima actualización borrara el registro.
        registry.clear_cache('default')
        IrModule = ResPartner._meta.apps.get_model('base', 'IrModule')
        IrModule.objects.get_or_create(
            name='rlmod', defaults={'state': 'installed'})
        with context_scope(import_file=True):
            with pytest.raises(UserError):
                ResPartner._load_records([
                    {'xml_id': 'rlmod.rl_bad', 'values': {'name': 'Mal'}}])

    def test_import_file_accepts_a_prefix_that_is_not_a_module(self):
        registry.clear_cache('default')
        with context_scope(import_file=True):
            records = ResPartner._load_records([
                {'xml_id': '__import__.rl_ok', 'values': {'name': 'Bien'}}])
        assert records[0].name == 'Bien'

    def test_noupdate_exempts_the_import_file_check(self):
        # La fuente sólo lo comprueba ``if xml_id and not data.get('noupdate')``.
        registry.clear_cache('default')
        IrModule = ResPartner._meta.apps.get_model('base', 'IrModule')
        IrModule.objects.get_or_create(
            name='rlmod2', defaults={'state': 'installed'})
        with context_scope(import_file=True):
            records = ResPartner._load_records([
                {'xml_id': 'rlmod2.rl_exempt', 'noupdate': True,
                 'values': {'name': 'Exento'}}])
        assert records[0].name == 'Exento'


@pytest.mark.django_db
class TestPartnerBatchSync:
    """El override de ``ResPartner``: la sincronización en lote."""

    def test_the_address_of_the_parent_reaches_its_contacts(self):
        registry.clear_cache('default')
        company = ResPartner.objects.create(
            name='Empresa', is_company=True, street='Calle 1', city='CDMX')
        records = ResPartner._load_records([
            {'xml_id': 'base.rl_kid', 'values': {
                'name': 'Contacto', 'parent': company,
                'type': ResPartner.TYPE_CONTACT}},
        ])
        records[0].refresh_from_db()
        assert records[0].street == 'Calle 1'

    def test_a_delivery_address_is_not_overwritten(self):
        # CONTROL: la dirección baja SÓLO a los hijos de tipo contacto. Una
        # dirección de entrega es distinta a propósito.
        registry.clear_cache('default')
        company = ResPartner.objects.create(
            name='Empresa2', is_company=True, street='Calle 1')
        records = ResPartner._load_records([
            {'xml_id': 'base.rl_ship', 'values': {
                'name': 'Entrega', 'parent': company,
                'type': ResPartner.TYPE_DELIVERY, 'street': 'Bodega 9'}},
        ])
        records[0].refresh_from_db()
        assert records[0].street == 'Bodega 9'
