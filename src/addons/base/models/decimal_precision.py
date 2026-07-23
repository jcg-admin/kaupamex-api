"""``decimal.precision`` — precisión decimal por dominio (Odoo ``base``).

Portación fiel de ``DecimalPrecision`` (``decimal_precision.py`` de Odoo 18/19).
Config global que fija cuántos decimales usa un grupo de campos (``Product Price``,
``Product Unit of Measure``, ``Account``…). Da el control de precisión que tiene
Odoo (``digits='Product Price'``) sobre Django.
"""
import fields
import models


class DecimalPrecision(models.Model):
    """``decimal.precision`` — dígitos decimales para un uso nombrado."""

    name   = fields.Char(
        max_length=128, unique=True,
        help_text='Uso (Odoo name, p. ej. "Product Price"). Único.',
    )
    digits = fields.Integer(
        default=2, help_text='Número de decimales (Odoo digits).',
    )

    class Meta:
        db_table = 'decimal_precision'
        ordering = ['name']
        verbose_name = 'Precisión decimal'
        verbose_name_plural = 'Precisiones decimales'

    def __str__(self) -> str:
        return f'{self.name}: {self.digits}'
