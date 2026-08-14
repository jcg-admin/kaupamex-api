"""``account.fiscal.position.account`` — mapeo de cuentas de una posición
fiscal (Odoo ``account``).

Adaptación de Odoo addons/account/models/partner.py
(odoo-tools@622ddc2aa5563d12295b4ab7d3eb438a43eb31de, odoo19c:, LGPL-3),
clase ``AccountFiscalPositionAccount`` (odoo19c: partner.py:300-315).

Fiel: ``position`` (FK cascade), ``company`` (Odoo
``related='position_id.company_id', store=True`` — aquí resuelto en
``save()``), ``account_src``, ``account_dest`` (ambas requeridas),
único ``(position, account_src, account_dest)`` (Odoo
``_account_src_dest_uniq``).
"""
import fields
import models


class AccountFiscalPositionAccount(models.Model):
    """``account.fiscal.position.account`` — cuenta origen → cuenta destino."""

    position     = fields.Many2one(
        'account.AccountFiscalPosition', on_delete=models.CASCADE, related_name='account_ids',
        help_text='Posición fiscal dueña de este mapeo (Odoo position_id, requerido).',
    )
    company       = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, null=True, blank=True,
        related_name='fiscal_position_accounts',
        help_text='Empresa (Odoo company_id, related=position_id.company_id, store=True).',
    )
    account_src    = fields.Many2one(
        'account.AccountAccount', on_delete=models.CASCADE, related_name='fiscal_position_mappings_src',
        help_text='Cuenta declarada en el producto (Odoo account_src_id, requerido).',
    )
    account_dest    = fields.Many2one(
        'account.AccountAccount', on_delete=models.CASCADE, related_name='fiscal_position_mappings_dest',
        help_text='Cuenta a usar en su lugar (Odoo account_dest_id, requerido).',
    )

    class Meta:
        db_table = 'account_fiscal_position_account'
        constraints = [
            models.UniqueConstraint(
                fields=['position', 'account_src', 'account_dest'],
                name='unique_fiscal_position_account_src_dest',
            ),
        ]
        verbose_name = 'Mapeo de cuenta de posición fiscal'
        verbose_name_plural = 'Mapeos de cuenta de posición fiscal'

    def __str__(self) -> str:
        return f'{self.position} · {self.account_src} → {self.account_dest}'

    def save(self, *args, **kwargs):
        if self.position_id is not None and self.company_id is None:
            self.company = self.position.company
        return super().save(*args, **kwargs)
