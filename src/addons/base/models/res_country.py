"""``res.country`` / ``res.country.state`` — geografía política (Odoo ``base``).

Portación fiel de ``res_country.py`` (Odoo 18 / 19 idéntico). Espina base de la
adaptación de familias (SOL-096): direcciones/impuestos dependen de país+estado.
"""
import fields
import models


class ResCountry(models.Model):
    """``res.country`` — país (Odoo base).

    Fiel a ``res_country.py`` (18:32-68 / 19 idéntico): ``name`` (requerido),
    ``code`` (ISO 3166-1 alpha-2, único), ``currency`` (FK res.currency),
    ``phone_code``. ``state_ids`` es el reverso de ``ResCountryState.country``.
    """

    name        = fields.Char(
        max_length=120,
        help_text='Nombre del país (Odoo res.country.name).',
    )
    code        = fields.Char(
        max_length=2, unique=True, null=True, blank=True,
        help_text='Código ISO 3166-1 alpha-2 (Odoo code).',
    )
    currency    = fields.Many2one(
        'base.ResCurrency', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='countries',
        help_text='Moneda del país (Odoo currency_id).',
    )
    phone_code  = fields.Integer(
        null=True, blank=True,
        help_text='Código telefónico del país (Odoo phone_code).',
    )

    class Meta:
        db_table = 'res_country'
        ordering = ['name']
        verbose_name = 'País'
        verbose_name_plural = 'Países'

    def __str__(self) -> str:
        return self.name


class ResCountryState(models.Model):
    """``res.country.state`` — estado/provincia de un país (Odoo base).

    Fiel a ``res_country.py`` (18:162-171 / 19 idéntico): ``country`` (FK,
    requerido), ``name`` (requerido), ``code`` (requerido). Único (country, code)
    replica el ``_sql_constraints`` ``name_code_uniq`` de Odoo.
    """

    country = fields.Many2one(
        'base.ResCountry', on_delete=models.CASCADE, related_name='state_ids',
        help_text='País (Odoo country_id).',
    )
    name    = fields.Char(
        max_length=120, help_text='Nombre del estado (Odoo name).',
    )
    code    = fields.Char(
        max_length=8, help_text='Código del estado (Odoo code).',
    )

    class Meta:
        db_table = 'res_country_state'
        constraints = [
            models.UniqueConstraint(
                fields=['country', 'code'], name='unique_state_country_code',
            ),
        ]
        ordering = ['country', 'code']
        verbose_name = 'Estado / provincia'
        verbose_name_plural = 'Estados / provincias'

    def __str__(self) -> str:
        return f'{self.name} ({self.country.code})'
