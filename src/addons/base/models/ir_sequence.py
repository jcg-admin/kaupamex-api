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
import logging

from django.utils import timezone
import fields
import models

logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    """``ir.sequence`` — secuencia con prefijo/sufijo/padding e incremento."""

    IMPLEMENTATIONS = [('standard', 'Standard'), ('no_gap', 'No gap')]

    name           = fields.Char(max_length=128, help_text='Nombre (Odoo name).')
    code           = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Código de la secuencia (Odoo code).',
    )
    implementation = fields.Char(
        max_length=16, choices=IMPLEMENTATIONS, default='standard',
        help_text='Standard o No gap (Odoo implementation).',
    )
    active         = fields.Boolean(default=True, help_text='Odoo active.')
    prefix         = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Prefijo, interpolable por fecha (Odoo prefix).',
    )
    suffix         = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Sufijo, interpolable por fecha (Odoo suffix).',
    )
    number_next    = fields.Integer(
        default=1, help_text='Próximo número (Odoo number_next).',
    )
    number_increment = fields.Integer(
        default=1, help_text='Paso de incremento (Odoo number_increment / Step).',
    )
    padding        = fields.Integer(
        default=0, help_text='Ancho con ceros a la izquierda (Odoo padding).',
    )
    use_date_range = fields.Boolean(
        default=False, help_text='Subsecuencias por rango de fecha (Odoo use_date_range).',
    )
    company        = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='sequences',
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

    @classmethod
    def next_by_code(cls, sequence_code: str, company=None, for_date=None):
        """Siguiente valor de la secuencia con ese código, o ``None``. ≙
        ``next_by_code`` (``odoo19c: odoo/addons/base/models/ir_sequence.py:279-292``).

        «Draw an interpolated string using a sequence with the requested code.
        If several sequences with the correct code are available to the user
        (multi-company cases), the one from the user's current company will be
        used.»

        Se conserva la desambiguación multi-empresa: se buscan las secuencias de
        la empresa dada **y** las globales (``company IS NULL``), ordenadas por
        empresa para que la propia gane sobre la global — el ``order='company_id'``
        de la fuente. Sin secuencia, la referencia registra un ``debug`` y
        devuelve ``False``; aquí devuelve ``None``, que es el vacío tipado de
        este stack (H-API-590: un ``False`` portado a un campo tipado miente).

        :param sequence_code: valor de ``code`` a buscar.
        :param company: empresa cuyo ``code`` tiene prioridad; ``None`` mira sólo
            las globales.
        :param for_date: fecha de interpolación de prefijo/sufijo.
        """
        qs = cls.objects.filter(code=sequence_code, active=True)
        qs = qs.filter(company__in=[company, None]) if company else qs.filter(company__isnull=True)
        secuencia = qs.order_by(models.F('company').desc(nulls_last=True), 'id').first()
        if secuencia is None:
            logger.debug(
                "No ir.sequence has been found for code '%s'. Please make sure "
                "a sequence is set for current company.", sequence_code,
            )
            return None
        return secuencia.get_next(for_date=for_date)
