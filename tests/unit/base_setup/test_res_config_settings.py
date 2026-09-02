"""Contrato de ``base_setup`` — el formulario de ajustes generales.

Cada caso ejerce un símbolo que el porte trajo de
``odoo19c: addons/base_setup/models/res_config_settings.py``. Los cómputos de
la fuente son campos ``compute=`` sobre un ``TransientModel``; aquí son campos
no persistidos cuyo ``default`` invoca al método, así que el caso llama al
método y comprueba la misma población que la fuente consulta.
"""
import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_company import ResCompany
from addons.base.models.ir_ui_view import IrUiView
from addons.base.models.res_country import ResCountry
from addons.base.models.res_groups import ResGroups
from addons.base.models.res_lang import ResLang
from addons.base_setup.models.res_config_settings import (
    DEFAULT_USER_GROUP_XMLID,
    MULTI_CURRENCY_GROUP,
    PROFILING_ENABLED_UNTIL_PARAM,
    SHOW_EFFECT_PARAM,
    ResConfigSettings,
    SiteConfigSettings,
)
from orm.registry import clear_cache

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_param_cache():
    """La caché de ``SystemParameter`` es de módulo — sobrevive al rollback."""
    clear_cache('stable')
    yield
    clear_cache('stable')


class TestClassAttributes:
    """Los atributos de clase que la fuente declara — ``atributos-de-clase-de-modelo``."""

    def test_inherits_the_reference_model_name(self):
        assert ResConfigSettings._inherit == 'res.config.settings'

    def test_the_form_is_not_a_table(self):
        # ≙ ``TransientModel``: la clase se instancia y no tiene tabla propia.
        assert SiteConfigSettings._meta.managed is False


class TestFieldAttrs:
    """El metadato por campo — el equivalente de ``config_parameter=`` de la fuente."""

    def test_the_three_of_the_port_are_declared(self):
        attrs = ResConfigSettings.field_attrs
        assert attrs['group_multi_currency'] == {
            'implied_group': MULTI_CURRENCY_GROUP}
        assert attrs['show_effect'] == {'config_parameter': SHOW_EFFECT_PARAM}
        assert attrs['profiling_enabled_until'] == {
            'config_parameter': PROFILING_ENABLED_UNTIL_PARAM}

    def test_the_child_widens_the_map_instead_of_replacing_it(self):
        """Sin esto los tres del padre quedarían clasificados como ``other``."""
        for name in ResConfigSettings.field_attrs:
            assert name in SiteConfigSettings.field_attrs
        # y los suyos siguen ahí
        assert 'iva_rate' in SiteConfigSettings.field_attrs


class TestComputes:
    def test_company_count_matches_the_table(self):
        settings = SiteConfigSettings()
        assert settings._compute_company_count() == ResCompany.objects.count()

    def test_company_count_follows_a_new_company(self):
        settings = SiteConfigSettings()
        before = settings._compute_company_count()
        ResCompany.objects.create(name='Kaupamex QA')
        assert settings._compute_company_count() == before + 1

    def test_language_count_matches_the_installed_languages(self):
        settings = SiteConfigSettings()
        assert settings._compute_language_count() == len(ResLang.get_installed())

    def test_active_user_count_ignores_the_portal_user(self, django_user_model):
        settings = SiteConfigSettings()
        before = settings._compute_active_user_count()
        # ``share`` es una propiedad: la negación de ``_is_internal()``. Un
        # usuario nuevo sin grupo interno NO cuenta.
        django_user_model.objects.create_user(
            login='shared-user@example.com', password='x' * 12)
        assert settings._compute_active_user_count() == before

    def test_is_root_company_without_company(self):
        settings = SiteConfigSettings()
        settings.company_id = None
        assert settings._compute_is_root_company() is True

    def test_is_root_company_is_false_for_a_child(self):
        parent = ResCompany.objects.create(name='Matriz')
        child = ResCompany.objects.create(name='Filial', parent=parent)
        settings = SiteConfigSettings(company_id=child)
        assert settings._compute_is_root_company() is False

    def test_company_informations_concatenates_like_the_reference(self):
        country, _ = ResCountry.objects.get_or_create(
            code='TL', defaults={'name': 'Testlandia'})
        country.vat_label = 'RFC'
        country.save(update_fields=['vat_label'])
        company = ResCompany.objects.create(
            name='Kaupamex QA', street='Av. Siempre Viva 742',
            city='CDMX', zip='03100', country=country)
        # ``vat`` es una propiedad delegada al partner (``_inherits``), no una
        # columna de ``res.company``: se escribe donde vive.
        company.partner.vat = 'ABC010101XYZ'
        company.partner.save(update_fields=['vat'])
        settings = SiteConfigSettings(company_id=company)
        informations = settings._compute_company_informations()
        assert 'Av. Siempre Viva 742\n' in informations
        assert '03100 - CDMX\n' in informations
        # El doble espacio es de la fuente, no un descuido: ``vat_display``
        # ya termina en ``': '`` y la concatenación es ``'%s %s'``
        # (``odoo19c: :127-128``). Se porta verbatim.
        assert informations.endswith('\nRFC:  ABC010101XYZ')

    def test_company_informations_is_empty_without_company(self):
        settings = SiteConfigSettings()
        settings.company_id = None
        assert settings._compute_company_informations() == ''


