"""``account.payment.method`` / ``account.payment.method.line`` — métodos de
pago (Odoo ``account``).

Adaptación de Odoo ``addons/account/models/account_payment_method.py``
(``odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de``, ``odoo19c:``).

Dos modelos, como en la referencia:

- ``AccountPaymentMethod``: catálogo de métodos disponibles (``code`` +
  ``payment_type``, único). Núcleo portado: ``name``, ``code``,
  ``payment_type``, ``_get_payment_method_information`` (sólo el caso base
  ``manual``) y ``unlink``/``delete`` en cascada sobre sus líneas.
- ``AccountPaymentMethodLine``: instancia del método en un diario concreto
  (``payment_method``, ``journal``, ``payment_account``, ``sequence``,
  ``name`` computado).

No portado (declarado, no improvisado):

- ``create()`` + ``_auto_link_payment_methods``: el auto-alta de una línea por
  cada diario elegible al crear un método ``mode='multi'``. Depende de
  ``_get_payment_method_domain`` (moneda/país del diario), que este núcleo no
  modela — ``AccountJournal`` no tiene ``currency_ids``/país fiscal derivado.
- ``_get_payment_method_domain``: el filtro de diarios elegibles por
  ``currency_ids``/``country_id`` de la referencia. Sin datos de moneda/país
  por método, el dominio quedaría vacío o trivial; se documenta en vez de
  fabricar un criterio sin respaldo.
- ``available_payment_method_ids`` (related de ``journal.available_payment_
  method_ids``): campo de UI para acotar el dominio del selector en el
  formulario del diario — no hay modelo de "métodos disponibles por diario"
  portado.
- ``_check_company_domain_parent_of`` / multicompañía jerárquica: el núcleo
  portado usa FK simple a ``base.ResCompany`` (vía ``journal``), sin jerarquía
  padre-hijo de compañías (Odoo ``check_company_domain_parent_of``).
- ``_auto_toggle_account_to_reconcile`` y el hook SDD
  (``_get_sdd_payment_method_code``): utilidades de UI/onboarding sin
  consumidor en este núcleo.
"""

import api
import fields
import models
from addons.base.models import TimeStampedModel
from orm.domains import Domain


class AccountPaymentMethod(models.BaseModel, TimeStampedModel):
    """``account.payment.method`` — catálogo de métodos de pago disponibles."""

    #: Atributos de clase de ``account.payment.method``, verbatim
    #: (``odoo19c: account/models/account_payment_method.py:8-9``).
    _name = 'account.payment.method'
    _description = "Payment Methods"

    PAYMENT_TYPES = [
        ('inbound', 'Entrante'),
        ('outbound', 'Saliente'),
    ]

    name = fields.Char(
        max_length=255,
        help_text='Nombre del método (Odoo name, requerido).',
    )
    code = fields.Char(
        max_length=64,
        help_text='Identificación interna (Odoo code, requerido).',
    )
    payment_type = fields.Selection(
        max_length=8,
        choices=PAYMENT_TYPES,
        help_text='Tipo de pago (Odoo payment_type, requerido).',
    )

    class Meta:
        db_table = 'account_payment_method'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['code', 'payment_type'],
                name='unique_payment_method_code_type',
            ),
        ]
        verbose_name = 'Método de pago'
        verbose_name_plural = 'Métodos de pago'

    def __str__(self) -> str:
        return f'{self.name} ({self.payment_type})'

    @classmethod
    def create(cls, vals_list):
        """≙ ``create`` (``odoo19c: addons/account/models/
        account_payment_method.py:20-24``): tras crear, enlaza cada método
        ``multi`` a los diarios que pueden alojarlo."""
        payment_methods = super().create(vals_list)
        methods_info = payment_methods._get_payment_method_information()
        return payment_methods._auto_link_payment_methods(payment_methods,
                                                          methods_info)

    def _auto_link_payment_methods(self, payment_methods, methods_info):
        """≙ ``_auto_link_payment_methods`` (``:26-38``): una línea por
        diario elegible para cada método de modo ``multi``."""
        for method in payment_methods:
            information = methods_info.get(method.code, {})
            if information.get('mode') == 'multi':
                method_domain = method._get_payment_method_domain(method.code)
                journals = self.env['account.journal'].search(method_domain)
                self.env['account.payment.method.line'].create([{
                    'name': method.name,
                    'payment_method_id': method.id,
                    'journal_id': journal.id,
                } for journal in journals])
        return payment_methods

    @api.model
    def _get_payment_method_domain(self, code, with_currency=True,
                                   with_country=True):
        """≙ ``_get_payment_method_domain`` (``odoo19c: addons/account/
        models/account_payment_method.py:40-61``): el dominio de los diarios
        que pueden alojar el método de código ``code``.

        Sin código, ``Domain.TRUE``. Si no, ``type`` en los tipos que declara
        la información del código (bank, cash y credit por defecto), más la
        moneda y el país cuando la información los declara.
        """
        if not code:
            return Domain.TRUE
        information = self._get_payment_method_information().get(code)
        journal_types = information.get('type', ('bank', 'cash', 'credit'))
        domain = Domain('type', 'in', journal_types)

        if with_currency and (currency_ids := information.get(
                'currency_ids')):
            domain &= (
                Domain('currency_id', '=', False)
                & Domain('company_id.currency_id', 'in', currency_ids)
            ) | Domain('currency_id', 'in', currency_ids)

        if with_country and (country_id := information.get('country_id')):
            domain &= Domain('company_id.account_fiscal_country_id', '=',
                             country_id)

        return domain

    @api.model
    def _get_payment_method_information(self):
        """
        Info de inicialización por código (Odoo
        ``_get_payment_method_information``).

        Sólo el caso base ``manual`` (``mode`` multi, sin restricción de
        moneda/país) — los métodos electrónicos de proveedores de pago no
        están portados en este núcleo.
        """
        return {
            'manual': {'mode': 'multi', 'type': ('bank', 'cash', 'credit')},
        }

    def unlink(self):
        """≙ ``unlink`` (``odoo19c: addons/account/models/
        account_payment_method.py:90-92``): borra sus líneas con su propio
        ``unlink`` antes de borrarse. La clave ``payment_method`` es
        ``restrict``, así que un ``DELETE`` sin este paso se rehúsa.
        """
        AccountPaymentMethodLine.search(
            [('payment_method', 'in', self.ids)]).unlink()
        return super().unlink()


