"""``account.tax.repartition.line`` — línea de reparto de un impuesto (Odoo
``account``).

Adaptación de Odoo addons/account/models/account_tax.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3),
clase ``AccountTaxRepartitionLine`` (odoo19c: account_tax.py:5240-5308).

Un ``account.tax`` no se cobra a una sola cuenta: se reparte en líneas
(base/impuesto × factura/nota de crédito), cada una con su cuenta destino y
sus etiquetas de reporte (``tag_ids``, Odoo "casillas fiscales"). Es el
prerrequisito de ``account_update_tax_tags`` (bloqueado hasta este port).

Campos núcleo portados: ``factor_percent``, ``factor`` (computado,
``save()``), ``repartition_type``, ``document_type``, ``account`` (FK
opcional — nulo cuando ``repartition_type='base'``, Odoo
``_onchange_repartition_type``), ``tag_ids`` (M2M a ``account.account.tag``),
``tax`` (FK, cascade), ``company`` (Odoo ``related='tax_id.company_id',
store=True`` — aquí resuelto en ``save()``), ``sequence``,
``use_in_tax_closing`` (computado, ``save()``).

NO se porta: ``tag_ids_domain`` (dominio dinámico para el widget de
selección en el cliente web de Odoo, sin análogo en DRF) ni
``_get_aml_target_tax_account`` con ``force_caba_exigibility``/
``cash_basis_transition_account_id`` (cash basis — ``tax_exigibility`` no
está portado en ``AccountTax``; queda declarado como pendiente, no
fabricado).
"""
import fields
import models


class AccountTaxRepartitionLine(models.Model):
    """``account.tax.repartition.line`` — reparto de un impuesto por cuenta."""

    REPARTITION_TYPES = [
        ('base', 'Base'),
        ('tax', 'Del impuesto'),
    ]
    DOCUMENT_TYPES = [
        ('invoice', 'Factura'),
        ('refund', 'Nota de crédito'),
    ]

    factor_percent      = fields.Float(
        default=100,
        help_text='Porcentaje del factor aplicado a los apuntes generados (Odoo factor_percent).',
    )
    factor               = fields.Float(
        default=1.0,
        help_text='Factor en fracción (Odoo factor, compute=_compute_factor; resuelto en save()).',
    )
    repartition_type      = fields.Selection(
        max_length=8, choices=REPARTITION_TYPES, default='tax',
        help_text='Base sobre la que se aplica el factor (Odoo repartition_type, requerido).',
    )
    document_type          = fields.Selection(
        max_length=8, choices=DOCUMENT_TYPES,
        help_text='Factura o nota de crédito (Odoo document_type, requerido).',
    )
    account                 = fields.Many2one(
        'account.AccountAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_repartition_lines',
        help_text=(
            'Cuenta donde se postea el monto de impuesto (Odoo account_id). '
            'Vacía cuando repartition_type=base, igual que el _onchange de '
            'la referencia.'
        ),
    )
    tag_ids                  = fields.Many2many(
        'account.AccountAccountTag', related_name='tax_repartition_lines', blank=True,
        db_table='account_tax_repartition_line_tag_rel',
        help_text='Casillas fiscales asociadas (Odoo tag_ids, domain applicability=taxes).',
    )
    tax                        = fields.Many2one(
        'account.AccountTax', on_delete=models.CASCADE, related_name='repartition_lines',
        help_text='Impuesto al que pertenece esta línea (Odoo tax_id).',
    )
    company                     = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='tax_repartition_lines',
        help_text='Empresa (Odoo company_id, related=tax_id.company_id, store=True).',
    )
    sequence                     = fields.Integer(
        default=1,
        help_text=(
            'Orden de presentación/emparejamiento (Odoo sequence). Para que '
            'las notas de crédito casen bien con la factura, el orden debe '
            'coincidir entre document_type=invoice y document_type=refund.'
        ),
    )
    use_in_tax_closing             = fields.Boolean(
        default=False,
        help_text='Entra en el asiento de cierre de IVA (Odoo use_in_tax_closing, compute; resuelto en save()).',
    )

    class Meta:
        db_table = 'account_tax_repartition_line'
        ordering = ['document_type', 'repartition_type', 'sequence', 'id']
        verbose_name = 'Línea de reparto de impuesto'
        verbose_name_plural = 'Líneas de reparto de impuesto'

    def __str__(self) -> str:
        return f'{self.tax} · {self.document_type}/{self.repartition_type} ({self.factor_percent}%)'

    def _compute_factor(self):
        """Factor en fracción — Odoo ``_compute_factor`` (odoo19c: 5288-5291)."""
        self.factor = (self.factor_percent or 0) / 100.0

    def _compute_use_in_tax_closing(self):
        """Entra en el cierre de IVA — Odoo ``_compute_use_in_tax_closing``
        (odoo19c: 5279-5286): sólo líneas ``repartition_type=tax`` con cuenta
        cuyo grupo interno no sea ingreso/gasto (i.e. cuentas de balance:
        IVA por cobrar/pagar, no cuentas de resultados)."""
        self.use_in_tax_closing = bool(
            self.repartition_type == 'tax'
            and self.account_id is not None
            and self.account.internal_group not in ('income', 'expense')
        )

    def save(self, *args, **kwargs):
        if self.tax_id is not None and self.company_id is None:
            self.company = self.tax.company
        self._compute_factor()
        self._compute_use_in_tax_closing()
        return super().save(*args, **kwargs)
