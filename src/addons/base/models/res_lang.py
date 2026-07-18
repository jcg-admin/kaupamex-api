"""``res.lang`` — idiomas/locales (Odoo ``base``).

Portación fiel de ``res_lang.py`` (Odoo 18/19). Catálogo de idiomas con su
locale, formatos de fecha/hora, separadores y agrupamiento numérico. Es config
de dominio (no framework-UI): da el control de localización que tiene Odoo
(``lang.grouping``, ``decimal_point``, ``week_start``), sobre Django.
"""
from django.db import models


class ResLang(models.Model):
    """``res.lang`` — idioma/locale con sus formatos de presentación."""

    DIRECTIONS = [('ltr', 'Left-to-Right'), ('rtl', 'Right-to-Left')]
    TIME_FORMATS = [('%H:%M:%S', '13:00:00'), ('%I:%M:%S %p', ' 1:00:00 PM')]
    WEEK_STARTS = [
        ('1', 'Monday'), ('2', 'Tuesday'), ('3', 'Wednesday'), ('4', 'Thursday'),
        ('5', 'Friday'), ('6', 'Saturday'), ('7', 'Sunday'),
    ]
    GROUPINGS = [('[3,0]', 'International Grouping'), ('[3,2,0]', 'Indian Grouping')]

    name         = models.CharField(max_length=64, help_text='Nombre del idioma (Odoo name).')
    code         = models.CharField(
        max_length=16, unique=True,
        help_text='Locale code (Odoo code, p. ej. es_MX). Único.',
    )
    iso_code     = models.CharField(
        max_length=16, blank=True, default='',
        help_text='ISO code — nombre del .po de traducción (Odoo iso_code).',
    )
    url_code     = models.CharField(
        max_length=16, help_text='Código en la URL (Odoo url_code).',
    )
    active       = models.BooleanField(default=False, help_text='Odoo active.')
    direction    = models.CharField(
        max_length=3, choices=DIRECTIONS, default='ltr',
        help_text='Dirección de escritura (Odoo direction).',
    )
    date_format  = models.CharField(
        max_length=32, default='%m/%d/%Y', help_text='Formato de fecha (Odoo date_format).',
    )
    time_format  = models.CharField(
        max_length=32, choices=TIME_FORMATS, default='%H:%M:%S',
        help_text='Formato de hora (Odoo time_format).',
    )
    week_start   = models.CharField(
        max_length=1, choices=WEEK_STARTS, default='7',
        help_text='Primer día de la semana (Odoo week_start).',
    )
    grouping     = models.CharField(
        max_length=16, choices=GROUPINGS, default='[3,0]',
        help_text='Formato de agrupamiento de miles (Odoo grouping).',
    )
    decimal_point = models.CharField(
        max_length=4, default='.', help_text='Separador decimal (Odoo decimal_point).',
    )
    thousands_sep = models.CharField(
        max_length=4, blank=True, default=',',
        help_text='Separador de miles (Odoo thousands_sep).',
    )

    class Meta:
        db_table = 'res_lang'
        ordering = ['-active', 'name']
        verbose_name = 'Idioma'
        verbose_name_plural = 'Idiomas'

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'
