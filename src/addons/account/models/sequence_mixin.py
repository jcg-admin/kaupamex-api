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

**Cobertura: 19 de los 21 métodos de la referencia.** Los dos que faltan, con
su razón:

- ``_get_sequence_cache`` — caché por transacción para evitar un savepoint por
  documento al numerar en lote. No aplica: con el advisory lock no hay
  savepoints que ahorrar. Divergencia de **rendimiento**, no de resultado;
  detallada en ``set_next_sequence``.
- ``write`` — en la referencia intercepta la reescritura del campo de secuencia
  para invalidar la caché anterior y revalidar el periodo. Su equivalente aquí
  sería ``save()``, pero interceptarlo en un modelo **abstracto** obligaría a
  cada consumidor a llamar a ``super()`` en el orden correcto, y hoy el único
  consumidor (``AccountMove``) ya valida en ``post()``, que es donde se asigna
  el número. Queda como **DESCONOCIDO declarado**: se decide cuando exista un
  segundo consumidor que numere fuera de ``post()`` — antes no hay con qué
  comparar el diseño.
"""
import calendar
import datetime
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
        qs = self.get_last_sequence_domain(type(self).objects.all())
        qs = qs.filter(sequence_prefix=prefix)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.aggregate(models.Max('sequence_number'))['sequence_number__max']

    @staticmethod
    def get_sequence_cache():
        """Caché de secuencia con vida de **transacción**.

        ≙ ``_get_sequence_cache``. En la referencia cuelga de ``cr.cache`` y
        existe para no pedir un savepoint por documento al numerar en lote;
        aquí cuelga de ``connection`` y se limpia al cerrar la transacción,
        que es el equivalente de este ORM.

        El ciclo de vida es lo que la hace correcta, no la velocidad: la
        entrada sólo es válida **mientras la transacción sostiene el lock**
        del prefijo. En cuanto se libera, otra transacción puede consumir el
        siguiente número y la caché dejaría de saberlo.

        Por eso se invalida en ``lock_sequence()`` —el único punto donde se
        sabe qué prefijo se está protegiendo— y no colgando un ``on_commit``:
        ese hook no corre en ROLLBACK, así que dejaría entradas vivas justo
        cuando la transacción que las validaba se deshizo. La invalidación por
        cambio de prefijo cubre los dos desenlaces sin depender de API interna
        del ORM.
        """
        cache = getattr(connection, '_sequence_mixin_cache', None)
        if cache is None:
            cache = {}
            connection._sequence_mixin_cache = cache
        return cache

    @classmethod
    def clear_sequence_cache(cls):
        """Invalida la caché de secuencia de la transacción actual."""
        connection._sequence_mixin_cache = None

    def save(self, *args, **kwargs):
        """≙ el ``write`` de la referencia: invalida la caché al renombrar.

        La referencia intercepta ``write`` para vaciar la caché cuando alguien
        toca el campo de secuencia (``odoo19c: sequence_mixin.py:114-117``); el
        equivalente en este ORM es ``save()``.

        Por qué importa: si un documento se renumera a mano, el último número
        cacheado deja de describir la serie. Sin esta invalidación, el
        siguiente documento de la misma transacción heredaría un valor obsoleto
        y podría chocar con el UNIQUE.

        El guard ``update_fields`` evita vaciar la caché en cada ``save()`` que
        no toque el nombre — el equivalente del ``if self._sequence_field in
        vals`` de la referencia.
        """
        update_fields = kwargs.get('update_fields')
        toca_secuencia = update_fields is None or self.sequence_field in update_fields
        if toca_secuencia:
            self.clear_sequence_cache()
        return super().save(*args, **kwargs)

    def lock_sequence(self, prefix):
        """Serializa por prefijo dentro de la transacción actual.

        ≙ el efecto de ``_locked_increment``, por otro mecanismo (ver el
        docstring del módulo). ``pg_advisory_xact_lock`` toma un lock asociado
        a la transacción: dos transacciones que numeren el **mismo** prefijo se
        ponen en fila, y las de prefijos distintos no se estorban. Se libera al
        hacer COMMIT o ROLLBACK, sin liberación explícita.

        Sin esto, dos transacciones concurrentes leen el mismo MAX y proponen
        el mismo número; una de las dos muere con IntegrityError.

        Invalida además la caché si el prefijo protegido cambia: una entrada
        cacheada sólo vale mientras se sostenga el lock de **su** prefijo.
        """
        cache = self.get_sequence_cache()
        if cache.get('__prefix__') != prefix:
            cache.clear()
            cache['__prefix__'] = prefix
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

    @classmethod
    def is_end_of_seq_chain(cls, records):
        """¿Son estos registros los últimos de sus series?

        ≙ ``_is_end_of_seq_chain``, la versión en lote de
        ``is_last_from_seq_chain``. Existe porque anular N documentos de golpe
        no es N preguntas independientes: si se descartan el 41 y el 42 de la
        misma serie, **ambos** son válidos como corte aunque el 41 no sea el
        último visto por separado. Agrupa por serie, comprueba que los números
        de cada grupo sean consecutivos hasta el máximo, y sólo entonces
        acepta.
        """
        por_serie = {}
        for r in records:
            if not getattr(r, r.sequence_field, None):
                continue
            por_serie.setdefault(r.sequence_prefix, []).append(r)
        for prefijo, grupo in por_serie.items():
            numeros = sorted(r.sequence_number for r in grupo)
            ultimo = grupo[0].get_last_sequence_number(with_prefix=prefijo)
            if ultimo is None:
                continue
            # El bloque debe terminar en el último de la serie y no tener huecos.
            if numeros[-1] < ultimo:
                return False
            if numeros != list(range(numeros[0], numeros[-1] + 1)):
                return False
        return True

    # -- generar el siguiente nombre ---------------------------------------
    #
    # Ésta es la mitad de ESCRITURA del mecanismo. Sin ella el mixin sólo sabe
    # leer una numeración existente; es la que produce el nombre siguiente
    # respetando el formato que la serie ya venía usando.

    def get_last_sequence_name(self, relaxed=False):
        """El nombre completo del último de la serie, o ``None``.

        ≙ la otra mitad de ``_get_last_sequence``. ``get_last_sequence_number``
        devuelve el entero para el MAX; **esto devuelve el texto**, que es lo
        que hace falta para deducir el formato.

        ``relaxed``: si no hay ninguno con este prefijo, busca el último de
        **cualquier** prefijo del mismo segmento. Es como la referencia
        inaugura una serie nueva heredando el formato de la anterior, en vez
        de inventar uno.
        """
        qs = self.get_last_sequence_domain(type(self).objects.all(), relaxed=relaxed)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        # El prefijo de la serie sale de la fila **más reciente del dominio**,
        # no del prefijo que trae este documento. Es la subconsulta
        # ``sequence_prefix = (SELECT sequence_prefix … ORDER BY id DESC
        # LIMIT 1)`` de la referencia (``odoo19c: sequence_mixin.py:373``), y
        # es la pieza que hace que ``relaxed`` sirva de algo: un documento sin
        # numerar lleva ``'/'``, así que filtrar por *su* prefijo no encuentra
        # nunca nada y toda la serie se reiniciaría en 1 en cada documento.
        prefijo = qs.order_by('-id').values_list('sequence_prefix', flat=True).first()
        if prefijo is None:
            return None
        last = qs.filter(sequence_prefix=prefijo).order_by('-sequence_number').first()
        return getattr(last, self.sequence_field, None) if last else None

    def get_last_sequence_domain(self, queryset, relaxed=False):
        """Acota qué filas cuentan como "la serie".

        ≙ ``_get_last_sequence_domain``. En la referencia devuelve un WHERE
        crudo; aquí recibe y devuelve un ``QuerySet``, que es el equivalente
        componible en este ORM. **Los dos lectores pasan por aquí**
        (``get_last_sequence_number`` y ``get_last_sequence_name``), igual que
        en la referencia los dos caminos de ``_get_last_sequence`` construyen
        su consulta con este dominio; si no, el hook sería decorativo.

        La base hace lo genérico: segmentar por ``sequence_index`` y descartar
        los que **no tienen número asignado**. Un documento sin numerar lleva
        ``'/'`` en su campo de secuencia, así que excluirlo es lo que impide
        que un borrador entre en el MAX y deje un hueco al descartarse.

        La subclase **extiende** — p. ej. ``AccountMove`` añade la ventana de
        fechas del periodo. Lo que la subclase NO hace es filtrar por estado:
        un documento cancelado conserva su número y debe seguir contando, o el
        siguiente lo reutilizaría.
        """
        if self.sequence_index:
            queryset = queryset.filter(
                **{self.sequence_index: getattr(self, f'{self.sequence_index}_id', None)})
        return queryset.exclude(**{f'{self.sequence_field}__in': ('', '/')})

    def get_starting_sequence(self):
        """El nombre base de una serie que aún no existe.

        ≙ ``_get_starting_sequence``. Hook para la subclase: la referencia
        devuelve ``'00000000'`` y espera que el modelo concreto lo redefina con
        su propio formato (``AccountMove`` compone diario + año). Se incrementa
        después, así que arranca en cero a propósito.
        """
        return '00000000'

    def get_sequence_format_param(self, previous):
        """Deriva de un nombre el formato y sus valores.

        ≙ ``_get_sequence_format_param``, y es **el corazón del mecanismo**:
        ``format.format(**values)`` reconstruye ``previous`` exactamente. Eso
        es lo que permite continuar la serie con el formato que alguien ya
        eligió —relleno, separadores, dos o cuatro dígitos de año— en vez de
        imponer uno nuevo.

        El patrón se elige según la periodicidad deducida, y de ahí salen las
        longitudes (``seq_length``, ``year_length``…) que conservan el relleno.
        """
        reset = self.deduce_sequence_number_reset(previous)
        regex = {
            'year': self.sequence_yearly_regex,
            'year_range': self.sequence_year_range_regex,
            'month': self.sequence_monthly_regex,
            'year_range_month': self.sequence_year_range_monthly_regex,
        }.get(reset, self.sequence_fixed_regex)

        values = re.match(regex, previous).groupdict()
        values['seq_length'] = len(values['seq'] or '')
        values['year_length'] = len(values.get('year') or '')
        values['year_end_length'] = len(values.get('year_end') or '')
        if not values.get('seq') and 'prefix1' in values and 'suffix' in values:
            # Sin número, lo que hay es prefijo y no sufijo: la referencia lo
            # reinterpreta así para que el formato no quede invertido.
            values['prefix1'] = values['suffix']
            values['suffix'] = ''
        for campo in ('seq', 'year', 'month', 'year_end'):
            values[campo] = int(values.get(campo) or 0)

        marcadores = re.findall(
            r'\b(prefix\d|seq|suffix\d?|year|year_end|month)\b', regex)
        formato = ''.join(
            '{seq:0{seq_length}d}' if m == 'seq' else
            '{month:02d}' if m == 'month' else
            '{year:0{year_length}d}' if m == 'year' else
            '{year_end:0{year_end_length}d}' if m == 'year_end' else
            '{%s}' % m
            for m in marcadores
        )
        return formato, values

    def get_sequence_date_range(self, reset):
        """Ventana de fechas que cubre la periodicidad dada.

        ≙ ``_get_sequence_date_range``. ``never`` devuelve el rango máximo
        representable: una serie que no se reinicia cubre cualquier fecha.
        """
        ref = getattr(self, self.sequence_date_field, None) or datetime.date.today()
        if reset in ('year', 'year_range', 'year_range_month'):
            return datetime.date(ref.year, 1, 1), datetime.date(ref.year, 12, 31)
        if reset == 'month':
            ultimo = calendar.monthrange(ref.year, ref.month)[1]
            return datetime.date(ref.year, ref.month, 1), datetime.date(ref.year, ref.month, ultimo)
        if reset == 'never':
            return datetime.date(1, 1, 1), datetime.date(9999, 12, 31)
        raise NotImplementedError(reset)

    def get_next_sequence_format(self):
        """Formato y valores del **siguiente** nombre de la serie.

        ≙ ``_get_next_sequence_format``. Dos caminos:

        - la serie ya existe → se toma su último nombre y se hereda su formato;
        - la serie es nueva → se busca en modo ``relaxed`` un nombre del mismo
          segmento para heredar su forma, y si tampoco hay se parte de
          ``get_starting_sequence()``. En ese caso los campos de periodo se
          fijan desde la fecha del documento y el contador arranca en 0.
        """
        ultimo = self.get_last_sequence_name()
        nueva = not ultimo
        if nueva:
            ultimo = self.get_last_sequence_name(relaxed=True) or self.get_starting_sequence()

        formato, valores = self.get_sequence_format_param(ultimo)
        if nueva:
            reset = self.deduce_sequence_number_reset(ultimo)
            inicio, fin = self.get_sequence_date_range(reset)
            fecha = getattr(self, self.sequence_date_field, None) or inicio
            valores['seq'] = 0
            valores['year'] = self._truncate_year(inicio.year, valores['year_length'] or 4)
            valores['year_end'] = self._truncate_year(fin.year, valores['year_end_length'] or 4)
            valores['month'] = fecha.month
        return formato, valores

    def set_next_sequence(self):
        """Asigna el siguiente nombre de la serie, con bloqueo.

        ≙ ``_set_next_sequence``. El orden importa: **primero el lock, después
        la lectura**. Al revés, dos transacciones leerían el mismo último antes
        de que ninguna bloquee, y propondrían el mismo número.

        La referencia sostiene además una caché por transacción para no pedir
        un savepoint por documento al numerar en lote
        (``odoo19c: sequence_mixin.py:355``). Aquí no se porta: con el advisory
        lock no hay savepoints que ahorrar, y una caché de sesión sería estado
        mutable sin el ciclo de vida del ``env`` de Odoo que la limpia. Es una
        divergencia de rendimiento, no de resultado.
        """
        self.split_sequence()
        # La clave del lock es la **identidad de la serie**, no el prefijo que
        # el documento trae. Un borrador se llama ``'/'``, así que su prefijo
        # partido es ``'/'`` para todos: usarlo pondría en fila a todos los
        # documentos de todos los segmentos sobre un único lock, y además no
        # protegería la serie que se va a escribir. ``get_starting_sequence()``
        # es determinista a partir del segmento y la fecha del documento, así
        # que dos escritores de la misma serie coinciden en la clave **antes**
        # de leer, que es lo que el orden lock→lectura necesita.
        self.lock_sequence(self.get_starting_sequence())

        formato, valores = self.get_next_sequence_format()
        valores['seq'] = valores.get('seq', 0) + 1
        nombre = formato.format(**valores)

        setattr(self, self.sequence_field, nombre)
        self.split_sequence()
        return nombre

    # -- validación de periodo ---------------------------------------------

    def must_check_date_sequence(self):
        """Hook: ¿se comprueba que el número cae en su periodo?

        ≙ ``_must_check_constrains_date_sequence``. La subclase lo desactiva
        cuando la serie es legítimamente independiente de la fecha.
        """
        return True

    def year_matches(self, format_value, year):
        """¿El año del nombre corresponde al del documento?

        ≙ ``_year_match``. Compara truncando a la longitud que el nombre usa,
        para que ``26`` y ``2026`` se consideren el mismo año.
        """
        return format_value == self._truncate_year(year, len(str(format_value)))

    def constrains_date_sequence(self):
        """Valida que el nombre y la fecha hablen del mismo periodo.

        ≙ ``_constrains_date_sequence``. Lanza en vez de devolver ``False``
        porque es una restricción de integridad contable: un documento
        numerado en una serie de 2026 y fechado en 2027 rompe la correlación
        que la numeración promete al fisco.
        """
        if not self.must_check_date_sequence():
            return
        if not self.sequence_matches_date():
            nombre = getattr(self, self.sequence_field, '')
            fecha = getattr(self, self.sequence_date_field, None)
            raise ValidationError(_(
                'La secuencia «%(name)s» no corresponde al periodo de la fecha '
                '%(date)s. Cambie la fecha o el número.'
            ) % {'name': nombre, 'date': fecha})
