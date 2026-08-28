"""La columna de una FK portada lleva el nombre que la referencia declara (#141).

≙ ADR-029 (``docs: source/backend/adr/adr-029-convencion-fk-sufijo-id.rst``).

La referencia no separa los tres ejes que Django sí separa: en
``odoo19c: odoo/orm/fields_relational.py`` un ``partner_id = fields.Many2one(...)``
nombra a la vez el atributo, la columna y —menos el sufijo— la etiqueta. Aquí
son tres:

===============  ==========================================  ==================
Eje              Cómo se declara                             Ejemplo (forma C)
===============  ==========================================  ==================
símbolo          el nombre del atributo                      ``model_id``
``attname``      SIEMPRE ``<símbolo>_id``; no es opcional    ``model_id_id``
columna          ``db_column`` si se declara; si no, attname  ``model_id``
===============  ==========================================  ==================

Qué haría fallar a estos casos
==============================

Retirar el ``db_column`` de cualquiera de las declaraciones medidas: la columna
cae a su ``attname`` —``model_id_id``— y el caso rompe. Ése es el defecto que
el ADR cierra, y el control que lo discrimina es el segundo bloque: afirma que
el ``attname`` **sigue** siendo el doble sufijo, así que el caso no pasa por
una coincidencia entre los dos ejes.

Un caso que sólo mirase ``field.name`` sería verde con y sin ``db_column`` —
el nombre del símbolo no cambia. Por eso se mide ``field.column``, que es lo
único que llega a PostgreSQL.
"""
import pytest

from addons.account.report.account_invoice_report import AccountInvoiceReport
from addons.auto_backup.models.db_backup_details import DbBackupDetails
from addons.base_automation.models.base_automation import BaseAutomation
from addons.hr_recruitment.models.hr_applicant import HrApplicant
from addons.hr_recruitment.models.hr_recruitment_source import (
    HrRecruitmentSource)
from addons.stock.models.stock_picking import StockPickingType
from addons.utm.models.utm_campaign import UtmCampaign
from addons.utm.models.utm_mixin import UtmMixin
from addons.utm.models.utm_source import UtmSourceMixin

#: Las declaraciones que ADR-029 lleva a forma C. El nombre del símbolo ES el
#: de la referencia, así que la columna esperada es el propio nombre.
FORM_C = [
    pytest.param(AccountInvoiceReport, name, id=f'account_invoice_report.{name}')
    for name in (
        'move_id', 'journal_id', 'company_id', 'company_currency_id',
        'partner_id', 'commercial_partner_id', 'country_id', 'invoice_user_id',
        'fiscal_position_id', 'product_id', 'product_uom_id',
        'product_categ_id', 'account_id', 'currency_id',
    )
] + [
    pytest.param(DbBackupDetails, 'db_backup_id', id='db_backup_details.db_backup_id'),
    pytest.param(BaseAutomation, 'model_id', id='base_automation.model_id'),
    pytest.param(BaseAutomation, 'trg_date_id', id='base_automation.trg_date_id'),
    pytest.param(StockPickingType, 'sequence_id', id='stock_picking_type.sequence_id'),
    pytest.param(UtmCampaign, 'user_id', id='utm_campaign.user_id'),
    pytest.param(UtmCampaign, 'stage_id', id='utm_campaign.stage_id'),
    #: Los cuatro que llegan por mixin abstracto: la declaración vive en
    #: ``UtmMixin``/``UtmSourceMixin`` y la columna aterriza en el concreto.
    pytest.param(HrApplicant, 'campaign_id', id='hr_applicant.campaign_id'),
    pytest.param(HrApplicant, 'source_id', id='hr_applicant.source_id'),
    pytest.param(HrApplicant, 'medium_id', id='hr_applicant.medium_id'),
    pytest.param(HrRecruitmentSource, 'source_id', id='hr_recruitment_source.source_id'),
]


class TestTheColumnCarriesTheReferenceName:
    """Forma C: símbolo fiel + ``db_column`` con ese mismo nombre."""

    @pytest.mark.parametrize('model, name', FORM_C)
    def test_the_column_is_the_symbol_not_its_attname(self, model, name):
        field = model._meta.get_field(name)

        assert field.column == name

    @pytest.mark.parametrize('model, name', FORM_C)
    def test_the_attname_still_doubles_the_suffix(self, model, name):
        """El control que discrimina.

        Si Django no doblara el sufijo, el caso de arriba pasaría solo y no
        mediría nada: sería el verde que no distingue *"declaramos la
        columna"* de *"aquí no había nada que declarar"* (sub-patrón D de
        ``metrica-decide-la-conclusion.md``).
        """
        field = model._meta.get_field(name)

        assert field.attname == f'{name}_id'
        assert field.attname != field.column


class TestTheAbstractMixinPropagatesItsColumn:
    """Un ``db_column`` declarado en un mixin abstracto llega al concreto.

    No es redundante con el bloque anterior: aquél mide el concreto; éste mide
    que la declaración **está en el mixin** y no copiada en cada consumidor —
    si alguien la copiara, retirarla del mixin no rompería nada y el porte
    quedaría con dos fuentes de verdad.
    """

    def test_the_declaration_lives_in_the_abstract_parent(self):
        assert UtmMixin._meta.abstract
        assert UtmMixin._meta.get_field('campaign_id').db_column == 'campaign_id'

    def test_the_source_mixin_declares_its_own(self):
        assert UtmSourceMixin._meta.abstract
        assert UtmSourceMixin._meta.get_field('source_id').db_column == 'source_id'
