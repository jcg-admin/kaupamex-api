"""Tests — ``WebConfigSettings`` (tarea #397).

Contrato adaptado de ``odoo19c: addons/web/models/res_config_settings.py``
(``odoo-tools@622ddc2a``): un único campo ``config_parameter``. Se verifica
el motor heredado de ``ResConfigSettings`` (``addons.base.models.res_config``)
con el campo real de este addon — clasificación, escritura y lectura —, y
que el modelo NO crea tabla (``managed = False``, formulario transitorio).
"""
import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.web.models.res_config_settings import WebConfigSettings

pytestmark = pytest.mark.django_db


class TestWebConfigSettingsShape:
    """El modelo es un formulario transitorio, no una tabla."""

    def test_is_unmanaged(self):
        assert WebConfigSettings._meta.managed is False

    def test_field_attrs_declares_config_parameter(self):
        assert WebConfigSettings.field_attrs == {
            'web_app_name': {'config_parameter': 'web.web_app_name'},
        }

    def test_classify_fields_puts_it_in_config_category(self):
        classified = WebConfigSettings.classify_fields()
        assert classified['config'] == [('web_app_name', 'web.web_app_name')]
        assert classified['default'] == []
        assert classified['group'] == []


class TestWebConfigSettingsRoundTrip:
    """``apply_values`` escribe en ``SystemParameter``; ``current_values``
    lo lee de vuelta — las dos direcciones tienen que coincidir."""

    def test_apply_values_writes_the_system_parameter(self):
        settings = WebConfigSettings(web_app_name='Kaupamex Tienda')
        settings.apply_values()
        assert SystemParameter.get_param('web.web_app_name') == 'Kaupamex Tienda'

    def test_current_values_reads_back_what_was_written(self):
        settings = WebConfigSettings(web_app_name='Kaupamex App')
        settings.apply_values()
        values = WebConfigSettings.current_values()
        assert values['web_app_name'] == 'Kaupamex App'

    def test_unset_parameter_reads_back_as_none(self):
        """``current_values`` no cae al default del campo Django — es el
        contrato del motor base (``ResConfigSettings.current_values``, sin
        ``or default``); el formulario del cliente aplica su propio default
        de UI cuando el valor llega ``None``."""
        values = WebConfigSettings.current_values()
        assert values['web_app_name'] is None