class AccountPaymentMethodLine(models.BaseModel, TimeStampedModel):
    """
    ``account.payment.method.line`` — método de pago habilitado en un diario.
    """

    #: Atributos de clase de ``account.payment.method.line``, verbatim
    #: (``odoo19c: account/models/account_payment_method.py:96-98``).
    _name = 'account.payment.method.line'
    _description = "Payment Methods"
    _order = 'sequence, id'

    name = fields.Char(
        max_length=255,
        blank=True,
        default='',
        help_text='Nombre visible (Odoo name, computado del método si vacío).',
        compute='_compute_name',
        store=True,
        readonly=False,
    )
    sequence = fields.Integer(
        default=10,
        help_text='Orden de presentación (Odoo sequence).',
    )
    payment_method = fields.Many2one(
        'account.AccountPaymentMethod',
        null=False, on_delete=models.PROTECT,
        related_name='method_line_ids',
        help_text='Método de pago (Odoo payment_method_id, requerido).',
    )
    payment_account = fields.Many2one(
        'account.AccountAccount',
        on_delete=models.PROTECT,
        related_name='payment_method_lines',
        null=True,
        blank=True,
        help_text='Cuenta de contrapartida (Odoo payment_account_id).',
    )
    journal = fields.Many2one(
        'account.AccountJournal',
        on_delete=models.SET_NULL,
        related_name='payment_method_lines',
        null=True,
        blank=True,
        help_text='Diario donde queda habilitado (Odoo journal_id).',
    )

    class Meta:
        db_table = 'account_payment_method_line'
        ordering = ['sequence', 'id']
        verbose_name = 'Línea de método de pago'
        verbose_name_plural = 'Líneas de método de pago'

    def __str__(self) -> str:
        journal_code = self.journal.code if self.journal_id else '-'
        return f'{self.name} ({journal_code})'

    #: Forma N de ADR-029: relacionados sin columna, con el nombre de la
    #: fuente (``odoo19c: addons/account/models/account_payment_method.py:
    #: 122-129``). Como campos, y no ``property``, entran en un dominio: el
    #: del diario filtra las líneas por ``payment_type``.
    default_account_id = fields.Many2one(
        'account.AccountAccount',
        related='journal.default_account',
        store=False,
        help_text='Cuenta por defecto del diario (Odoo default_account_id).',
    )
    code = fields.Char(
        related='payment_method.code',
        store=False,
        help_text='Código del método (Odoo code).',
    )
    payment_type = fields.Selection(
        related='payment_method.payment_type',
        store=False,
        help_text='Tipo del método (Odoo payment_type).',
    )
    company_id = fields.Many2one(
        'base.ResCompany',
        related='journal.company',
        store=False,
        help_text='Empresa del diario (Odoo company_id).',
    )

    @api.depends('payment_method.name')
    def _compute_name(self):
        """Nombre por defecto = nombre del método (Odoo ``_compute_name``)."""
        if not self.name:
            self.name = self.payment_method.name

    def save(self, *args, **kwargs):
        self._compute_name()
        return super().save(*args, **kwargs)
