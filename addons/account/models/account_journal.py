"""``account.journal`` — diario contable (Odoo ``account``).

Portación fiel de ``account_journal.py`` (Odoo 18/19, ``type`` idéntico:
sale/purchase/cash/bank/credit/general). Campos núcleo: ``name``, ``code``,
``type``, ``currency``, ``default_account``, ``company``, ``active``.
"""

from django.apps import apps

import api
import fields
import models
from addons.base.models import TimeStampedModel
from addons.mail.models import MailActivityMixin, MailThread
from addons.portal.models.portal_mixin import PortalMixin


class AccountJournal(models.BaseModel, PortalMixin, MailThread,
                     MailActivityMixin, TimeStampedModel):
    """``account.journal`` — diario donde se registran los asientos."""

    #: Los atributos de clase que la fuente declara
    #: (``odoo19c: account_journal.py:43-53``). Sin ``_name`` el diario NO
    #: entra en ``orm.registry.MODELS_BY_NAME``, y con el fuera ni
    #: ``linked_journal`` del asistente de banco resuelve su comodelo ni
    #: ``_check_company_auto`` tiene a quien preguntar.
    _name = 'account.journal'
    _description = 'Journal'
    _order = 'sequence, type, code'
    #: ≙ ``_inherit`` (``:46-50``), verbatim. En este árbol la lista es
    #: metadato: el comportamiento sale de la herencia de Python. El diario
    #: hereda tres de los cuatro, en el orden de la lista: ``PortalMixin``
    #: (``addons/portal/models/portal_mixin.py``), ``MailThread``
    #: (``addons/mail/models/mail_thread.py``) y ``MailActivityMixin``
    #: (``addons/mail/models/mail_activity_mixin.py``).
    #: BLOQUEADO por ``mail.alias.mixin``: ``mail.alias.mixin.optional`` no
    #: existe aquí y depende de su porte (TASK-GEN-0413); con él quedan sin
    #: portar ``alias_name`` y ``_alias_get_creation_values``
    #: (``:829-842``).
    _inherit = [
        'portal.mixin',
        'mail.alias.mixin.optional',
        'mail.thread',
        'mail.activity.mixin',
    ]
    #: ≙ ``_check_company_auto = True`` (``:51``): la coherencia de empresa se
    #: valida al guardar.
    _check_company_auto = True
    #: ≙ ``_check_company_domain`` (``:52``).
    #: El ``classmethod`` es la forma de ESTE arbol, no un adorno: su
    #: hermano ``CheckCompanyMixin._check_company_domain`` es un
    #: ``@classmethod`` y el consumidor lo invoca sobre la clase. La fuente
    #: asigna la funcion pelada porque alla el consumidor es un recordset,
    #: que es una instancia. Mismo simbolo, misma semantica; lo que cambia
    #: es sobre que se invoca.
    _check_company_domain = classmethod(models.check_company_domain_parent_of)
    #: ≙ ``_rec_names_search = ['name', 'code']`` (``:53``).
    _rec_names_search = ['name', 'code']

    JOURNAL_TYPES = [
        ('sale', 'Ventas'),
        ('purchase', 'Compras'),
        ('cash', 'Efectivo'),
        ('bank', 'Banco'),
        ('credit', 'Tarjeta de crédito'),
        ('general', 'Varios'),
    ]

    name = fields.Char(
        max_length=255,
        help_text='Nombre del diario (Odoo name, requerido).',
    )
    code = fields.Char(
        max_length=12,
        help_text='Código corto del diario (Odoo code).',
    )
    type = fields.Selection(
        max_length=12,
        choices=JOURNAL_TYPES,
        help_text='Tipo de diario (Odoo type, requerido).',
    )
    currency = fields.Many2one(
        'base.ResCurrency',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='journals',
        help_text='Moneda del diario (Odoo currency_id).',
    )
    default_account = fields.Many2one(
        'account.AccountAccount',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_for_journals',
        help_text='Cuenta por defecto (Odoo default_account_id).',
    )
    company = fields.Many2one(
        'base.ResCompany',
        null=False, on_delete=models.PROTECT,
        related_name='journals',
        help_text='Empresa (Odoo company_id).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Diario activo (Odoo active).',
    )
    sequence = fields.Integer(
        default=10,
        help_text='Orden del diario (Odoo sequence).',
    )
    # ``show_on_dashboard`` y ``color`` los declara la referencia en
    # ``account_journal_dashboard.py:30-31``, un ``_inherit`` del **mismo**
    # addon. Se portan aquí —misma clase, mismo addon— porque el archivo
    # aparte de allá es una separación de lectura, no de modelo; el resto de
    # ese archivo (la agregación del tablero) queda pendiente, sucesor #158.
    show_on_dashboard = fields.Boolean(
        default=True,
        help_text='Mostrar en el tablero (Odoo show_on_dashboard).',
    )
    color = fields.Integer(
        default=0,
        help_text='Índice de color (Odoo color).',
    )

    # Campos de diario bancario — ≙ ``odoo19c: account_journal.py:245-255``.
    # Los desbloquea la tarea #333: el asistente de alta manual de cuenta
    # (``account.setup.bank.manual.config``) liga la cuenta al diario por
    # ``bank_account``, y sin el campo su ``set_linked_journal_id`` no podia
    # hacer lo que la fuente hace.
    company_partner = fields.Many2one(
        'base.ResPartner',
        related='company.partner',
        store=False,
        verbose_name='Account Holder',
        help_text='Titular de la cuenta (Odoo company_partner_id).',
    )
    #: Forma C de ADR-029 (#141): el simbolo lleva el ``_id`` de la fuente Y
    #: la columna tambien. Las FK de arriba son forma A —deuda congelada que
    #: barre #143—; una declaracion NUEVA no la ensancha.
    bank_account_id = fields.Many2one(
        'base.ResPartnerBank',
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        db_index=True,
        db_column='bank_account_id',
        related_name='journals',
        verbose_name='Bank Account',
        help_text='Cuenta bancaria del diario (Odoo bank_account_id).',
    )
    #: ≙ ``bank_statements_source`` (``:253``). Su ``selection`` allá es el
    #: metodo ``_get_bank_statements_available_sources``, que un addon extiende
    #: para anadir su origen; aqui las opciones se resuelven al declarar la
    #: clase, asi que la lista base vive en el metodo y el campo la consume.
    bank_statements_source = fields.Selection(
        max_length=32,
        default='undefined',
        verbose_name='Bank Feeds',
        choices=[('undefined', 'Undefined Yet')],
        help_text=(
            'Como se registran los extractos bancarios '
            '(Odoo bank_statements_source).'
        ),
    )
    bank_acc_number = fields.Char(
        'Bank Account Number',
        related='bank_account_id.acc_number',
        readonly=False,
    )
    #: Forma N de ADR-029: ``related`` sin columna. El ``store=False`` es
    #: explicito porque el gate lo mide, no lo infiere del ``related``.
    bank_id = fields.Many2one(
        'base.ResBank',
        related='bank_account_id.bank',
        readonly=False,
        store=False,
        verbose_name='Bank',
        help_text='Banco (Odoo bank_id).',
    )

    #: ≙ ``inbound_payment_method_line_ids`` / ``outbound_…``
    #: (``odoo19c: addons/account/models/account_journal.py:205-233``):
    #: One2many calculados y almacenados sobre la línea, separados por el
    #: ``payment_type`` del método. Almacenar aquí es que la línea guarda
    #: el diario: el diario no lleva columna.
    inbound_payment_method_line_ids = fields.One2many(
        'account.AccountPaymentMethodLine', 'journal',
        domain=[('payment_type', '=', 'inbound')],
        compute='_compute_inbound_payment_method_line_ids',
        store=True,
        readonly=False,
        copy=False,
        check_company=True,
        string='Inbound Payment Methods',
    )
    outbound_payment_method_line_ids = fields.One2many(
        'account.AccountPaymentMethodLine', 'journal',
        domain=[('payment_type', '=', 'outbound')],
        compute='_compute_outbound_payment_method_line_ids',
        store=True,
        readonly=False,
        copy=False,
        check_company=True,
        string='Outbound Payment Methods',
    )

    class Meta:
        db_table = 'account_journal'
        # ≙ ``_order = 'sequence, type, code'`` (odoo19c:
        # account_journal.py:45).
        ordering = ['sequence', 'type', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'],
                name='unique_journal_code_company',
            ),
        ]
        verbose_name = 'Diario contable'
        verbose_name_plural = 'Diarios contables'

    @classmethod
    def _get_bank_statements_available_sources(cls):
        """Los origenes de extracto que este arbol conoce.

        ≙ ``_get_bank_statements_available_sources``
        (``odoo19c: account_journal.py:68-69``), que delega en el privado de
        doble guion ``__get_bank_statements_available_sources`` (``:65-66``).
        La fuente separa los dos para que un addon extienda el publico sin
        tocar la lista base; aqui la separacion no aporta —el mangling de
        Python hace inalcanzable al privado desde una subclase— asi que el
        publico lleva la lista y es el punto de extension.

        **Divergencia de mecanismo declarada:** alla el metodo alimenta
        ``selection=`` del campo y se evalua por registro, asi que un addon
        instalado despues suma su origen. Aqui ``choices`` se resuelve al
        declarar la clase, de modo que el campo lleva la lista base y un addon
        que quiera sumar la suya lo hace sobre ``choices`` en su ``ready()``.
        El vocabulario es el mismo; lo que cambia es cuando se fija.
        """
        return [('undefined', 'Undefined Yet')]

    @classmethod
    def _get_next_journal_default_code(
        cls, journal_type, company, cache=None, protected_codes=None
    ):
        """El siguiente codigo libre para un diario de ese tipo.

        ≙ ``_get_next_journal_default_code``
        (``odoo19c: account_journal.py:884-899``), incluido su tope: el codigo
        mide 5 como maximo, asi que el sufijo no pasa de 99 y el bucle es
        ``range(1, 100)``. Devuelve ``None`` si los 99 estan tomados, igual
        que la fuente.

        ``cache`` son codigos que el llamador ya reservo en esta pasada y aun
        no estan en la base; ``protected_codes``, los que no se pueden usar
        aunque esten libres.
        """
        prefix_map = {
            'sale': 'INV',
            'purchase': 'BILL',
            'cash': 'CSH',
            'bank': 'BNK',
            'credit': 'CCD',
            'general': 'MISC',
        }
        journal_code_base = prefix_map.get(journal_type)
        if journal_code_base is None:
            return None
        domain = cls._check_company_domain(company)
        queryset = (
            cls.objects.all() if domain is None
            else cls.objects.filter(models.to_q(domain, cls))
        )
        existing_codes = set(
            queryset.filter(code__startswith=journal_code_base).values_list(
                'code', flat=True
            )
        ) | set(cache or [])
        for num in range(1, 100):
            journal_code = f'{journal_code_base}{num}'
            if journal_code in existing_codes:
                continue
            if protected_codes and journal_code in protected_codes:
                continue
            return journal_code
        return None

    def __str__(self) -> str:
        return f'{self.code} — {self.name}'

    def _default_inbound_payment_methods(self):
        """≙ ``_default_inbound_payment_methods``
        (``odoo19c: addons/account/models/account_journal.py:59-60``)."""
        return self.env.ref('account.account_payment_method_manual_in')

    def _default_outbound_payment_methods(self):
        """≙ ``_default_outbound_payment_methods`` (``:62-63``)."""
        return self.env.ref('account.account_payment_method_manual_out')

    @api.depends('type', 'currency')
    def _compute_inbound_payment_method_line_ids(self):
        """≙ ``_compute_inbound_payment_method_line_ids`` (``:462-482``):
        vaciar y crear una línea por método por defecto, conservando la
        cuenta de la línea anterior del mismo método si su moneda no choca
        con la del diario."""
        for journal in self:
            pay_method_line_ids_commands = [fields.Command.clear()]
            if journal.type in ('bank', 'cash', 'credit'):
                existing_method_lines = (
                    journal.inbound_payment_method_line_ids)
                default_methods = journal._default_inbound_payment_methods()
                for pay_method in default_methods:
                    same = existing_method_lines.filtered(
                        lambda m: m.payment_method_id == pay_method.id)
                    payment_account = (same[0].payment_account if same
                                       else None)
                    keep = payment_account and (
                        not payment_account.currency_id
                        or payment_account.currency_id
                        == journal.currency_id)
                    pay_method_line_ids_commands += [
                        fields.Command.create({
                            'name': pay_method.name,
                            'payment_method_id': pay_method.id,
                            'payment_account_id': (
                                payment_account.id if keep else False),
                        })
                    ]
            journal.inbound_payment_method_line_ids = (
                pay_method_line_ids_commands)

    @api.depends('type', 'currency')
    def _compute_outbound_payment_method_line_ids(self):
        """≙ ``_compute_outbound_payment_method_line_ids`` (``:484-504``):
        vaciar y crear una línea por método por defecto, conservando la
        cuenta de la línea anterior del mismo método si su moneda no choca
        con la del diario."""
        for journal in self:
            pay_method_line_ids_commands = [fields.Command.clear()]
            if journal.type in ('bank', 'cash', 'credit'):
                existing_method_lines = (
                    journal.outbound_payment_method_line_ids)
                default_methods = journal._default_outbound_payment_methods()
                for pay_method in default_methods:
                    same = existing_method_lines.filtered(
                        lambda m: m.payment_method_id == pay_method.id)
                    payment_account = (same[0].payment_account if same
                                       else None)
                    keep = payment_account and (
                        not payment_account.currency_id
                        or payment_account.currency_id
                        == journal.currency_id)
                    pay_method_line_ids_commands += [
                        fields.Command.create({
                            'name': pay_method.name,
                            'payment_method_id': pay_method.id,
                            'payment_account_id': (
                                payment_account.id if keep else False),
                        })
                    ]
            journal.outbound_payment_method_line_ids = (
                pay_method_line_ids_commands)

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: addons/account/models/
        account_journal.py:725-733``): borra las líneas de método de pago
        del diario con su ``unlink``, luego el diario, y después las cuentas
        bancarias que sólo usaban los diarios borrados."""
        bank_account_ids = []
        # ≙ ``self.mapped('bank_account_id')``, registro a registro: el
        # ``mapped`` relacional multi-registro sobre un comodelo de Django
        # es TASK-API-0401.
        used = {journal.bank_account_id.pk for journal in self
                if journal.bank_account_id}
        for bank_account_id in used:
            accounts = self.search(
                [('bank_account_id', '=', bank_account_id)])
            if accounts <= self:
                bank_account_ids.append(bank_account_id)
        self.env['account.payment.method.line'].search(
            [('journal_id', 'in', self.ids)]).unlink()
        ret = super().unlink()
        # ``res.partner.bank`` es un modelo de Django: su borrado lo emite
        # el ``Collector``, como en ``BaseModel.unlink``.
        apps.get_model('base', 'ResPartnerBank').objects.filter(
            pk__in=bank_account_ids).delete()
        return ret

    def _get_available_payment_method_lines(self, payment_type):
        """≙ ``_get_available_payment_method_lines``
        (``odoo19c: addons/account/models/account_journal.py:1188-1203``):
        las líneas de entrada o de salida del diario; vacío sin diario. Es
        el punto que los addons extienden (``account_payment`` filtra las
        pasarelas inactivas)."""
        if not self:
            return self.env['account.payment.method.line']
        self.ensure_one()
        if payment_type == 'inbound':
            return self.inbound_payment_method_line_ids
        return self.outbound_payment_method_line_ids
