"""``res.bank`` — instituciones bancarias (Odoo ``base``).

Portación fiel de ``ResBank`` (``res_bank.py`` de Odoo 18/19). El banco como
institución (con su BIC/SWIFT y dirección), distinto de la cuenta bancaria
(``res.partner.bank``, cuya validación IBAN vive en el addon ``base_bank``).

Cross-app: ``country`` → ``base.ResCountry``; ``state`` → ``base.ResCountryState``.
"""
import fields
import models


class ResBank(models.Model):
    """``res.bank`` — banco (institución) con su BIC y dirección."""

    name         = fields.Char(max_length=128, help_text='Nombre del banco (Odoo name).')
    bic          = fields.Char(
        max_length=16, blank=True, default='',
        help_text='Bank Identifier Code / SWIFT (Odoo bic).',
    )
    street       = fields.Char(max_length=128, blank=True, default='', help_text='Odoo street.')
    street2      = fields.Char(max_length=128, blank=True, default='', help_text='Odoo street2.')
    zip          = fields.Char(max_length=24, blank=True, default='', help_text='Odoo zip.')
    city         = fields.Char(max_length=128, blank=True, default='', help_text='Odoo city.')
    state        = fields.Many2one(
        'base.ResCountryState', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='Estado/provincia (Odoo state).',
    )
    country      = fields.Many2one(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='País (Odoo country).',
    )
    email        = fields.Char(max_length=254, blank=True, default='', help_text='Odoo email.')
    phone        = fields.Char(max_length=32, blank=True, default='', help_text='Odoo phone.')
    active       = fields.Boolean(default=True, help_text='Odoo active.')

    class Meta:
        db_table = 'res_bank'
        ordering = ['name', 'id']
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'

    def __str__(self) -> str:
        return f'{self.name}{" - " + self.bic if self.bic else ""}'
