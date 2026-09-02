"""``digest.digest._compute_kpis_actions`` — el gancho de acciones (addon
``digest``, tarea #158).

Adaptación fiel de Odoo digest/models/digest.py
(odoo-tools@622ddc2a, odoo19c:, LGPL-3, ``:330-337``) — el punto de
extensión que cada addon con KPI cuelga con ``overrides=``
(:mod:`orm.method_chain`) para enlazar la acción de su KPI.

Dos capas de prueba, deliberadamente separadas:

- El eslabón **base**, aislado de la cadena instalada por ``crm``/
  ``hr_recruitment`` — caminando ``_chain_previous`` hasta el final, mismo
  idioma que ``tests/integration/base/test_res_currency_engine.py``.
- La cadena **completa**, tal como Django la instala vía ``INSTALLED_APPS``
  (sin simular ``apply_*_extensions()`` a mano): si un ``overrides=`` de
  ``crm`` o ``hr_recruitment`` se rompiera —clave mal escrita, kwarg
  olvidado— estas claves desaparecerían del resultado.
"""
import pytest

from addons.base.models import ResCompany
from addons.base.models.ir_model import IrModelData
from addons.base.models.res_groups import ResGroups
from addons.digest.models import DigestDigest
from tests.factories.user_factory import UserFactory

pytestmark = pytest.mark.django_db

#: Los xml_id que ``crm``/``hr_recruitment`` cuelgan — verbatim de sus
#: propios módulos (no se importan de ahí para que un typo en cualquiera de
#: los dos lados se note aquí, no se enmascare comparando la misma cadena).
ACTION_PIPELINE = 'crm.crm_lead_action_pipeline'
ACTION_ALL_LEADS = 'crm.crm_lead_all_leads'
ACTION_OPEN_MY_EMPLOYEES = 'hr.open_view_employee_list_my'


def _base_method():
    """El eslabón base de la cadena instalada sobre ``DigestDigest`` — el
    que ``addons/digest/models/digest.py`` declara en el cuerpo de la
    clase, sin el ``overrides=`` que ``crm``/``hr_recruitment`` le cuelgan
    encima.
    """
    installed = DigestDigest.__dict__.get('_compute_kpis_actions')
    assert installed is not None, (
        '_compute_kpis_actions no está instalado en DigestDigest — el '
        'porte de la tarea #158 no aterrizó.')
    current = installed
    while getattr(current, '_chain_previous', None) is not None:
        current = current._chain_previous
    return current


@pytest.fixture
def company():
    return ResCompany.objects.create(
        code='digest-actions-co', name='Digest Actions Co')


@pytest.fixture
def digest(company):
    return DigestDigest.objects.create(
        name='Digest con acciones', company_id=company)


@pytest.fixture
def recipient():
    return UserFactory(login='destinatario@practicayoruba.mx')


@pytest.fixture
def group_use_lead():
    group = ResGroups.objects.create(name='Usa leads (fixture)')
    IrModelData.set_xmlid(group, 'crm.group_use_lead')
    return group


class TestBaseIsAnEmptyExtensionPoint:
    """El método base — ``{}``, igual que la fuente."""

    def test_returns_empty_dict(self, digest, company, recipient):
        base = _base_method()
        assert base(digest, company, recipient) == {}

    def test_ignores_its_arguments(self, digest):
        """La base no lee ``company`` ni ``user`` — puede recibir ``None``
        en los dos sin reventar. Es lo que hace posible que las
        extensiones, más abajo en la cadena, sean las únicas que
        condicionan algo."""
        base = _base_method()
        assert base(digest, None, None) == {}


class TestFullChainAsDjangoInstallsIt:
    """La cadena completa — ``crm`` + ``hr_recruitment`` sobre la base,
    instalada por ``AppConfig.ready()`` al arrancar (sin invocar
    ``apply_*_extensions()`` a mano)."""

    def test_default_actions_for_a_user_without_special_groups(
        self, digest, company, recipient,
    ):
        actions = digest._compute_kpis_actions(company, recipient)
        assert actions == {
            'kpi_crm_lead_created': ACTION_PIPELINE,
            'kpi_crm_opportunities_won': ACTION_PIPELINE,
            'kpi_hr_recruitment_new_colleagues': ACTION_OPEN_MY_EMPLOYEES,
        }

    def test_lead_action_switches_for_group_use_lead(
        self, digest, company, recipient, group_use_lead,
    ):
        recipient.group_ids.add(group_use_lead)
        actions = digest._compute_kpis_actions(company, recipient)
        assert actions['kpi_crm_lead_created'] == ACTION_ALL_LEADS
        # El grupo sólo condiciona el KPI de leads — el de oportunidades
        # ganadas y el de hr_recruitment no se mueven.
        assert actions['kpi_crm_opportunities_won'] == ACTION_PIPELINE
        assert actions['kpi_hr_recruitment_new_colleagues'] == (
            ACTION_OPEN_MY_EMPLOYEES)

    def test_no_recipient_is_fail_closed_not_a_crash(self, digest, company):
        """``user=None`` no revienta — la guarda ``user is not None`` de
        ``crm`` (mismo criterio que ``utm._user_has_group``) lo tolera, y
        cae al valor por defecto."""
        actions = digest._compute_kpis_actions(company, None)
        assert actions == {
            'kpi_crm_lead_created': ACTION_PIPELINE,
            'kpi_crm_opportunities_won': ACTION_PIPELINE,
            'kpi_hr_recruitment_new_colleagues': ACTION_OPEN_MY_EMPLOYEES,
        }
