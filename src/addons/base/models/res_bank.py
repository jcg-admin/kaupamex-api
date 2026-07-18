"""``res.bank`` — instituciones bancarias (Odoo ``base``).

Portación fiel de ``ResBank`` (``res_bank.py`` de Odoo 18/19). El banco como
institución (con su BIC/SWIFT y dirección), distinto de la cuenta bancaria
(``res.partner.bank``, cuya validación IBAN vive en el addon ``base_bank``).

Cross-app: ``country`` → ``base.ResCountry``; ``state`` → ``base.ResCountryState``.
"""
from django.db import models


class ResBank(models.Model):
    """``res.bank`` — banco (institución) con su BIC y dirección."""

    name         = models.CharField(max_length=128, help_text='Nombre del banco (Odoo name).')
    bic          = models.CharField(
        max_length=16, blank=True, default='',
        help_text='Bank Identifier Code / SWIFT (Odoo bic).',
    )
    street       = models.CharField(max_length=128, blank=True, default='', help_text='Odoo street.')
    street2      = models.CharField(max_length=128, blank=True, default='', help_text='Odoo street2.')
    zip          = models.CharField(max_length=24, blank=True, default='', help_text='Odoo zip.')
    city         = models.CharField(max_length=128, blank=True, default='', help_text='Odoo city.')
    state        = models.ForeignKey(
        'base.ResCountryState', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='Estado/provincia (Odoo state).',
    )
    country      = models.ForeignKey(
        'base.ResCountry', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='banks', help_text='País (Odoo country).',
    )
    email        = models.CharField(max_length=254, blank=True, default='', help_text='Odoo email.')
    phone        = models.CharField(max_length=32, blank=True, default='', help_text='Odoo phone.')
    active       = models.BooleanField(default=True, help_text='Odoo active.')

    class Meta:
        db_table = 'res_bank'
        ordering = ['name', 'id']
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'

    def __str__(self) -> str:
        return f'{self.name}{" - " + self.bic if self.bic else ""}'
