"""``ir.sequence`` / ``ir.sequence.date_range`` — el generador de numeración.

Adaptación fiel de ``odoo19c: odoo/addons/base/models/ir_sequence.py`` (LGPL-3,
copia + adaptación con atribución). Es la **estructura de control** de la
numeración: prefijo y sufijo interpolados por fecha, relleno con ceros, paso de
incremento, ámbito por empresa, y subsecuencias por rango de fecha — que es lo
que hace que un folio reinicie al cambiar el ejercicio.

Las dos implementaciones de la fuente, y por qué importan
---------------------------------------------------------

``standard``
    Una **secuencia nativa de PostgreSQL** por cada ``ir.sequence``, con nombre
    ``ir_sequence_%03d``. ``nextval()`` es atómico y no bloquea, así que dos
    peticiones concurrentes reciben números distintos sin esperarse. A cambio
    **deja huecos**: una transacción que aborta se lleva su número.

``no_gap``
    El contador vive en la fila y se incrementa bajo ``SELECT … FOR UPDATE
    NOWAIT``. No deja huecos, y por eso serializa: la segunda petición espera o
    falla. Más lento, y es el que exige la autoridad fiscal cuando la
    numeración debe ser continua.

DIVERGENCIA RETIRADA, no heredada
----------------------------------

La versión anterior de este archivo declaraba:

    *"la variante PostgreSQL-sequence de Odoo (``_predict_nextval``) no aplica
    en MariaDB — el contador vive en la fila"*

Eso describía un motor que este proyecto **ya no usa**: ADR-028 fija PostgreSQL
desde 2026-08-06, y las secuencias nativas están disponibles. La divergencia se
retira y las seis funciones de módulo de la fuente se portan enteras. Ver
:ref:`h-api-792`.

Su consecuencia era peor que la ausencia: ``get_next`` hacía leer-modificar-
escribir **sin ningún candado**, así que dos llamadas concurrentes devolvían el
mismo número. Ni ``standard`` (que no lo necesita, porque delega en el motor)
ni ``no_gap`` (que lo necesita y no lo tenía).

DIVERGENCIA HEREDADA, declarada y con sucesor
----------------------------------------------

La fuente **no** declara ``_log_access = False`` en ninguna de las dos clases,
así que su ORM les añade las cuatro columnas de auditoría
(``create_uid``/``create_date``/``write_uid``/``write_date``). Aquí ninguna de
las dos hereda ``TimeStampedModel``: ``ir.sequence`` no lo hacía antes de este
porte, y ``ir.sequence.date_range`` se escribe igual que ella para no dejar dos
tablas hermanas con contratos distintos.

**No se corrige en este pase a propósito**: añadir las columnas a una tabla
viva es una migración con default sobre filas existentes, y ése es un cambio
con su propio riesgo, no un efecto colateral de portar la subsecuencia.
Sucesor: tarea **#40**.
"""
import logging
from datetime import datetime, timedelta

from django.db import connection, models as django_models
from django.utils import timezone

import fields
import models
from exceptions import UserError
from orm.environments import context_scope, get_context

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Las seis funciones de módulo de la fuente (``:13-80``)
# ---------------------------------------------------------------------------

def _create_sequence(seq_name, number_increment, number_next):
    """≙ ``_create_sequence`` (``odoo19c: ir_sequence.py:13-18``).

    ``CREATE SEQUENCE`` no admite parámetros para el nombre, así que el
    identificador se compone. **No es inyección**: el nombre lo produce
    ``'ir_sequence_%03d' % pk``, con un entero de la propia base.
    """
    if number_increment == 0:
        raise UserError('El paso no puede ser cero.')
    with connection.cursor() as cursor:
        cursor.execute(
            f'CREATE SEQUENCE {connection.ops.quote_name(seq_name)} '
            f'INCREMENT BY %s START WITH %s',
            [number_increment, number_next])


def _drop_sequences(seq_names):
    """≙ ``_drop_sequences`` (``:21-28``).

    ``RESTRICT`` es el default y se escribe igual que en la fuente, con su
    comentario: impide soltar la secuencia si algún objeto depende de ella.
    """
    if not seq_names:
        return
    names = ', '.join(connection.ops.quote_name(n) for n in seq_names)
    with connection.cursor() as cursor:
        cursor.execute(f'DROP SEQUENCE IF EXISTS {names} RESTRICT')