class TestActions:
    def test_open_company_returns_the_reference_action(self):
        action = SiteConfigSettings().open_company()
        assert action['type'] == 'ir.actions.act_window'
        assert action['res_model'] == 'res.company'
        assert action['view_mode'] == 'form'
        assert action['target'] == 'current'

    def test_open_new_user_default_groups_creates_the_group_with_its_xmlid(self):
        """La rama de creación: sin el identificador sembrado, lo crea y lo registra.

        El árbol **sí** siembra ``base.default_user_group``, así que la rama
        de creación sólo se alcanza retirando el registro primero. Sin ese
        paso el caso mediría la rama de reutilización y pasaría en verde sin
        ejercer nada de lo que dice medir.
        """
        IrModelData.objects.filter(module='base',
                                   name='default_user_group').delete()
        clear_cache('stable')
        assert IrModelData.ref(DEFAULT_USER_GROUP_XMLID,
                               raise_if_not_found=False) is None
        action = SiteConfigSettings().open_new_user_default_groups()
        clear_cache('stable')
        created = IrModelData.ref(DEFAULT_USER_GROUP_XMLID)
        assert isinstance(created, ResGroups)
        assert action['res_id'] == created.pk
        assert action['target'] == 'new'

    def test_open_new_user_default_groups_omits_the_view_it_cannot_resolve(self):
        """``base.view_default_groups_form`` no está sembrado — se declara arriba.

        El caso fija la conducta degradada: la acción sale sin la clave
        ``views`` en vez de levantar. Si algún día se siembra la vista, este
        caso cae y hay que reescribirlo — que es exactamente lo que se quiere.
        """
        action = SiteConfigSettings().open_new_user_default_groups()
        assert 'views' not in action

    def test_open_new_user_default_groups_reuses_the_existing_group(self):
        seeded = IrModelData.ref(DEFAULT_USER_GROUP_XMLID)
        before = ResGroups.objects.count()
        first = SiteConfigSettings().open_new_user_default_groups()
        second = SiteConfigSettings().open_new_user_default_groups()
        assert first['res_id'] == second['res_id'] == seeded.pk
        assert ResGroups.objects.count() == before

    def test_prepare_report_view_action_points_at_the_view(self):
        view = IrUiView.objects.create(name='Cabecera externa', type='qweb',
                                       arch_db='<div/>')
        IrModelData.set_xmlid(view, 'base_setup.test_report_view')
        action = SiteConfigSettings._prepare_report_view_action(
            'base_setup.test_report_view')
        assert action == {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.view',
            'view_mode': 'form',
            'res_id': view.pk,
        }

    def test_edit_external_header_declares_its_blockade(self):
        with pytest.raises(NotImplementedError) as exc:
            SiteConfigSettings().edit_external_header()
        assert 'external_report_layout_id' in str(exc.value)


class TestShowEffectParameter:
    def test_absent_parameter_reads_as_false(self):
        assert bool(SystemParameter.get_param(SHOW_EFFECT_PARAM)) is False

    def test_set_and_read_back(self):
        SystemParameter.set_param(SHOW_EFFECT_PARAM, '1')
        assert bool(SystemParameter.get_param(SHOW_EFFECT_PARAM)) is True
