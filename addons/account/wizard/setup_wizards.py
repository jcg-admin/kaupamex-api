"""``account.financial.year.op`` + ``account.setup.bank.manual.config`` —
los dos asistentes del onboarding contable.

Adaptación de Odoo ``addons/account/wizard/setup_wizards.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, LGPL-3 —
atribución y aviso de licencia preservados, DEC-KX-03).

``TransientModel`` → clase con classmethods, no tabla — mismo patrón que
``AccountDebitNoteWizard``.

``AccountFinancialYearOp`` — 12 símbolos (5 campos + 7 defs), el desglose
==========================================================================

===================================  ======================================
Símbolo de la referencia              Qué pasa aquí
===================================  ======================================
``company_id`` (campo)                PORTADO — parámetro ``company``
``opening_move_posted`` (compute)     NO — lee
                                       ``company.account_opening_move_id``,
                                       campo no portado en ``res.company``
                                       (el asiento de apertura no está en
                                       ``models/res_company.py``, que porta
                                       candados, cuentas de utilidad y
                                       prefijos — no la apertura).
``opening_date`` (related)            NO — related a
                                       ``company.account_opening_date``
                                       (mismo bloqueo).
``fiscalyear_last_day`` (related)     NO — related a
                                       ``company.fiscalyear_last_day``
                                       (el cierre fiscal no está portado;
                                       mismo hueco que declara
                                       ``account_resequence.py``).
``fiscalyear_last_month`` (related)   NO — ídem.
``_compute_opening_move_posted``      NO — bloqueado (arriba).
``_check_fiscalyear``                 PORTADO — validación pura de fecha.
``_company_fields_to_update``         PORTADO — contrato verbatim.
``_update_company``                   NO — escribe los tres campos
                                       bloqueados de arriba y mueve la
                                       fecha del asiento de apertura.
``create``                            NO — persistencia del transitorio de
                                       Odoo (aquí el wizard no guarda
                                       fila; los valores viajan por
                                       parámetro). Su única lógica real es
                                       delegar en ``_update_company``,
                                       bloqueado.
``write``                             NO — ídem.
``action_save_onboarding_fiscal_year``  NO — marca el paso
                                       ``onboarding.onboarding.step`` por
                                       xmlid y devuelve un
                                       ``ir.actions.client`` — los pasos
                                       de onboarding de ``account`` (data
                                       XML) no están portados y la acción
                                       es navegación del cliente Odoo.
===================================  ======================================

``AccountSetupBankManualConfig`` — 17 símbolos (9 campos + 8 defs)
===================================================================

===================================  ======================================
Símbolo de la referencia              Qué pasa aquí
===================================  ======================================
``res_partner_bank_id`` (campo)       PORTADO — parámetro
                                       ``partner_bank`` (la delegación
                                       ``_inherits`` se declara verbatim
                                       en la clase; el mecanismo
                                       ``orm/inherits.py`` existe, pero un
                                       transitorio sin tabla no delega
                                       columnas — divergencia declarada).
``new_journal_name`` (campo)          PORTADO — parámetro
``linked_journal_id`` (campo)         PORTADO — parámetro ``journal``
``bank_bic`` (related)                PORTADO — parámetro ``bank_bic``
``num_journals_without_account_*``    NO — cuentan diarios sin
(los dos campos)                       ``bank_account_id``, campo del
                                       diario no portado
                                       (``account_journal.py`` no declara
                                       ``bank_account_id``).
``company_id`` (campo)                PORTADO — parámetro ``company``
``_number_unlinked_journal``          NO — bloqueado por
                                       ``journal.bank_account_id`` (arriba).
``_onchange_acc_number``              PORTADO
``create``                            PORTADO — ``create`` (la parte con
                                       lógica real: partner de la empresa
                                       + buscar/crear el banco por BIC)
``_onchange_new_journal_related_data``  PORTADO
``_compute_linked_journal_id``        NO — bloqueado por
                                       ``journal.bank_account_id`` (la
                                       relación cuenta↔diario no existe).
``default_linked_journal_id``         NO — ídem.
``set_linked_journal_id``             PORTADO (parcial declarado, ver su
                                       docstring)
``validate``                          PORTADO — hook de extensión; aquí
                                       devuelve ``None`` en vez del
                                       ``ir.actions.client soft_reload``
                                       (navegación del cliente Odoo).
``_compute_company_id``               PORTADO — el fallback a la empresa
                                       activa, con la empresa por
                                       parámetro.
===================================  ======================================
"""
from datetime import date

from addons.account.models.account_journal import AccountJournal
from addons.base.models import ResBank
from exceptions import ValidationError
from orm.models_transient import TransientModel
from tools.translate import _