def _alter_sequence(seq_name, number_increment=None, number_next=None):
    """≙ ``_alter_sequence`` (``:31-49``).

    La guarda de la fuente se conserva verbatim en su intención: si la
    secuencia todavía no existe estamos dentro de ``create()`` y se ignora,
    porque se creará después.
    """
    if number_increment == 0:
        raise UserError('El paso no puede ser cero.')
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT relname FROM pg_class'
            ' WHERE relkind = %s AND relname = %s'
            '   AND relnamespace = current_schema::regnamespace',
            ['S', seq_name])
        if not cursor.fetchone():
            return
        partes = [f'ALTER SEQUENCE {connection.ops.quote_name(seq_name)}']
        args = []
        if number_increment is not None:
            partes.append('INCREMENT BY %s')
            args.append(number_increment)
        if number_next is not None:
            partes.append('RESTART WITH %s')
            args.append(number_next)
        cursor.execute(' '.join(partes), args)


def _select_nextval(seq_name):
    """≙ ``_select_nextval`` (``:52-54``)."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT nextval(%s)', [seq_name])
        return cursor.fetchone()[0]


def _update_nogap(record, number_increment):
    """≙ ``_update_nogap`` (``:57-63``) — el candado de la variante sin huecos.

    ``FOR UPDATE NOWAIT`` es la mitad del mecanismo y la que faltaba: sin él,
    dos transacciones leen el mismo ``number_next`` y devuelven el mismo
    número. ``NOWAIT`` hace que la segunda **falle** en vez de esperar, que es
    la decisión de la fuente: en una numeración sin huecos, esperar es peor que
    reintentar.

    La fuente hace ``flush_recordset``/``invalidate_recordset`` alrededor
    porque su ORM difiere la escritura. Django no la difiere, así que esas dos
    llamadas no tienen contraparte y su ausencia es una **divergencia de
    mecanismo declarada**, no un símbolo omitido.
    """
    tabla = connection.ops.quote_name(record._meta.db_table)
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT number_next FROM {tabla} WHERE id = %s FOR UPDATE NOWAIT',
            [record.pk])
        (number_next,) = cursor.fetchone()
        cursor.execute(
            f'UPDATE {tabla} SET number_next = number_next + %s WHERE id = %s',
            [number_increment, record.pk])
    record.number_next = number_next + number_increment
    return number_next


def _predict_nextval(seq_id):
    """≙ ``_predict_nextval`` (``:65-80``) — el próximo valor **sin consumirlo**.

    El comentario de la fuente explica por qué no usa ``currval()``: exige una
    llamada previa a ``nextval()`` en la misma sesión. Se lee de
    ``pg_sequences``, y la rama de ``server_version < 100000`` de la fuente
    **no se porta**: el mínimo efectivo de este proyecto es PostgreSQL 14
    (``docs: adr-028``), así que esa rama no tiene entorno donde ejercerse.
    """
    seq_name = f'ir_sequence_{seq_id}'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT last_value,'
            ' (SELECT increment_by FROM pg_sequences WHERE sequencename = %s),'
            f' is_called FROM {connection.ops.quote_name(seq_name)}',
            [seq_name])
        last_value, increment_by, is_called = cursor.fetchone()
    if is_called:
        return last_value + increment_by
    # La secuencia acaba de recibir RESTART: el próximo será last_value.
    return last_value


class IrSequence(models.Model):
    """``ir.sequence`` — ≙ ``IrSequence`` (``odoo19c: ir_sequence.py:83-292``).

    Docstring de la fuente, verbatim: *"The sequence model allows to define and
    use so-called sequence objects. Such objects are used to generate unique
    identifiers in a transaction-safe way."*
    """

    _name = 'ir.sequence'
    _description = 'Sequence'
    _order = 'name, id'
    #: La fuente lo declara ``False``: una secuencia NO se manipula con
    #: privilegio elevado desde un comando, porque su número es un hecho
    #: contable.
    _allow_sudo_commands = False

    IMPLEMENTATIONS = [('standard', 'Standard'), ('no_gap', 'No gap')]

    name = fields.Char(
        max_length=128, help_text='Odoo name.')
    code = fields.Char(
        max_length=64, blank=True, default='',
        help_text='Odoo code ("Sequence Code").')
    implementation = fields.Char(
        max_length=16, choices=IMPLEMENTATIONS, default='standard',
        help_text='Odoo implementation. "no_gap" garantiza que no falte '
                  'ningún número; es más lento que "standard".')
    active = fields.Boolean(default=True, help_text='Odoo active.')
    prefix = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Odoo prefix — interpolable por fecha.')
    suffix = fields.Char(
        max_length=128, blank=True, default='',
        help_text='Odoo suffix — interpolable por fecha.')
    number_next = fields.Integer(
        default=1, help_text='Odoo number_next ("Next Number").')
    number_increment = fields.Integer(
        default=1, help_text='Odoo number_increment ("Step").')
    padding = fields.Integer(
        default=0, help_text='Odoo padding ("Sequence Size") — ceros a la '
                             'izquierda.')
    use_date_range = fields.Boolean(
        default=False, help_text='Odoo use_date_range — subsecuencias por '
                                 'rango de fecha.')
    company = fields.Many2one(
        'base.ResCompany', on_delete=models.CASCADE, related_name='sequences',
        null=True, blank=True, help_text='Odoo company_id.')

    class Meta:
        db_table = 'ir_sequence'
        ordering = ['name', 'id']
        verbose_name = 'Secuencia'
        verbose_name_plural = 'Secuencias'

    def __str__(self):
        return f'{self.name}{" [" + self.code + "]" if self.code else ""}'

    # -- number_next_actual: compute + inverse de la fuente ---------------

    @property
    def number_next_actual(self):
        """≙ ``_get_number_next_actual`` (``:97-106``).

        Docstring de la fuente: *"Return number from ir_sequence row when
        no_gap implementation, and number from postgres sequence when standard
        implementation."*

        Es un ``compute`` sin ``store`` en la fuente; aquí es una ``property``,
        que es la equivalencia que este árbol declara para ese caso.
        """
        if not self.pk:
            return 0
        if self.implementation != 'standard':
            return self.number_next
        return _predict_nextval('%03d' % self.pk)

    @number_next_actual.setter
    def number_next_actual(self, value):
        """≙ ``_set_number_next_actual`` (``:108-110``) — el ``inverse``."""
        self.number_next = value or 1
        self.save(update_fields=['number_next'])

    # -- ciclo de vida: create / write / unlink de la fuente ---------------

    def save(self, *args, **kwargs):
        """≙ ``create`` (``:155-162``) y ``write`` (``:168-197``).

        Django no separa las dos operaciones, así que el discriminador es
        ``self._state.adding``. Las dos ramas conservan el contenido de la
        fuente:

        - al **crear** con ``standard``, se crea la secuencia nativa;
        - al **escribir**, las cuatro combinaciones que la fuente enumera en su
          comentario —*"4 cases: we test the previous impl. against the new
          one"*— deciden si se altera, se suelta o se crea.
        """
        creating = self._state.adding
        previous = None
        if not creating:
            previous = type(self).objects.filter(pk=self.pk).first()
        super().save(*args, **kwargs)

        if creating:
            if self.implementation == 'standard':
                # Los valores van VERBATIM, sin ``or 1``: la fuente escribe
                # ``vals.get('number_increment', 1)``, cuyo default aplica sólo
                # si la clave FALTA, no si vale cero. Un ``or`` se traga el
                # cero y con él la guarda *"Step must not be zero"* de
                # ``_create_sequence`` — el default ya lo pone el campo.
                _create_sequence('ir_sequence_%03d' % self.pk,
                                 self.number_increment, self.number_next)
            return

        if previous is None:
            return
        seq_name = 'ir_sequence_%03d' % self.pk
        if previous.implementation == 'standard':
            if self.implementation == 'standard':
                # No cambió la implementación: sólo se altera lo pedido.
                if self.number_next != previous.number_next:
                    _alter_sequence(seq_name, number_next=self.number_next)
                if self.number_increment != previous.number_increment:
                    _alter_sequence(seq_name,
                                    number_increment=self.number_increment)
                for sub in self.date_range_ids.all():
                    sub.alter_sequence(
                        number_increment=self.number_increment)
            else:
                _drop_sequences([seq_name])
                _drop_sequences([
                    'ir_sequence_%03d_%03d' % (self.pk, sub.pk)
                    for sub in self.date_range_ids.all()])
        elif self.implementation == 'standard':
            _create_sequence(seq_name, self.number_increment, self.number_next)
            for sub in self.date_range_ids.all():
                _create_sequence(
                    'ir_sequence_%03d_%03d' % (self.pk, sub.pk),
                    self.number_increment, sub.number_next)

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``:164-166``)."""
        _drop_sequences(['ir_sequence_%03d' % self.pk])
        return super().delete(*args, **kwargs)

    # -- el motor de numeración -------------------------------------------

    def _get_current_sequence(self, sequence_date=None):
        """≙ ``_get_current_sequence`` (``:113-128``).

        Docstring de la fuente: *"Returns the object on which we can find the
        number_next to consider for the sequence. It could be an ir.sequence or
        an ir.sequence.date_range depending if use_date_range is checked or
        not. This function will also create the ir.sequence.date_range if none
        exists yet for today."*
        """
        if not self.use_date_range:
            return self
        sequence_date = sequence_date or timezone.now().date()
        rango = self.date_range_ids.filter(
            date_from__lte=sequence_date, date_to__gte=sequence_date).first()
        if rango is not None:
            return rango
        return self._create_date_range_seq(sequence_date)

    def _next_do(self):
        """≙ ``_next_do`` (``:199-204``) — el número, por la vía que toque."""
        if self.implementation == 'standard':
            number_next = _select_nextval('ir_sequence_%03d' % self.pk)
        else:
            number_next = _update_nogap(self, self.number_increment)
        return self.get_next_char(number_next)

    def _get_prefix_suffix(self, date=None, date_range=None):
        """≙ ``_get_prefix_suffix`` (``:206-236``).

        Los **quince** tokens de la fuente, cada uno en sus tres formas
        (``x``, ``range_x``, ``current_x``) — cuarenta y cinco claves. La
        versión anterior portaba siete en una sola forma, y un prefijo que
        usara ``%(isoweek)s`` reventaba con ``KeyError``.

        El segundo canal de la fecha es el **contexto**, igual que en la
        fuente: ``date or self.env.context.get('ir_sequence_date')``. Aquí ese
        ``env.context`` es ``orm.environments.get_context()`` (DEC-AISL-04,
        tercer eje) — el mecanismo existe, así que la firma de la fuente se
        porta tal cual en vez de ensanchar la de ``get_next_char``.
        """
        contexto = get_context()
        ahora = rango = efectiva = timezone.localtime()
        date = date or contexto.get('ir_sequence_date')
        date_range = date_range or contexto.get('ir_sequence_date_range')
        if date is not None:
            efectiva = date if isinstance(date, datetime) else (
                datetime.combine(date, datetime.min.time()))
        if date_range is not None:
            rango = date_range if isinstance(date_range, datetime) else (
                datetime.combine(date_range, datetime.min.time()))

        formatos = {
            'year': '%Y', 'month': '%m', 'day': '%d', 'y': '%y', 'doy': '%j',
            'woy': '%W', 'weekday': '%w', 'h24': '%H', 'h12': '%I',
            'min': '%M', 'sec': '%S',
            'isoyear': '%G', 'isoy': '%g', 'isoweek': '%V',
        }
        tokens = {}
        for clave, formato in formatos.items():
            tokens[clave] = efectiva.strftime(formato)
            tokens['range_' + clave] = rango.strftime(formato)
            tokens['current_' + clave] = ahora.strftime(formato)

        try:
            prefijo = (self.prefix % tokens) if self.prefix else ''
            sufijo = (self.suffix % tokens) if self.suffix else ''
        except (ValueError, TypeError, KeyError):
            raise UserError(
                f'Prefijo o sufijo inválido en la secuencia «{self.name}».')
        return prefijo, sufijo

    def get_next_char(self, number_next):
        """≙ ``get_next_char`` (``:238-240``).

        Firma de la fuente, un solo argumento: la fecha del rango **no** viaja
        por parámetro sino por el contexto que fija ``_next``.
        """
        prefijo, sufijo = self._get_prefix_suffix()
        return prefijo + '%%0%sd' % self.padding % number_next + sufijo

    def _create_date_range_seq(self, date):
        """≙ ``_create_date_range_seq`` (``:242-255``).

        El año natural como rango por defecto, **recortado** por los rangos
        vecinos: si ya existe uno que empieza después, éste termina el día
        anterior; si existe uno que termina antes, éste empieza el día
        siguiente. Es lo que impide que dos rangos se solapen.
        """
        if isinstance(date, datetime):
            date = date.date()
        year = date.strftime('%Y')
        date_from = datetime.strptime(f'{year}-01-01', '%Y-%m-%d').date()
        date_to = datetime.strptime(f'{year}-12-31', '%Y-%m-%d').date()

        posterior = self.date_range_ids.filter(
            date_from__gte=date, date_from__lte=date_to
        ).order_by('-date_from').first()
        if posterior is not None:
            date_to = posterior.date_from + timedelta(days=-1)
        anterior = self.date_range_ids.filter(
            date_to__gte=date_from, date_to__lte=date
        ).order_by('-date_to').first()
        if anterior is not None:
            date_from = anterior.date_to + timedelta(days=1)

        return IrSequenceDateRange.objects.create(
            sequence=self, date_from=date_from, date_to=date_to)

    def _next(self, sequence_date=None):
        """≙ ``_next`` (``:257-268``).

        Docstring de la fuente: *"Returns the next number in the preferred
        sequence in all the ones given in self."*
        """
        if not self.use_date_range:
            return self._next_do()
        dt = sequence_date or timezone.now()
        the_date = dt.date() if isinstance(dt, datetime) else dt
        rango = self.date_range_ids.filter(
            date_from__lte=the_date, date_to__gte=the_date).first()
        if rango is None:
            rango = self._create_date_range_seq(the_date)
        # La fuente entrega las dos fechas por CONTEXTO
        # (``with_context(ir_sequence_date_range=…, ir_sequence_date=…)``),
        # no por parámetro; por eso ``date_range._next()`` no recibe nada.
        with context_scope(ir_sequence_date=the_date,
                           ir_sequence_date_range=rango.date_from):
            return rango._next()

    def next_by_id(self, sequence_date=None):
        """≙ ``next_by_id`` (``:270-273``).

        Docstring de la fuente: *"Draw an interpolated string using the
        specified sequence."*

        DIVERGENCIA DECLARADA: la fuente hace ``self.browse().check_access(
        'read')`` antes. Aquí la autorización vive en la vista, por capacidad
        (DEC-11), y no en el modelo — el mismo criterio con que ``remove()`` de
        las claves de API perdió su ``@check_identity``.
        """
        return self._next(sequence_date=sequence_date)

    @classmethod
    def next_by_code(cls, sequence_code, company=None, sequence_date=None):
        """≙ ``next_by_code`` (``:275-292``).

        Docstring de la fuente: *"Draw an interpolated string using a sequence
        with the requested code. If several sequences with the correct code are
        available to the user (multi-company cases), the one from the user's
        current company will be used."*

        Se conserva la desambiguación multi-empresa: la propia gana sobre la
        global (el ``order='company_id'`` de la fuente). Sin secuencia, la
        fuente registra un ``debug`` y devuelve ``False``; aquí ``None``, que es
        el vacío tipado de este stack (:ref:`h-api-590`).
        """
        qs = cls.objects.filter(code=sequence_code, active=True)
        qs = (qs.filter(company__in=[company, None]) if company
              else qs.filter(company__isnull=True))
        secuencia = qs.order_by(
            django_models.F('company').desc(nulls_last=True), 'id').first()
        if secuencia is None:
            _logger.debug(
                "No ir.sequence has been found for code '%s'. Please make sure "
                "a sequence is set for current company.", sequence_code)
            return None
        return secuencia._next(sequence_date=sequence_date)


