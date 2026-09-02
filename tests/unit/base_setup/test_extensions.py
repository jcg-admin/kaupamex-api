"""Contrato de las tres extensiones de ``base_setup``.

``kpi.provider``, ``ir.http`` y ``res.users`` son los tres modelos ajenos que
el addon extiende. Aquí se ejercen los símbolos que el porte trajo, y la
instalación misma: que ``ready()`` haya colgado lo que declara.
"""
import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_users import ResUsers
from addons.base_setup.controllers.kpi import _get_kpi_providers
from addons.base_setup.models.ir_http import IrHttp
from addons.base_setup.models.kpi_provider import KpiProvider
from addons.base_setup.models.res_config_settings import SHOW_EFFECT_PARAM
from addons.base_setup.models.res_users import DISCUSS_REQUIRED_MESSAGE
from exceptions import UserError
from orm.registry import clear_cache

pytestmark = pytest.mark.django_db


@pytest.fixture
def internal_user(admin_user):
    """Un usuario con grupo de ``user_type='internal'`` — lo que mide ``_is_internal``."""
    group = ResGroups.objects.create(name='Internos QA', user_type='internal')
    admin_user.group_ids.add(group)
    return admin_user


@pytest.fixture(autouse=True)
def _clear_param_cache():
    clear_cache('stable')
    yield
    clear_cache('stable')


class TestKpiProvider:
    """≙ ``kpi.provider`` (``odoo19c: base_setup/models/kpi_provider.py``)."""

    def test_class_attributes_come_from_the_reference(self):
        assert KpiProvider._name == 'kpi.provider'
        assert KpiProvider._description == 'KPI Provider'
        assert KpiProvider._meta.abstract is True

    def test_the_base_provider_contributes_nothing(self):
        # La fuente devuelve ``[]``: el modelo es el punto de enganche, no el
        # que aporta indicadores.
        assert KpiProvider.get_kpi_summary() == []


class TestKpiProviderLoader:
    """≙ ``_get_kpi_providers`` (``odoo19c: controllers/kpi.py:20-70``)."""

    def test_the_result_is_cached(self):
        assert _get_kpi_providers() is _get_kpi_providers()

    def test_no_addon_declares_a_provider_today(self):
        # Denominador declarado: ningún ``__manifest__.py`` del árbol trae la
        # clave ``kpi_providers``, así que la tupla es vacía. El caso mide que
        # el barrido corre sin levantar, no que la clave no exista.
        assert _get_kpi_providers() == ()


class TestIrHttpSessionInfo:
    """≙ ``IrHttp.session_info`` (``odoo19c: base_setup/models/ir_http.py``)."""

    def test_class_attributes_come_from_the_reference(self):
        assert IrHttp._inherit == 'ir.http'
        assert IrHttp._meta.abstract is True

    def test_an_internal_user_gets_the_flag(self, internal_user):
        SystemParameter.set_param(SHOW_EFFECT_PARAM, '1')
        assert IrHttp.session_info(internal_user, {})['show_effect'] is True

    def test_the_flag_is_false_when_the_parameter_is_absent(self, internal_user):
        assert IrHttp.session_info(internal_user, {})['show_effect'] is False

    def test_a_user_without_an_internal_group_gets_no_flag(self, admin_user):
        """La guarda ``_is_internal()`` de la fuente, con su control negativo.

        ``admin_user`` tiene rol de superadministrador pero **ningún grupo con
        ``user_type='internal'``**, que es lo que ``_is_internal()`` mide. Sin
        este caso el par de arriba no distinguiría «la guarda pasa» de «la
        guarda no existe».
        """
        SystemParameter.set_param(SHOW_EFFECT_PARAM, '1')
        assert 'show_effect' not in IrHttp.session_info(admin_user, {})

    def test_an_anonymous_caller_gets_no_flag(self):
        SystemParameter.set_param(SHOW_EFFECT_PARAM, '1')
        assert 'show_effect' not in IrHttp.session_info(None, {})

    def test_the_body_is_returned_untouched_for_an_anonymous_caller(self):
        body = {'uid': None}
        assert IrHttp.session_info(None, body) is body


class TestWebCreateUsers:
    """≙ ``res.users.web_create_users`` (``odoo19c: base_setup/models/res_users.py``)."""

    def test_the_extension_is_installed_on_the_foreign_model(self):
        # ``ready()`` cuelga el método sobre ``base.ResUsers`` con
        # ``extend_model``; sin la instalación este atributo no existiría.
        assert hasattr(ResUsers, 'web_create_users')

    def test_it_raises_the_reference_message_without_discuss(self):
        """La guarda de la fuente, con su mensaje verbatim.

        ``email_normalized`` lo aporta Discuss y no existe en este árbol, así
        que ésta es hoy la conducta completa del método — la misma que la
        fuente tiene cuando el addon no está instalado.
        """
        with pytest.raises(UserError) as exc:
            ResUsers.web_create_users(['alguien@example.com'])
        assert DISCUSS_REQUIRED_MESSAGE in str(exc.value)
