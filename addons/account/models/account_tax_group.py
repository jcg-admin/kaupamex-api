"""``account.tax.group`` — grupo de impuestos (Odoo ``account``).

Adaptación de Odoo addons/account/models/account_tax.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3),
clase ``AccountTaxGroup`` (odoo19c: account_tax.py:26-63).

Campos núcleo portados: ``name``, ``sequence``, ``company``,
``tax_payable_account``/``tax_receivable_account``/
``advance_tax_payment_account`` (los tres FK a ``account.account``, usados
como contrapartida del asiento de cierre de IVA), ``country`` (Odoo
``country_id``, computado desde la empresa — aquí se resuelve en ``save()``
en vez de ``@api.depends`` + ``store=True``), ``preceding_subtotal``,
``pos_receipt_label``.

NO se porta: ``country_code`` (``related='country_id.code'`` — propiedad de
solo lectura trivial, se expone como ``@property``).
"""
import fields
import models


class AccountTaxGroup(models.Model):
    """``account.tax.group`` — agrupador de impuestos (Odoo ``account``)."""

    name                         = fields.Char(
        max_length=255, help_text='Nombre del grupo (Odoo name, requerido).',
    )
    sequence                     = fields.Integer(
        default=10, help_text='Orden de presentación (Odoo sequence).',
    )
    company                      = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='tax_groups',
        help_text='Empresa (Odoo company_id, requerido).',
    )
    tax_payable_account          = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_groups_payable',
        help_text=(
            'Cuenta de contrapartida del asiento de cierre cuando el saldo '
            'favorece a la autoridad fiscal (Odoo tax_payable_account_id).'
        ),
    )
    tax_receivable_account       = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_groups_receivable',
        help_text=(
            'Cuenta de contrapartida del asiento de cierre cuando el saldo '
            'favorece a la empresa (Odoo tax_receivable_account_id).'
        ),
    )
    advance_tax_payment_account  = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_groups_advance',
        help_text='Cuenta de anticipos considerada en el cierre (Odoo advance_tax_payment_account_id).',
    )
    country                      = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_groups',
        help_text=(
            'País de aplicación (Odoo country_id, compute desde la empresa; '
            'aquí resuelto en save(), ver _compute_country()).'
        ),
    )
    preceding_subtotal            = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta del subtotal previo al grupo (Odoo preceding_subtotal).',
    )
    pos_receipt_label             = fields.Char(
        max_length=255, blank=True, default='',
        help_text='Etiqueta en el ticket de punto de venta (Odoo pos_receipt_label).',
    )

    class Meta:
        db_table = 'account_tax_group'
        ordering = ['sequence', 'id']
        verbose_name = 'Grupo de impuestos'
        verbose_name_plural = 'Grupos de impuestos'

    def __str__(self) -> str:
        return self.name

    def _compute_country(self):
        """País del grupo — Odoo ``_compute_country_id``: el país fiscal de la
        empresa, o su país si no declara uno fiscal específico.

        La referencia usa ``company_id.account_fiscal_country_id``; ese campo
        no está portado (requiere ``res.company`` con distinción moneda vs.
        país fiscal). Se usa ``company.country`` (propiedad ya portada en
        ``ResCompany``) como equivalente directo.
        """
        if self.company_id is not None:
            self.country = self.company.country

    def save(self, *args, **kwargs):
        if self.country_id is None:
            self._compute_country()
        return super().save(*args, **kwargs)
