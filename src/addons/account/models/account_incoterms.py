"""``account.incoterms`` — Adaptación de Odoo addons/account/models/account_incoterms.py
(odoo-tools@622ddc2a, odoo19c:).

Catálogo de Incoterms (términos de comercio internacional): dividen costos y
responsabilidades de transporte entre comprador y vendedor. Campos núcleo:
``name``, ``code`` (3 caracteres), ``active``.
"""
import fields
import models


class AccountIncoterms(models.Model):
    """``account.incoterms`` — término de comercio internacional (Incoterm)."""

    name = fields.Char(
        max_length=255,
        help_text='Nombre del Incoterm (Odoo name, requerido, traducible).',
    )
    code = fields.Char(
        max_length=3,
        help_text='Código estándar del Incoterm, ej. "FOB" (Odoo code, '
                  'requerido).',
    )
    active = fields.Boolean(
        default=True,
        help_text='Ocultar sin eliminar (Odoo active).',
    )

    class Meta:
        db_table = 'account_incoterms'
        ordering = ['code']
        verbose_name = 'Incoterm'
        verbose_name_plural = 'Incoterms'

    def __str__(self) -> str:
        # Odoo _compute_display_name: '[CODE] Name'.
        return f'[{self.code}] {self.name}' if self.code else self.name