class IrSequenceDateRange(models.Model):
    """``ir.sequence.date_range`` — ≙ ``IrSequenceDate_Range`` (``:295-376``).

    La subsecuencia por rango: lo que hace que un folio reinicie al cambiar el
    ejercicio en vez de seguir corriendo. Su número vive aparte del de la
    secuencia madre, y con ``standard`` tiene su **propia** secuencia nativa,
    ``ir_sequence_%03d_%03d``.
    """

    _name = 'ir.sequence.date_range'
    _description = 'Sequence Date Range'
    _rec_name = 'sequence_id'
    _allow_sudo_commands = False

    date_from = fields.Date(help_text='Odoo date_from ("From").')
    date_to = fields.Date(help_text='Odoo date_to ("To").')
    sequence = fields.Many2one(
        'base.IrSequence', on_delete=models.CASCADE,
        related_name='date_range_ids',
        help_text='Odoo sequence_id ("Main Sequence").')
    number_next = fields.Integer(
        default=1, help_text='Odoo number_next ("Next Number").')

    class Meta:
        db_table = 'ir_sequence_date_range'
        ordering = ['date_from', 'id']
        verbose_name = 'Rango de secuencia'
        verbose_name_plural = 'Rangos de secuencia'
        constraints = [
            # ≙ ``_unique_range_per_sequence`` (``:301-304``), con su nombre
            # conservado. Es un objeto de tabla de 19, y su hogar aquí es
            # ``Meta.constraints`` (``atributos-de-clase-de-modelo.md``).
            django_models.UniqueConstraint(
                fields=['sequence', 'date_from', 'date_to'],
                name='unique_range_per_sequence',
                violation_error_message='No se pueden crear dos rangos de '
                                        'fecha iguales para la misma '
                                        'secuencia.'),
        ]

    def __str__(self):
        return f'{self.sequence_id} [{self.date_from} … {self.date_to}]'

    @property
    def number_next_actual(self):
        """≙ ``_get_number_next_actual`` (``:306-314``)."""
        if self.sequence.implementation != 'standard':
            return self.number_next
        return _predict_nextval('%03d_%03d' % (self.sequence_id, self.pk))

    @number_next_actual.setter
    def number_next_actual(self, value):
        """≙ ``_set_number_next_actual`` (``:316-318``)."""
        self.number_next = value or 1
        self.save(update_fields=['number_next'])

    @classmethod
    def default_get(cls, campos):
        """≙ ``default_get`` (``:320-325``).

        La fuente fuerza ``number_next_actual = 1`` en el formulario de alta.
        Aquí no hay formulario de ORM, así que el método existe para que el
        serializer o el comando que cree un rango tenga de dónde leer el mismo
        default sin volver a inventarlo.
        """
        resultado = {}
        if 'number_next_actual' in campos:
            resultado['number_next_actual'] = 1
        return resultado

    def _next(self):
        """≙ ``_next`` (``:336-341``) — firma de la fuente, sin argumentos.

        El número sale de **su** secuencia nativa, y el formato lo pone la
        madre: ``get_next_char`` es de ``ir.sequence``, no del rango. Las
        fechas con que se interpola el prefijo llegan por el contexto que fijó
        ``IrSequence._next``.
        """
        if self.sequence.implementation == 'standard':
            number_next = _select_nextval(
                'ir_sequence_%03d_%03d' % (self.sequence_id, self.pk))
        else:
            number_next = _update_nogap(self, self.sequence.number_increment)
        return self.sequence.get_next_char(number_next)

    def alter_sequence(self, number_increment=None, number_next=None):
        """≙ ``_alter_sequence`` (``:344-346``).

        DESPROMOCIÓN DECLARADA, y es la única del archivo: la fuente tiene
        **dos** símbolos con ese nombre —la función de módulo y este método— y
        allá no chocan porque uno vive en el módulo y el otro en la clase. Aquí
        el de módulo conserva ``_alter_sequence``; llamar igual a los dos en el
        mismo espacio de nombres los haría indistinguibles al leer. Es la
        excepción que ``porte-completo-no-parcial.md`` admite cuando la fuente
        declara ambos, declarada aquí y no en silencio.

        La fuente lo escribe sobre el **conjunto** (``for seq in self``);
        Django no tiene recordset, así que el bucle vive en quien llama.
        """
        _alter_sequence(
            'ir_sequence_%03d_%03d' % (self.sequence_id, self.pk),
            number_increment=number_increment, number_next=number_next)

    def save(self, *args, **kwargs):
        """≙ ``create`` (``:348-356``) y ``write`` (``:363-376``)."""
        creating = self._state.adding
        previous = None
        if not creating:
            previous = type(self).objects.filter(pk=self.pk).first()
        super().save(*args, **kwargs)

        if creating:
            if self.sequence.implementation == 'standard':
                _create_sequence(
                    'ir_sequence_%03d_%03d' % (self.sequence_id, self.pk),
                    self.sequence.number_increment, self.number_next)
            return
        if (previous is not None and self.number_next != previous.number_next
                and self.sequence.implementation == 'standard'):
            self.alter_sequence(number_next=self.number_next)

    def delete(self, *args, **kwargs):
        """≙ ``unlink`` (``:358-360``)."""
        _drop_sequences(['ir_sequence_%03d_%03d' % (self.sequence_id, self.pk)])
        return super().delete(*args, **kwargs)