class AccountFinancialYearOp(TransientModel):
    """≙ ``account.financial.year.op`` — fecha de apertura y cierre fiscal
    de la empresa (ver la tabla del módulo para lo bloqueado)."""

    _name = 'account.financial.year.op'
    _description = 'Opening Balance of Financial Year'

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _check_fiscalyear(cls, fiscalyear_last_month, fiscalyear_last_day):
        """≙ ``_check_fiscalyear`` — la fecha debe existir; se prueba sobre
        2020 (bisiesto), igual que la referencia."""
        try:
            date(2020, int(fiscalyear_last_month), fiscalyear_last_day)
        except ValueError:
            raise ValidationError(_(
                'Incorrect fiscal year date: day is out of range for '
                'month. Month: %(month)s; Day: %(day)s') % {
                    'month': fiscalyear_last_month,
                    'day': fiscalyear_last_day,
                })

    @classmethod
    def _company_fields_to_update(cls):
        """≙ ``_company_fields_to_update`` — el contrato, verbatim. Sus
        consumidores (``_update_company``/``create``/``write``) están
        bloqueados por los campos de la empresa; ver la tabla del módulo."""
        return {'fiscalyear_last_day', 'fiscalyear_last_month', 'opening_date'}


class AccountSetupBankManualConfig(TransientModel):
    """≙ ``account.setup.bank.manual.config`` — alta manual de una cuenta
    bancaria y su diario (ver la tabla del módulo para lo bloqueado)."""

    _name = 'account.setup.bank.manual.config'
    _inherits = {'res.partner.bank': 'res_partner_bank_id'}
    _description = 'Bank setup manual config'
    _check_company_auto = True

    class Meta:
        abstract = True
        managed = False

    @classmethod
    def _onchange_acc_number(cls, acc_number):
        """≙ ``_onchange_acc_number`` — el nombre propuesto del diario es el
        número de cuenta."""
        return acc_number

    @classmethod
    def create(cls, company, acc_number, bank=None, bank_bic=None):
        """La parte con lógica real de ``create`` — ≙ el cuerpo del
        ``@api.model_create_multi``: el partner es SIEMPRE el de la empresa
        activa, y sin banco elegido un BIC busca (o crea) el banco.

        Devuelve ``(partner, new_journal_name, bank)`` — los tres valores
        que la referencia inyecta en ``vals`` antes del ``super().create``
        (que aquí no persiste fila: transitorio sin tabla).
        """
        partner = company.partner
        new_journal_name = acc_number
        if bank is None and bank_bic:
            bank = ResBank.objects.filter(bic=bank_bic).first()
            if bank is None:
                bank = ResBank.objects.create(name=bank_bic, bic=bank_bic)
        return partner, new_journal_name, bank

    @classmethod
    def _onchange_new_journal_related_data(cls, journal):
        """≙ ``_onchange_new_journal_related_data`` — con diario elegido, el
        nombre propuesto es el suyo."""
        return journal.name if journal is not None else None

    @classmethod
    def set_linked_journal_id(cls, company, partner_bank, new_journal_name,
                               journal=None, journal_type='bank'):
        """≙ ``set_linked_journal_id`` (parcial declarado).

        Sin diario elegido, crea uno del tipo pedido — la referencia además
        (a) deriva el código con
        ``account.journal._get_next_journal_default_code`` (no portado; el
        código sale del prefijo del tipo + consecutivo simple, divergencia
        declarada) y (b) enlaza ``bank_account_id`` /
        ``bank_statements_source`` (campos del diario no portados —
        bloqueado por ellos; el enlace cuenta↔diario queda para cuando
        aterricen).
        """
        if journal is None:
            prefix = 'BNK' if journal_type == 'bank' else 'CRD'
            count = AccountJournal.objects.filter(
                company=company, type=journal_type).count()
            journal = AccountJournal.objects.create(
                name=new_journal_name,
                code=f'{prefix}{count + 1}',
                type=journal_type,
                company=company,
            )
        else:
            journal.name = new_journal_name
            journal.save(update_fields=['name'])
        return journal

    @classmethod
    def validate(cls):
        """Called by the validation button of this wizard. Serves as an
        extension hook in account_bank_statement_import.

        (Docstring verbatim de la referencia.) Aquí devuelve ``None`` — el
        ``ir.actions.client soft_reload`` es navegación del cliente Odoo.
        """
        return None

    @classmethod
    def _compute_company_id(cls, company=None, active_company=None):
        """≙ ``_compute_company_id`` — el fallback a la empresa activa."""
        return company or active_company
