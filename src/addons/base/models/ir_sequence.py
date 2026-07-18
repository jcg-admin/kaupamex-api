"""``ir.sequence` — generador de secuencias numéricas (Odoo ``base``).

Portación fiel de ``IrSequence`` (``ir_sequence.py`` de Odoo 18/19). NO es
framework-UI: es la **estructura de control** de numeración que tiene Odoo
(prefijo/sufijo interpolados por fecha, padding, paso de incremento, per-empresa),
usada por facturas, pickings, órdenes. Se porta para tener ese control sobre
Django (que no expone un generador equivalente como dato editable en caliente).

Cross-app: ``company`` → ``company.Company``.

Alcance de esta portación: implementación ``standard``/``no_gap`` como contador
en la fila (``number_next``); la variante PostgreSQL-sequence de Odoo
(``_predict_nextval``) no aplica en MariaDB — el contador vive en la fila.
Interpolación de fecha: se portan los tokens comunes (``%(year)s`` ``%(y)s``
``%(month)s`` ``%(day)s`` ``%(doy)s`` ``%(woy)s``); el resto queda documentado.
"""
from django.db import models
from django.utils import timezone


class IrSequence(models.Model):
    """``ir.sequence`` — secuencia con prefijo/sufijo/padding e incremento."""

    IMPLEMENTATIONS = [('standard', 'Standard'), ('no_gap', 'No gap')]

    name           = models.CharField(max_length=128, help_text='Nombre (Odoo name).')
    code           = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Código de la secuencia (Odoo code).',
    )
    implementation = models.CharField(
        max_length=16, choices=IMPLEMENTATIONS, default='standard',
        help_text='Standard o No gap (Odoo implementation).',
    )
    active         = models.BooleanField(default=True, help_text='Odoo active.')
    prefix         = models.CharField(
        max_length=128, blank=True, default='',
        help_text='Prefijo, interpolable por fecha (Odoo prefix).',
    )
    suffix         = models.CharField(
        max_length=128, blank=True, default='',
        help_text='Sufijo, interpolable por fecha (Odoo suffix).',
    )
    number_next    = models.IntegerField(
        default=1, help_text='Próximo número (Odoo number_next).',
    )
    number_increment = models.IntegerField(
        default=1, help_text='Paso de incremento (Odoo number_increment / Step).',
    )
    padding        = models.IntegerField(
        default=0, help_text='Ancho con ceros a la izquierda (Odoo padding).',
    )
    use_date_range = models.BooleanField(
        default=False, help_text='Subsecuencias por rango de fecha (Odoo use_date_range).',
    )
    company        = models.ForeignKey(
        'company.Company', on_delete=models.CASCADE, related_name='sequences',
        null=True, blank=True, help_text='Empresa (Odoo company_id).',
    )

    class Meta:
        db_table = 'ir_sequence'
        ordering = ['name', 'id']
        verbose_name = 'Secuencia'
        verbose_name_plural = 'Secuencias'

    def __str__(self) -> str:
        return f'{self.name}{" [" + self.code + "]" if self.code else ""}'

    # -- Odoo _get_prefix_suffix + _next ----------------------------------
    def _interpolation_dict(self, for_date=None):
        """Tokens de fecha para prefijo/sufijo (Odoo ``_interpolation_dict``)."""
        d = for_date or timezone.now().date()
        return {
            'year': '%04d' % d.year,
            'y': '%02d' % (d.year % 100),
            'month': '%02d' % d.month,
            'day': '%02d' % d.day,
            'doy': '%03d' % d.timetuple().tm_yday,
            'woy': '%02d' % d.isocalendar()[1],
            'weekday': str(d.isoweekday()),
        }

    @staticmethod
    def _interpolate(fragment, tokens):
        # Odoo usa ``s % d`` con claves ``%(year)s``; replica el mismo formato.
        return (fragment or '') % tokens if fragment else ''

    def get_next(self, for_date=None):
        """Devuelve el siguiente valor formateado e incrementa (Odoo ``_next``).

        ``prefijo_interpolado + numero_con_padding + sufijo_interpolado``; luego
        ``number_next += number_increment``. Devuelve el string generado.
        """
        tokens = self._interpolation_dict(for_date)
        prefix = self._interpolate(self.prefix, tokens)
        suffix = self._interpolate(self.suffix, tokens)
        number = self.number_next
        formatted = '%s%%0%sd%s' % (prefix, self.padding, suffix) % number
        self.number_next = number + self.number_increment
        self.save(update_fields=['number_next'])
        return formatted
