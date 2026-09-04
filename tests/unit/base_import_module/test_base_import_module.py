"""``base_import_module`` — el asistente y sus dos símbolos con veto medido.

``odoo19c: addons/base_import_module/models/base_import_module.py:8-45``.
"""
import pytest

from addons.base_import_module.models import BaseImportModule
from addons.base_import_module.models.base_import_module import (
    IR_MODULE_MODEL, STATE_CHOICES)

pytestmark = pytest.mark.django_db


class TestClassAttributes:
    """Los dos atributos que la fuente declara (``:9-10``)."""

    def test_it_declares_name_and_description(self):
        assert BaseImportModule._name == 'base.import.module'
        assert BaseImportModule._description == 'Import Module'

    def test_the_table_derives_from_the_dotted_name(self):
        assert BaseImportModule._meta.db_table == \
            BaseImportModule._name.replace('.', '_')


class TestTheSixFields:
    """Los seis campos de la fuente (``:12-17``), con sus valores por defecto."""

    def test_the_wizard_persists_and_reads_back(self):
        wizard = BaseImportModule.objects.create(module_file=b'PK\x03\x04')
        assert BaseImportModule.objects.get(pk=wizard.pk).module_file == b'PK\x03\x04'

    def test_state_defaults_to_init(self):
        assert BaseImportModule.objects.create().state == 'init'

    def test_the_state_vocabulary_is_the_one_of_the_source(self):
        assert STATE_CHOICES == [('init', 'init'), ('done', 'done')]

    def test_the_two_booleans_default_to_false(self):
        wizard = BaseImportModule.objects.create()
        assert wizard.force is False
        assert wizard.with_demo is False

    def test_the_two_texts_default_to_empty(self):
        wizard = BaseImportModule.objects.create()
        assert wizard.import_message == ''
        assert wizard.modules_dependencies == ''

    def test_str_shows_the_state(self):
        assert str(BaseImportModule.objects.create()) == 'init'


class TestActionModuleOpen:
    """≙ ``action_module_open`` (``:36-45``) — el act_window verbatim."""

    def test_it_returns_the_act_window_of_the_source(self):
        action = BaseImportModule.objects.create().action_module_open()
        assert action['type'] == 'ir.actions.act_window'
        assert action['res_model'] == IR_MODULE_MODEL
        assert action['view_mode'] == 'list,form'
        assert action['name'] == 'Modules'
        assert action['view_id'] is False

    def test_the_named_modules_travel_in_the_domain(self):
        action = BaseImportModule.objects.create().action_module_open(
            module_name=['sale', 'stock'])
        assert action['domain'] == [('name', 'in', ['sale', 'stock'])]

    def test_without_names_the_domain_is_empty(self):
        """La fuente lee ``context.get('module_name', [])``: sin clave, vacío."""
        action = BaseImportModule.objects.create().action_module_open()
        assert action['domain'] == [('name', 'in', [])]


class TestTheTwoBlockedSymbols:
    """Los dos símbolos vetados fallan ruidoso y nombran a su bloqueador."""

    def test_import_module_names_its_blocker(self):
        with pytest.raises(NotImplementedError, match='_import_zipfile'):
            BaseImportModule.objects.create().import_module()

    def test_get_dependencies_names_its_blocker(self):
        with pytest.raises(NotImplementedError,
                           match='_get_missing_dependencies_modules'):
            BaseImportModule.objects.create().get_dependencies_to_install_names()
