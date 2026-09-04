"""``res.lang`` — idiomas/locales (Odoo ``base``).

Portación fiel de ``res_lang.py`` (Odoo 18/19). Catálogo de idiomas con su
locale, formatos de fecha/hora, separadores y agrupamiento numérico. Es config
de dominio (no framework-UI): da el control de localización que tiene Odoo
(``lang.grouping``, ``decimal_point``, ``week_start``), sobre Django.
"""
import ast
import re

from django.core.exceptions import ValidationError

import fields
import models
from tools.misc import DATETIME_FORMATS_MAP


class ResLang(models.Model):
    """``res.lang`` — idioma/locale con sus formatos de presentación."""

    _name = 'res.lang'
    _description = "Languages"
    _order = "active desc,name"
    _allow_sudo_commands = False

    #: Las directivas que ``strftime`` no sabe devolver a ``strptime``, y que
    #: por eso no pueden aparecer en un formato de ``res.lang``
    #: (≙ ``odoo19c: res_lang.py:55``). Es la lista de claves del mapa, no sus
    #: valores: lo que se prohíbe es la directiva de entrada.
    _disallowed_datetime_patterns = list(DATETIME_FORMATS_MAP)

    DIRECTIONS = [('ltr', 'Left-to-Right'), ('rtl', 'Right-to-Left')]
    TIME_FORMATS = [('%H:%M:%S', '13:00:00'), ('%I:%M:%S %p', ' 1:00:00 PM')]
    WEEK_STARTS = [
        ('1', 'Monday'), ('2', 'Tuesday'), ('3', 'Wednesday'), ('4', 'Thursday'),
        ('5', 'Friday'), ('6', 'Saturday'), ('7', 'Sunday'),
    ]
    GROUPINGS = [('[3,0]', 'International Grouping'), ('[3,2,0]', 'Indian Grouping')]

    name         = fields.Char(max_length=64, help_text='Nombre del idioma (Odoo name).')
    code         = fields.Char(
        # La unicidad la declara ``_code_uniq`` en ``Meta.constraints``, como
        # la fuente: es un objeto de tabla, no un atributo del campo.
        max_length=16,
        help_text='Locale code (Odoo code, p. ej. es_MX). Único.',
    )
    iso_code     = fields.Char(
        max_length=16, blank=True, default='',
        help_text='ISO code — nombre del .po de traducción (Odoo iso_code).',
    )
    url_code     = fields.Char(
        max_length=16, help_text='Código en la URL (Odoo url_code).',
    )
    active       = fields.Boolean(default=False, help_text='Odoo active.')
    direction    = fields.Char(
        max_length=3, choices=DIRECTIONS, default='ltr',
        help_text='Dirección de escritura (Odoo direction).',
    )
    date_format  = fields.Char(
        max_length=32, default='%m/%d/%Y', help_text='Formato de fecha (Odoo date_format).',
    )
    time_format  = fields.Char(
        max_length=32, choices=TIME_FORMATS, default='%H:%M:%S',
        help_text='Formato de hora (Odoo time_format).',
    )
    week_start   = fields.Char(
        max_length=1, choices=WEEK_STARTS, default='7',
        help_text='Primer día de la semana (Odoo week_start).',
    )
    grouping     = fields.Char(
        max_length=16, choices=GROUPINGS, default='[3,0]',
        help_text='Formato de agrupamiento de miles (Odoo grouping).',
    )
    decimal_point = fields.Char(
        max_length=4, default='.', help_text='Separador decimal (Odoo decimal_point).',
    )
    thousands_sep = fields.Char(
        max_length=4, blank=True, default=',',
        help_text='Separador de miles (Odoo thousands_sep).',
    )

    class Meta:
        db_table = 'res_lang'
        ordering = ['-active', 'name']
        verbose_name = 'Idioma'
        verbose_name_plural = 'Idiomas'
        constraints = [
            # Los tres ``models.Constraint`` de la fuente
            # (``odoo19c: res_lang.py:110-121``), con su nombre conservado.
            models.UniqueConstraint(
                fields=['name'], name='res_lang_name_uniq',
                violation_error_message='The name of the language must be unique!',
            ),
            models.UniqueConstraint(
                fields=['code'], name='res_lang_code_uniq',
                violation_error_message='The code of the language must be unique!',
            ),
            models.UniqueConstraint(
                fields=['url_code'], name='res_lang_url_code_uniq',
                violation_error_message='The URL code of the language must be unique!',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'

    @classmethod
    def get_installed(cls):
        """≙ ``get_installed`` (``odoo19c: odoo/addons/base/models/res_lang.py:311-313``).

        Los pares ``(code, name)`` de los idiomas **activos**, ordenados por
        nombre. La fuente los saca de ``_get_active_by('code')``, una caché de
        ``LangData`` indexada por el campo que se le pida; aquí la consulta va
        directa al gestor porque esa caché es del ORM de la referencia y su
        porte no es de este archivo.
        """
        return [
            (row.code, row.name)
            for row in cls.objects.filter(active=True).order_by('name')
        ]

    def format(self, percent, value, grouping=False):
        """≙ ``format`` (``odoo19c: res_lang.py:418-446``).

        Aplica el especificador ``percent`` al valor y luego **localiza** el
        resultado: el separador decimal de este idioma, y —si ``grouping``— la
        agrupación de miles que ``grouping`` declara.

        Es lo que separa ``1234567.89`` de ``1,234,567.89``, y el agrupamiento
        no es universal: ``[3, 0]`` reparte de tres en tres, pero hay
        localizaciones que declaran ``[3, 2, 0]`` (el sistema indio:
        ``12,34,567``). Por eso la agrupación se lee del **registro**, no de
        una constante.

        :param percent: un único especificador ``%`` (``'%.2f'``).
        :param value: el valor a formatear.
        :param grouping: si se agrupan los miles.
        :return: la cadena localizada.
        """
        if not percent or percent[0] != '%':
            raise ValidationError(
                'format() necesita exactamente un especificador %char.')

        formatted = percent % value
        decimal_point = self.decimal_point or '.'

        if grouping:
            thousands_sep = self.thousands_sep or ''
            lang_grouping = ast.literal_eval(self.grouping or '[]')
            if percent[-1] in 'eEfFgG':
                parts = formatted.split('.')
                parts[0] = intersperse(parts[0], lang_grouping,
                                       thousands_sep)[0]
                formatted = decimal_point.join(parts)
            elif percent[-1] in 'diu':
                formatted = intersperse(formatted, lang_grouping,
                                        thousands_sep)[0]
        elif percent[-1] in 'eEfFgG' and '.' in formatted:
            formatted = formatted.replace('.', decimal_point)

        return formatted


def split(sequence, counts):
    """≙ ``split`` (``odoo19c: res_lang.py:465-499``).

    Parte ``sequence`` en tramos de los tamaños que ``counts`` enumera, con dos
    marcas especiales que el agrupamiento numérico necesita: ``0`` significa
    *«sigue repitiendo el último tamaño hasta agotar»* —que es lo que hace que
    ``[3, 0]`` agrupe de tres en tres sin declarar cuántos grupos hay— y ``-1``
    significa *«para aquí»*, es decir, no agrupes el resto.

    >>> split('hello world', [2, 3])
    ['he', 'llo', ' world']
    >>> split('hello world', [2, -1, 3])
    ['he', 'llo world']
    """
    res = []
    saved_count = len(sequence)   # el tamaño a repetir cuando llegue un cero
    for count in counts:
        if not sequence:
            break
        if count == -1:
            break
        if count == 0:
            while sequence:
                res.append(sequence[:saved_count])
                sequence = sequence[saved_count:]
            break
        res.append(sequence[:count])
        sequence = sequence[count:]
        saved_count = count
    if sequence:
        res.append(sequence)
    return res


INTERSPERSE_PAT = re.compile('([^0-9]*)([^ ]*)(.*)')


def intersperse(string, counts, separator=''):
    """≙ ``intersperse`` (``odoo19c: res_lang.py:503-513``).

    Inserta ``separator`` entre los tramos que ``counts`` define, **contando
    desde la derecha** — que es la única forma correcta para un número: los
    miles se agrupan desde el punto decimal hacia atrás, no desde el principio.
    De ahí las tres inversiones del cuerpo.

    El patrón separa la cadena en tres: lo que va antes del primer dígito (un
    signo, un símbolo de moneda), los dígitos, y el resto. Sólo se agrupa el
    tramo del medio.

    Devuelve ``(cadena, número_de_separadores_insertados)``, como la fuente.
    """
    left, rest, right = INTERSPERSE_PAT.match(string).groups()
    splits = split(rest[::-1], counts)
    res = separator.join(s[::-1] for s in reversed(splits))
    return left + res + right, max(len(splits) - 1, 0)
