"""``base_install_request`` — el asistente y la acción que lo abre.

Cubre los seis símbolos portados de ``odoo19c: base_install_request/wizard/
base_module_install_request.py`` y los dos que el puerto declara con su
arista de veto, más la acción
de ``models/ir_module_module.py``.
"""
import pytest

from addons.base.models import IrModule, ResPartner, ResUsers
from addons.base.models.ir_model import IrModelData
from addons.base.models.ir_module import IrModuleDependency
from addons.base_install_request.data import (
    INSTALL_REQUEST_TEMPLATE, INSTALL_REQUEST_TEMPLATE_MODULE,
    INSTALL_REQUEST_TEMPLATE_XMLID)
from addons.base_install_request.wizard.base_module_install_request import (
    BaseModuleInstallRequest, BaseModuleInstallReview,
    _auto_install_apps, render_modules_description)
from exceptions import UserError

pytestmark = pytest.mark.django_db


@pytest.fixture
def sale():
    """Un módulo desinstalado, que es el dominio de los dos ``module_id``."""
    return IrModule.objects.create(
        name='sale', shortdesc='Ventas', application=True,
        state='uninstalled', icon='/sale/static/description/icon.png')


@pytest.fixture
def product(sale):
    """Una dependencia de ``sale`` que también es aplicación."""
    dep = IrModule.objects.create(
        name='product', shortdesc='Productos', application=True,
        state='uninstalled')
    IrModuleDependency.objects.create(module=sale, name='product')
    return dep


class TestClassAttributes:
    """Los tres atributos que la fuente declara en cada ``TransientModel``."""

    def test_request_declares_name_description_and_rec_name(self):
        assert BaseModuleInstallRequest._name == 'base.module.install.request'
        assert BaseModuleInstallRequest._description == (
            'Module Activation Request')
        assert BaseModuleInstallRequest._rec_name == 'module_id'

    def test_review_declares_name_description_and_rec_name(self):
        assert BaseModuleInstallReview._name == 'base.module.install.review'
        assert BaseModuleInstallReview._description == (
            'Module Activation Review')
        assert BaseModuleInstallReview._rec_name == 'module_id'

    def test_the_table_name_derives_from_the_odoo_name(self):
        """``_name.replace('.', '_')`` — la derivación de la fuente."""
        for model in (BaseModuleInstallRequest, BaseModuleInstallReview):
            assert model._meta.db_table == model._name.replace('.', '_')


class TestTheWizardHasATable:
    """Un ``TransientModel`` de la fuente tiene tabla real (``_auto = True``)."""

    def test_a_request_can_be_saved_and_read_back(self, sale):
        wizard = BaseModuleInstallRequest.objects.create(module_id=sale)
        assert BaseModuleInstallRequest.objects.get(pk=wizard.pk).module_id_id \
            == sale.pk

    def test_str_uses_the_rec_name(self, sale):
        assert str(BaseModuleInstallRequest.objects.create(
            module_id=sale)) == 'Ventas'


class TestComputeUserIds:
    """≙ ``_compute_user_ids`` — los usuarios de ``base.group_system``."""

    def test_it_returns_the_users_of_group_system(self, sale):
        group = IrModelData.ref('base.group_system', raise_if_not_found=False)
        if group is None:
            pytest.skip('base.group_system no está sembrado en esta base')
        # ``name`` es una property que delega en el partner (``orm/inherits``):
        # el usuario se crea con su partner, no con el nombre suelto.
        partner = ResPartner.objects.create(
            name='Sysadmin', email='sysadmin@example.test')
        member = ResUsers.objects.create(
            login='sysadmin-install-request', partner=partner)
        member.group_ids.add(group)
        wizard = BaseModuleInstallRequest.objects.create(module_id=sale)
        assert member in wizard._compute_user_ids()

    def test_the_field_reads_the_compute(self, sale):
        """El descriptor sin columna sirve lo que el cómputo devuelve."""
        wizard = BaseModuleInstallRequest.objects.create(module_id=sale)
        assert list(wizard.user_ids) == list(wizard._compute_user_ids())


