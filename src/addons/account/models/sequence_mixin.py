"""Secuencia editable con numeración sin huecos — ≙ ``sequence.mixin``.

Adaptación de ``addons/account/models/sequence_mixin.py``
(``odoo-tools@622ddc2a``, ``odoo19c:``). Es el mecanismo que da a un documento
contable un número **consecutivo, sin huecos y único por diario**, y que sabe
deducir si esa numeración se reinicia cada año, cada mes o nunca.

Quién lo hereda
================

En la referencia lo heredan cuatro modelos; dentro de lo que portamos, **uno**:
``account.move``. Los otros tres son localizaciones fuera de alcance —
``l10n_es_edi_tbai``, ``l10n_hr_edi`` y ``l10n_my_edi`` (en ``odoo18c``,
``l10n_my_edi_pos``). Medido sobre los cuatro árboles.

Un mixin con un solo consumidor no es un mixin de más: es la forma que tiene la
referencia, y separar el mecanismo del modelo es lo que permite que el segundo
consumidor no lo reimplemente. Ya ocurrió una vez en este proyecto con el
redondeo de divisa (:ref:`h-api-325`).

Por qué el número vive en dos columnas
=======================================

``name`` es texto (``INV/VTA/2026/00042``); ``sequence_prefix`` y
``sequence_number`` son su forma **consultable**. Sin ellas, "dame el último"
se responde ordenando por ``name`` — un orden de **cadena** que se rompe a los
100 000 documentos, porque ``'/100000'`` es lexicográficamente menor que
``'/99999'``: la secuencia propone un número ya usado, el UNIQUE lo rechaza y
el diario queda atascado de forma permanente. Ver :ref:`h-api-339`, que es
exactamente ese defecto y la razón de ser de estas dos columnas.

Tres divergencias de mecanismo, declaradas
===========================================

1. **El bloqueo.** La referencia serializa apoyándose en el UNIQUE de la tabla
   más *savepoints*: intenta escribir, y si choca reintenta con el siguiente
   (``odoo19c: sequence_mixin.py:355``). Aquí se usa un **advisory lock de
   transacción** por prefijo (``pg_advisory_xact_lock``). Mismo efecto —
   unicidad entre transacciones concurrentes— y una ventaja: el advisory lock
   funciona **aunque no exista ninguna fila todavía**, que es justo el caso en
   que dos transacciones crean el primer documento de un diario a la vez. Se
   libera solo al terminar la transacción, sin ``unlock`` explícito que se
   pueda olvidar.

2. **Los campos computados almacenados.** Allá son ``compute=... store=True``,
   recalculados por el ORM. Aquí se pueblan en ``split_sequence()``, invocado
   por quien asigna el nombre. Es la misma decisión ya tomada para el resto de
   los ``compute`` del porte.

3. **El índice.** La referencia lo crea en ``init()`` con SQL directo. Aquí va
   como ``Meta.indexes`` del modelo concreto, que es donde Django lo sabe
   gestionar y donde una migración lo puede versionar.

Lo que este archivo NO hace
============================

No numera al crear: numera al **publicar**. Es la semántica de la referencia —
un borrador no consume número— y la que ``AccountMove.post()`` ya implementaba
antes de existir este mixin.
"""
import re

from django.db import connection, models

from exceptions import ValidationError
from tools.translate import _

#: Piezas del patrón, iguales a las de la referencia
#: (``odoo19c: sequence_mixin.py:31-39``). Se conservan verbatim porque son el
#: contrato de qué formas de numeración se saben leer.
_PREFIX = r'(?P<prefix1>.*?)'
_PREFIX2 = r'(?P<prefix2>\D)'
_PREFIX3 = r'(?P<prefix3>\D+?)'
_SEQ = r'(?P<seq>\d*)'
_MONTH = r'(?P<month>(0[1-9]|1[0-2]))'
_YEAR = r'(?P<year>((?<=\D)|(?<=^))((19|20|21)\d{2}|(\d{2}(?=\D))))'
_YEAR_END = r'(?P<year_end>((?<=\D)|(?<=^))((19|20|21)\d{2}|(\d{2}(?=\D))))'
_SUFFIX = r'(?P<suffix>\D*?)'


