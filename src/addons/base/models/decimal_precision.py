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

    @classmethod
    def precision_get(cls, application: str) -> int:
        """Dígitos declarados para ``application``, o 2. ≙ ``precision_get``
        (``odoo19c: odoo/addons/base/models/decimal_precision.py:23-27``).

        La referencia baja a SQL crudo (``select digits from decimal_precision
        where name=%s``) precedido de un ``flush_model``, porque su ORM difiere
        las escrituras y el valor recién puesto no estaría en la tabla. Aquí no
        hay cola que vaciar —Django escribe al ejecutar—, así que el
        ``flush_model`` no tiene contraparte y la consulta se hace por el ORM.
        El fallback a **2** se conserva verbatim: es el que hace que un uso no
        sembrado no reviente.
        """
        fila = cls.objects.filter(name=application).values_list('digits', flat=True).first()
        return fila if fila is not None else 2
