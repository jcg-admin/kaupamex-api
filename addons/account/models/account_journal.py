"""``account.journal`` — diario contable (Odoo ``account``).

Portación fiel de ``account_journal.py`` (Odoo 18/19, ``type`` idéntico:
sale/purchase/cash/bank/credit/general). Campos núcleo: ``name``, ``code``,
``type``, ``currency``, ``default_account``, ``company``, ``active``.
"""
import fields
import models


class AccountJournal(models.Model):
    """``account.journal`` — diario donde se registran los asientos."""

    #: Los atributos de clase que la fuente declara
    #: (``odoo19c: account_journal.py:43-53``). Sin ``_name`` el diario NO
    #: entra en ``orm.registry.MODELS_BY_NAME``, y con el fuera ni
    #: ``linked_journal`` del asistente de banco resuelve su comodelo ni
    #: ``_check_company_auto`` tiene a quien preguntar (tarea #333).
    _name = 'account.journal'
    _description = 'Journal'
    _order = 'sequence, type, code'
    #: ≙ ``_inherit`` (``:46-50``), **verbatim**: nombra la extension aunque el
    #: mixin aun no exista, que es lo que manda
    #: ``atributos-de-clase-de-modelo.md`` para esta clave. Medido hoy:
    #: ``mail.thread`` y ``mail.activity.mixin`` SI estan
    #: (``addons/mail/models/mail_thread.py``); ``portal.mixin`` y
    #: ``mail.alias.mixin.optional`` NO — su porte es la tarea #163 (el hilo
    #: de mail sobre crm.team) y #161 (mail.alias.mixin) respectivamente.
    _inherit = ['portal.mixin',
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
    _check_company_domain = classmethod(
        models.check_company_domain_parent_of)
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

    name            = fields.Char(
        max_length=255, help_text='Nombre del diario (Odoo name, requerido).',
    )
    code            = fields.Char(
        max_length=12, help_text='Código corto del diario (Odoo code).',
    )
    type            = fields.Selection(
        max_length=12, choices=JOURNAL_TYPES,
        help_text='Tipo de diario (Odoo type, requerido).',
    )
    currency        = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='journals',
        help_text='Moneda del diario (Odoo currency_id).',
    )
    default_account = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='default_for_journals',
        help_text='Cuenta por defecto (Odoo default_account_id).',
    )
    company         = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='journals',
        help_text='Empresa (Odoo company_id).',
    )
    active          = fields.Boolean(
        default=True, help_text='Diario activo (Odoo active).',
    )
    sequence        = fields.Integer(
        default=10, help_text='Orden del diario (Odoo sequence).',
    )
    # ``show_on_dashboard`` y ``color`` los declara la referencia en
    # ``account_journal_dashboard.py:30-31``, un ``_inherit`` del **mismo**
    # addon. Se portan aquí —misma clase, mismo addon— porque el archivo
    # aparte de allá es una separación de lectura, no de modelo; el resto de
    # ese archivo (la agregación del tablero) queda pendiente, sucesor #158.
    show_on_dashboard = fields.Boolean(
        default=True, help_text='Mostrar en el tablero (Odoo show_on_dashboard).',
    )
    color           = fields.Integer(
        default=0, help_text='Índice de color (Odoo color).',
    )

    # Campos de diario bancario — ≙ ``odoo19c: account_journal.py:245-255``.
    # Los desbloquea la tarea #333: el asistente de alta manual de cuenta
    # (``account.setup.bank.manual.config``) liga la cuenta al diario por
    # ``bank_account``, y sin el campo su ``set_linked_journal_id`` no podia
    # hacer lo que la fuente hace.
    company_partner = fields.Many2one(
        'base.ResPartner', related='company.partner', store=False,
        verbose_name='Account Holder',
        help_text='Titular de la cuenta (Odoo company_partner_id).',
    )
    #: Forma C de ADR-029 (#141): el simbolo lleva el ``_id`` de la fuente Y
    #: la columna tambien. Las FK de arriba son forma A —deuda congelada que
    #: barre #143—; una declaracion NUEVA no la ensancha.
    bank_account_id = fields.Many2one(
        'base.ResPartnerBank', on_delete=models.RESTRICT, null=True, blank=True,
        db_index=True, db_column='bank_account_id', related_name='journals',
        verbose_name='Bank Account',
        help_text='Cuenta bancaria del diario (Odoo bank_account_id).',
    )
    #: ≙ ``bank_statements_source`` (``:253``). Su ``selection`` allá es el
    #: metodo ``_get_bank_statements_available_sources``, que un addon extiende
    #: para anadir su origen; aqui las opciones se resuelven al declarar la
    #: clase, asi que la lista base vive en el metodo y el campo la consume.
    bank_statements_source = fields.Selection(
        max_length=32, default='undefined', verbose_name='Bank Feeds',
        choices=[('undefined', 'Undefined Yet')],
        help_text='Como se registran los extractos bancarios '
                  '(Odoo bank_statements_source).',
    )
    bank_acc_number = fields.Char(
        'Bank Account Number', related='bank_account_id.acc_number',
        readonly=False)
    #: Forma N de ADR-029: ``related`` sin columna. El ``store=False`` es
    #: explicito porque el gate lo mide, no lo infiere del ``related``.
    bank_id         = fields.Many2one(
        'base.ResBank', related='bank_account_id.bank', readonly=False,
        store=False, verbose_name='Bank', help_text='Banco (Odoo bank_id).',
    )

    class Meta:
        db_table = 'account_journal'
        # ≙ ``_order = 'sequence, type, code'`` (odoo19c: account_journal.py:45).
        ordering = ['sequence', 'type', 'code']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'code'], name='unique_journal_code_company',
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
    def _get_next_journal_default_code(cls, journal_type, company,
                                       cache=None, protected_codes=None):
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
        queryset = cls.objects.all() if domain is None else cls.objects.filter(domain)
        existing_codes = set(
            queryset.filter(code__startswith=journal_code_base)
            .values_list('code', flat=True)
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