class TestActionSendRequest:
    """≙ ``action_send_request`` — envía y devuelve la notificación."""

    def test_it_returns_the_client_action_of_the_source(self, sale):
        wizard = BaseModuleInstallRequest.objects.create(module_id=sale)
        action = wizard.action_send_request()
        assert action['type'] == 'ir.actions.client'
        assert action['tag'] == 'display_notification'
        assert action['params']['type'] == 'success'
        assert action['params']['next'] == {
            'type': 'ir.actions.act_window_close'}

    def test_the_template_is_seeded_with_its_external_id(self):
        """La semilla de la migración: sin ella el envío no tiene plantilla."""
        template = IrModelData.ref(
            '%s.%s' % (INSTALL_REQUEST_TEMPLATE_MODULE,
                       INSTALL_REQUEST_TEMPLATE_XMLID))
        assert template is not None
        assert template.name == INSTALL_REQUEST_TEMPLATE['name']

    def test_without_the_template_it_raises(self, sale, monkeypatch):
        """Control de anulación: sin plantilla la acción no calla, levanta."""
        monkeypatch.setattr(IrModelData, 'ref',
                            classmethod(lambda cls, *a, **k: None))
        wizard = BaseModuleInstallRequest.objects.create(module_id=sale)
        with pytest.raises(UserError):
            wizard.action_send_request()


class TestRenderModulesDescription:
    """≙ la plantilla QWeb, compuesta en Python marca por marca."""

    def test_the_paragraph_appears_only_with_applications(self, sale):
        assert 'The following apps will be installed:' in (
            render_modules_description([sale]))

    def test_without_applications_there_is_no_paragraph(self):
        technical = IrModule.objects.create(
            name='base_setup', shortdesc='Ajustes', application=False)
        assert 'The following apps will be installed:' not in (
            render_modules_description([technical]))

    def test_a_non_application_gets_no_item(self):
        """``t-if="app.application"`` sobre cada ``<li>``."""
        technical = IrModule.objects.create(
            name='base_vat', shortdesc='NIF', application=False)
        assert '<li' not in render_modules_description([technical])

    def test_the_item_carries_the_icon_and_the_shortdesc(self, sale):
        markup = render_modules_description([sale])
        assert 'class="list-unstyled row"' in markup
        assert 'class="mt8 col-lg-6"' in markup
        assert sale.icon in markup
        assert 'Ventas' in markup

    def test_the_shortdesc_is_escaped(self):
        """``t-esc`` escapa por definición; el ``shortdesc`` es de un tercero."""
        hostile = IrModule.objects.create(
            name='evil', shortdesc='<script>x</script>', application=True)
        assert '<script>' not in render_modules_description([hostile])


class TestGetDependingApps:
    """≙ ``_get_depending_apps`` — el cierre hacia arriba y sus dos guardas."""

    def test_without_a_module_it_raises(self):
        with pytest.raises(UserError):
            BaseModuleInstallReview._get_depending_apps(None)

    def test_an_installed_module_raises(self):
        installed = IrModule.objects.create(
            name='already_installed', shortdesc='Instalado',
            state='installed')
        with pytest.raises(UserError):
            BaseModuleInstallReview._get_depending_apps(installed)

    def test_the_module_itself_comes_first(self, sale):
        assert BaseModuleInstallReview._get_depending_apps(sale)[0] == sale

    def test_an_application_dependency_is_included(self, sale, product):
        apps = BaseModuleInstallReview._get_depending_apps(sale)
        assert product in apps

    def test_the_result_has_no_duplicates(self, sale, product):
        apps = BaseModuleInstallReview._get_depending_apps(sale)
        assert len(apps) == len({app.pk for app in apps})


class TestComputeModulesDescription:
    """≙ ``_compute_modules_description`` — los dos campos en una pasada."""

    def test_both_fields_come_from_the_same_pass(self, sale, product):
        review = BaseModuleInstallReview.objects.create(module_id=sale)
        apps, description = review._compute_modules_description()
        assert sale in apps and product in apps
        assert description == render_modules_description(apps)

    def test_the_descriptors_serve_each_half(self, sale):
        review = BaseModuleInstallReview.objects.create(module_id=sale)
        assert list(review.module_ids) == [sale]
        assert 'Ventas' in review.modules_description


class TestTheBlockedTwo:
    """Los dos símbolos sin portar fallan ruidoso, no en silencio."""

    def test_action_install_module_declares_its_blockade(self, sale):
        review = BaseModuleInstallReview.objects.create(module_id=sale)
        with pytest.raises(NotImplementedError, match='button_immediate_install'):
            review.action_install_module()

    def test_auto_install_apps_declares_its_blockade(self):
        with pytest.raises(NotImplementedError, match='button_install'):
            _auto_install_apps()


class TestActionOpenInstallRequest:
    """≙ ``IrModuleModule.action_open_install_request`` — la acción de entrada."""

    def test_it_returns_the_act_window_of_the_source(self, sale):
        action = sale.action_open_install_request()
        assert action['type'] == 'ir.actions.act_window'
        assert action['target'] == 'new'
        assert action['view_mode'] == 'form'
        assert action['res_model'] == BaseModuleInstallRequest._name
        assert action['context'] == {'default_module_id': sale.pk}

    def test_the_name_carries_the_shortdesc(self, sale):
        assert 'Ventas' in sale.action_open_install_request()['name']