class SequenceMixin(models.Model):
    """Numeración consecutiva con periodicidad deducida del nombre anterior."""

    #: Campo que lleva el nombre secuenciado.
    sequence_field = 'name'
    #: Campo de fecha con el que se comprueba que el número cae en su periodo.
    sequence_date_field = 'date'
    #: Campo por el que se segmenta la secuencia (``journal`` en ``AccountMove``).
    #: ``None`` = una sola secuencia global.
    sequence_index = None

    sequence_year_range_monthly_regex = (
        rf'^{_PREFIX}{_YEAR}{_PREFIX2}{_YEAR_END}(?P<prefix3>\D){_MONTH}'
        rf'(?P<prefix4>\D+?){_SEQ}{_SUFFIX}$')
    sequence_year_range_regex = (
        rf'^(?:{_PREFIX}{_YEAR}{_PREFIX2}{_YEAR_END}{_PREFIX3})?{_SEQ}{_SUFFIX}$')
    sequence_monthly_regex = (
        rf'^{_PREFIX}{_YEAR}(?P<prefix2>\D*?){_MONTH}{_PREFIX3}{_SEQ}{_SUFFIX}$')
    sequence_yearly_regex = (
        rf'^{_PREFIX}(?P<year>((?<=\D)|(?<=^))((19|20|21)?\d{{2}}))'
        rf'(?P<prefix2>\D+?){_SEQ}{_SUFFIX}$')
    sequence_fixed_regex = rf'^{_PREFIX}(?P<seq>\d{{0,9}}){_SUFFIX}$'

    sequence_prefix = models.CharField(
        max_length=128, blank=True, default='', db_index=True,
        help_text='Parte no numérica del nombre — p. ej. ``INV/VTA/2026/``. '
                  'Es la forma consultable del prefijo (Odoo sequence_prefix).')
    sequence_number = models.IntegerField(
        default=0,
        help_text='Parte numérica del nombre, como entero. El "último" se '
                  'obtiene con MAX sobre esta columna, nunca ordenando el '
                  'nombre — ver H-API-339 (Odoo sequence_number).')

    class Meta:
        abstract = True

    # -- partir el nombre --------------------------------------------------

    @classmethod
    def _non_capturing(cls, regex):
        """Convierte los grupos con nombre en grupos sin captura.

        ``(?P<seq>\\d*)`` → ``(?:\\d*)``. Sirve para reutilizar el mismo patrón
        cuando sólo interesa **una** posición: se deja capturando la que se
        quiere y se anulan las demás (``odoo19c: sequence_mixin.py:227``).
        """
        return re.sub(r'\(\?P<\w+>', '(?:', regex)

    def split_sequence(self):
        """Puebla ``sequence_prefix``/``sequence_number`` desde el nombre.

        ≙ ``_compute_split_sequence``. El truco es el de la referencia: se toma
        el patrón fijo, se le quita el nombre al grupo ``seq`` para que sea el
        **único** grupo capturante, y el prefijo es todo lo que hay antes de su
        inicio. Así el corte no depende de que el separador sea ``/``.
        """
        name = getattr(self, self.sequence_field, '') or ''
        regex = self._non_capturing(self.sequence_fixed_regex.replace(r'?P<seq>', ''))
        matching = re.match(regex, name)
        if not matching:
            self.sequence_prefix = name
            self.sequence_number = 0
            return
        self.sequence_prefix = name[:matching.start(1)]
        self.sequence_number = int(matching.group(1) or 0)

    # -- deducir la periodicidad -------------------------------------------

    @classmethod
    def deduce_sequence_number_reset(cls, name):
        """¿La numeración se reinicia por año, por mes, por rango o nunca?

        ≙ ``_deduce_sequence_number_reset``. Se deduce del **nombre anterior**,
        no de una configuración: el formato que alguien usó una vez es el
        contrato que la serie debe seguir.

        El guard de ``year_end`` es el que evita leer ``2026/2030`` como un
        rango: dos años sólo forman rango si el segundo es el siguiente, y con
        la misma cantidad de dígitos.
        """
        candidatos = [
            (cls.sequence_year_range_monthly_regex, 'year_range_month',
             ('seq', 'year', 'year_end', 'month')),
            (cls.sequence_monthly_regex, 'month', ('seq', 'month', 'year')),
            (cls.sequence_year_range_regex, 'year_range', ('seq', 'year', 'year_end')),
            (cls.sequence_yearly_regex, 'year', ('seq', 'year')),
            (cls.sequence_fixed_regex, 'never', ('seq',)),
        ]
        for regex, valor, requeridos in candidatos:
            match = re.match(regex, name or '')
            if not match:
                continue
            grupos = match.groupdict()
            year, year_end = grupos.get('year'), grupos.get('year_end')
            if year and year_end:
                incompatible = (
                    len(year) < len(year_end)
                    or cls._truncate_year(int(year) + 1, len(year_end)) != int(year_end))
                if incompatible:
                    continue
            if all(grupos.get(r) is not None for r in requeridos):
                return valor
        raise ValidationError(_(
            'El patrón de secuencia debe contener al menos el grupo «seq». '
            'Por ejemplo: ^(?P<prefix1>.*?)(?P<seq>\\d*)(?P<suffix>\\D*?)$'))

    @staticmethod
    def _truncate_year(year, length):
        """Recorta el año a los últimos ``length`` dígitos (2027 → 27)."""
        return year % (10 ** length)

    # -- consultar el último -----------------------------------------------

    def get_last_sequence_number(self, with_prefix=None):
        """El mayor ``sequence_number`` del prefijo, o ``None`` si no hay.

        ≙ la mitad útil de ``_get_last_sequence``. **MAX sobre la columna
        entera**, no orden sobre el nombre: es el punto de :ref:`h-api-339`.
        Excluye la propia fila para que renumerar un documento no se compare
        consigo mismo.
        """
        prefix = self.sequence_prefix if with_prefix is None else with_prefix
        qs = type(self).objects.filter(sequence_prefix=prefix)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if self.sequence_index:
            qs = qs.filter(**{self.sequence_index: getattr(self, f'{self.sequence_index}_id', None)})
        return qs.aggregate(models.Max('sequence_number'))['sequence_number__max']

    def lock_sequence(self, prefix):
        """Serializa por prefijo dentro de la transacción actual.

        ≙ el efecto de ``_locked_increment``, por otro mecanismo (ver el
        docstring del módulo). ``pg_advisory_xact_lock`` toma un lock asociado
        a la transacción: dos transacciones que numeren el **mismo** prefijo se
        ponen en fila, y las de prefijos distintos no se estorban. Se libera al
        hacer COMMIT o ROLLBACK, sin liberación explícita.

        Sin esto, dos transacciones concurrentes leen el mismo MAX y proponen
        el mismo número; una de las dos muere con IntegrityError.
        """
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', [prefix])

    # -- comprobar que el número cae en su periodo -------------------------

    def sequence_matches_date(self):
        """¿El nombre corresponde al periodo de su fecha?

        ≙ ``_sequence_matches_date``. Un asiento fechado en enero de 2027 con
        número ``INV/2026/00042`` es una numeración fuera de periodo: no es un
        error de formato, es un documento mal fechado o mal numerado.

        Devuelve ``True`` cuando no hay con qué comparar (sin nombre, sin
        fecha, o periodicidad ``never``) — la ausencia de evidencia no es
        evidencia de conflicto.
        """
        name = getattr(self, self.sequence_field, '') or ''
        date = getattr(self, self.sequence_date_field, None)
        if not name or name == '/' or not date:
            return True
        reset = self.deduce_sequence_number_reset(name)
        if reset == 'never':
            return True
        match = re.match(self.sequence_fixed_regex, name)
        if not match:
            return True
        for regex, comprobar in (
            (self.sequence_monthly_regex, ('year', 'month')),
            (self.sequence_yearly_regex, ('year',)),
        ):
            m = re.match(regex, name)
            if not m:
                continue
            grupos = m.groupdict()
            if 'year' in comprobar and grupos.get('year') is not None:
                year = int(grupos['year'])
                esperado = date.year if len(grupos['year']) == 4 else date.year % 100
                if year != esperado:
                    return False
            if 'month' in comprobar and grupos.get('month') is not None:
                if int(grupos['month']) != date.month:
                    return False
            return True
        return True

    # -- cadena de secuencia -----------------------------------------------

    def is_last_from_seq_chain(self):
        """¿Es el último de su serie?

        ≙ ``_is_last_from_seq_chain``. Es la pregunta que permite decidir si un
        documento se puede anular sin dejar un hueco: sólo el último puede
        irse sin romper la continuidad que la numeración promete.
        """
        last = self.get_last_sequence_number()
        if last is None:
            return True
        return self.sequence_number >= last
