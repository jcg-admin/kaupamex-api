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


class AccountPaymentMethod(models.Model):
    """``account.payment.method`` — catálogo de métodos de pago disponibles."""

    PAYMENT_TYPES = [
        ('inbound', 'Entrante'),
        ('outbound', 'Saliente'),
    ]

    name         = fields.Char(
        max_length=255, help_text='Nombre del método (Odoo name, requerido).',
    )
    code         = fields.Char(
        max_length=64,
        help_text='Identificación interna (Odoo code, requerido).',
    )
    payment_type = fields.Selection(
        max_length=8, choices=PAYMENT_TYPES,
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

    @api.model
    def _get_payment_method_information(self):
        """Info de inicialización por código (Odoo ``_get_payment_method_information``).

        Sólo el caso base ``manual`` (``mode`` multi, sin restricción de
        moneda/país) — los métodos electrónicos de proveedores de pago no
        están portados en este núcleo.
        """
        return {
            'manual': {'mode': 'multi', 'type': ('bank', 'cash', 'credit')},
        }

    def delete(self, *args, **kwargs):
        """Borra sus líneas antes de borrarse (Odoo ``unlink``)."""
        self.method_line_ids.all().delete()
        return super().delete(*args, **kwargs)


class AccountPaymentMethodLine(models.Model):
    """``account.payment.method.line`` — método de pago habilitado en un diario."""

    name              = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Nombre visible (Odoo name, computado del método si vacío).',
    )
    sequence          = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    payment_method    = fields.Many2one(
        'account.AccountPaymentMethod', on_delete=models.CASCADE,
        related_name='method_line_ids',
        help_text='Método de pago (Odoo payment_method_id, requerido).',
    )
    payment_account   = fields.Many2one(
        'account.AccountAccount', on_delete=models.PROTECT,
        related_name='payment_method_lines', null=True, blank=True,
        help_text='Cuenta de contrapartida (Odoo payment_account_id).',
    )
    journal           = fields.Many2one(
        'account.AccountJournal', on_delete=models.CASCADE,
        related_name='payment_method_lines', null=True, blank=True,
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

    # -- Odoo related fields (code, payment_type, company) — vía FK ----------
    @property
    def code(self):
        """Odoo ``code`` (``related="payment_method_id.code"``)."""
        return self.payment_method.code

    @property
    def payment_type(self):
        """Odoo ``payment_type`` (``related="payment_method_id.payment_type"``)."""
        return self.payment_method.payment_type

    @property
    def company(self):
        """Odoo ``company_id`` (``related="journal_id.company_id"``)."""
        return self.journal.company if self.journal_id else None

    @property
    def default_account(self):
        """Odoo ``default_account_id`` (``related="journal_id.default_account_id"``)."""
        return self.journal.default_account if self.journal_id else None

    @api.depends('payment_method.name')
    def _compute_name(self):
        """Nombre por defecto = nombre del método (Odoo ``_compute_name``)."""
        if not self.name:
            self.name = self.payment_method.name

    def save(self, *args, **kwargs):
        self._compute_name()
        return super().save(*args, **kwargs)
